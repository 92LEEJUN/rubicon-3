"""실험 정의 레지스트리(ADR-0064, 요구사항 2).

실험을 키·variant(가중치)·control·rollout/holdout·salt로 선언해 단일 인메모리 레지스트리에
보관한다. 미등록 키 조회는 None(호출측이 control 폴백) — 예외를 던지지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Variant:
    """실험 variant — 이름 + 상대 가중치(레지스트리 합으로 정규화)."""

    name: str
    weight: float = 1.0


@dataclass(frozen=True)
class Experiment:
    """실험 정의(불변).

    - `variants`: 분배 대상 variant들(control 포함 가능).
    - `control`: 폴백/홀드아웃/롤아웃-외 기본 variant 이름(요구사항 2.3).
    - `rollout`: [0,1] 실험 대상 트래픽 비율(canary). rollout 밖 → control.
    - `holdout`: [0,1] 실험에서 제외(control 고정)되는 비율.
    - `salt`: 키별 독립 버킷을 위한 해시 솔트.
    """

    key: str
    variants: tuple[Variant, ...]
    control: str
    rollout: float = 1.0
    holdout: float = 0.0
    salt: str = ""

    def variant_names(self) -> tuple[str, ...]:
        return tuple(v.name for v in self.variants)


# 인메모리 단일 레지스트리(프로세스 수명). 영속 아님 — 데모/실험 토대.
REGISTRY: dict[str, Experiment] = {}


def register(exp: Experiment) -> Experiment:
    """실험 등록(키로 덮어쓰기). 반환은 등록된 실험."""
    REGISTRY[exp.key] = exp
    return exp


def get(key: str) -> Experiment | None:
    """키로 조회 — 미등록이면 None(호출측이 control 폴백, 요구사항 2.2)."""
    return REGISTRY.get(key)


def default_registry() -> dict[str, Experiment]:
    """예시 실험을 시드한다(테스트·데모 가시성). 호출 시 REGISTRY에 등록.

    토글 off면 어차피 control이라 동작 영향 없음(회귀 불변).
    """
    register(
        Experiment(
            key="bridge_cta_copy",
            variants=(Variant("control", 1.0), Variant("treatment", 1.0)),
            control="control",
            rollout=1.0,
            holdout=0.0,
            salt="bridge_cta_copy",
        )
    )
    register(
        Experiment(
            key="home_layout",
            variants=(Variant("control", 0.5), Variant("compact", 0.25), Variant("rich", 0.25)),
            control="control",
            rollout=0.5,   # canary: 절반에만 노출
            holdout=0.1,   # 10% 홀드아웃
            salt="home_layout",
        )
    )
    return REGISTRY
