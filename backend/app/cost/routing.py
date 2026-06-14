"""모델 라우팅 정책 — 결정적 경량/상위 선택(ADR-0062, ADR-0034 위; 요구사항 2).

`MODEL_ROUTING` off면 기존 기본 모델(`llm.MODEL`)을 그대로 반환(회귀 불변). on이면 입력(복잡도·크기
힌트)만으로 **결정적**으로 선택한다(난수 없음): 단순/대량 → 경량, 복잡 → 상위.
"""
from __future__ import annotations

import os

LIGHT_MODEL = os.environ.get("LLM_LIGHT_MODEL", "gpt-4o-mini")
HEAVY_MODEL = os.environ.get("LLM_HEAVY_MODEL", "gpt-4o")

# 이 크기(근사 토큰)를 넘으면 비용 방어를 위해 복잡이라도 경량으로(대량=경량).
_BIG_THRESHOLD = int(os.environ.get("MODEL_ROUTING_BIG_TOKENS", "8000"))

_COMPLEX = frozenset({"complex", "heavy", "hard", "high"})


def _routing_on() -> bool:
    return (os.environ.get("MODEL_ROUTING") or "").strip().lower() in ("1", "true", "yes", "on")


def route_model(complexity: str = "simple", *, size_hint: int = 0) -> str:
    """복잡도·크기 힌트로 모델을 결정적으로 선택.

    - `MODEL_ROUTING` off → `llm.MODEL`(회귀 불변).
    - 복잡(`complex`/`heavy`/…) and 크기 < 임계 → 상위(HEAVY).
    - 단순 또는 대량(크기 ≥ 임계) → 경량(LIGHT).
    """
    if not _routing_on():
        from ..llm import MODEL

        return MODEL
    is_complex = (complexity or "").strip().lower() in _COMPLEX
    if is_complex and size_hint < _BIG_THRESHOLD:
        return HEAVY_MODEL
    return LIGHT_MODEL
