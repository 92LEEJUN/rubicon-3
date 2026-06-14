"""실험·롤아웃(Runtime A/B) — S8(ADR-0064).

결정적 sticky 할당 · 실험 레지스트리 · canary/홀드아웃 게이트 · 노출 로깅.
전부 토글 `EXPERIMENTS`(기본 off) 뒤 — off면 항상 control(회귀 불변).
"""
from __future__ import annotations

from .assignment import assign, experiments_enabled, variant_for
from .exposure import record_exposure
from .registry import (
    REGISTRY,
    Experiment,
    Variant,
    default_registry,
    get,
    register,
)

__all__ = [
    "Variant",
    "Experiment",
    "REGISTRY",
    "get",
    "register",
    "default_registry",
    "experiments_enabled",
    "assign",
    "variant_for",
    "record_exposure",
]
