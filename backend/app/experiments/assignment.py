"""결정적 sticky 할당 + canary/홀드아웃 게이트(ADR-0064, 요구사항 1·3·4·6).

핵심: 같은 unit_id는 항상 같은 variant(sticky). 해시는 stdlib `hashlib`만 사용(새 의존성 없음).
토글 `EXPERIMENTS`(기본 off)면 항상 control(회귀 불변).
"""
from __future__ import annotations

import hashlib
import os

from .registry import Experiment, get


def experiments_enabled() -> bool:
    """실험 토글(기본 off). off면 모든 할당이 control(요구사항 3.1)."""
    return os.getenv("EXPERIMENTS", "").strip().lower() in ("1", "true", "yes", "on")


def bucket(salt: str, key: str, unit: str) -> float:
    """결정적 [0,1) 버킷 — md5 상위 64비트 / 2^64. 같은 입력 → 같은 값(요구사항 1.1).

    `salt`로 키/용도(할당 vs 게이트)별 독립 버킷을 만든다(상관관계 회피).
    """
    digest = hashlib.md5(f"{salt}:{key}:{unit}".encode()).digest()
    top = int.from_bytes(digest[:8], "big")
    return top / float(1 << 64)


def _weighted_pick(exp: Experiment, b: float) -> str:
    """가중치 누적 구간으로 variant 선택([0,1) 버킷 → variant). 합 0이면 control."""
    total = sum(max(0.0, v.weight) for v in exp.variants)
    if total <= 0 or not exp.variants:
        return exp.control
    target = b * total
    acc = 0.0
    for v in exp.variants:
        acc += max(0.0, v.weight)
        if target < acc:
            return v.name
    return exp.variants[-1].name


def assign(exp: Experiment, unit: str | None) -> str:
    """실험 할당 — 토글/게이트/가중 분배. control 폴백 안전(요구사항 1·6).

    순서: 토글 off → control · unit 없음 → control · holdout 구간 → control ·
    rollout 밖 → control · 그 외 가중 variant 분배.
    """
    if not experiments_enabled():
        return exp.control
    if not unit:
        return exp.control
    # holdout: 실험에서 제외(control 고정). 독립 솔트.
    if exp.holdout > 0.0 and bucket(exp.salt + "|holdout", exp.key, unit) < exp.holdout:
        return exp.control
    # rollout(canary): 비율 밖이면 미노출(control). rollout>=1이면 전원 통과.
    if exp.rollout < 1.0 and bucket(exp.salt + "|rollout", exp.key, unit) >= exp.rollout:
        return exp.control
    return _weighted_pick(exp, bucket(exp.salt + "|assign", exp.key, unit))


def variant_for(key: str, unit: str | None, *, expose: bool = False,
                sink=None, principal: str | None = None) -> str:
    """레지스트리 조회 + 할당 (+옵션 노출). 미등록 키·예외 시 control 폴백(요구사항 2.2·4.1).

    `expose=True`면 노출을 기록한다(exposure.record_exposure — analytics append).
    control(미노출/홀드아웃) 결과는 노출로 보지 않는다(실험 모집단만 기록).
    """
    exp = get(key)
    if exp is None:
        return "control"
    try:
        variant = assign(exp, unit)
    except Exception:
        return exp.control
    if expose and variant != exp.control:
        # 지연 import(순환 방지) — 노출은 비차단·실패 무시.
        try:
            from .exposure import record_exposure

            record_exposure(key, variant, unit or "", sink=sink, principal=principal)
        except Exception:
            pass
    return variant
