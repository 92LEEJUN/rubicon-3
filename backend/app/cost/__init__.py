"""비용·라우팅·예산 — S6 비용·캐싱(ADR-0062, Well-Architected 비용 최적화).

전부 토글 뒤(`COST_TRACKING`·`MODEL_ROUTING`·기본 off) — off면 무동작(회귀 불변).
- `accounting`: stdlib 근사 토큰·모델별 비용·메트릭 기록(`maybe_record`).
- `routing`: 결정적 모델 라우팅(`route_model`).
- `budget`: 일/세션 예산 가드(`BudgetGuard`·`default_guard`).
"""
from .accounting import (
    CostRecord,
    ModelPrice,
    estimate_cost,
    estimate_messages_tokens,
    estimate_tokens,
    maybe_record,
)
from .budget import BudgetGuard, default_guard
from .routing import HEAVY_MODEL, LIGHT_MODEL, route_model

__all__ = [
    "CostRecord",
    "ModelPrice",
    "estimate_cost",
    "estimate_messages_tokens",
    "estimate_tokens",
    "maybe_record",
    "BudgetGuard",
    "default_guard",
    "HEAVY_MODEL",
    "LIGHT_MODEL",
    "route_model",
]
