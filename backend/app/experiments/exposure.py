"""노출 로깅(exposure) — 기존 분석 택소노미에 `experiment_exposed` append(ADR-0064, 요구사항 5).

설계: 분석 이벤트는 owner append 규칙을 따른다(docs/analytics.md). BE에는 BFF 같은
영속 싱크가 없으므로 **duck-typed 싱크**(`.record(name, props, ts, principal)`)를 주입받고,
없으면 인프로세스 기본 싱크 + 구조화 로그 한 줄로 폴백한다. 토글 off면 no-op.

`(unit, key, variant)` 조합은 de-dup(인프로세스 셋) — 같은 노출 중복 억제(요구사항 5.2).
기존 분석 이벤트/시그니처는 변경하지 않는다(추가형, 요구사항 5.1).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional, Protocol

from .assignment import experiments_enabled

EXPOSURE_EVENT = "experiment_exposed"

_log = logging.getLogger("rubicon")

# 인프로세스 de-dup 셋(영속 아님). (unit, key, variant).
_seen: set[tuple[str, str, str]] = set()


class _Sink(Protocol):
    def record(self, name: str, props: Optional[dict] = ...,
               ts: Optional[float] = ..., principal: Optional[str] = ...) -> Any: ...


def reset_dedup() -> None:
    """테스트용 — de-dup 셋 초기화."""
    _seen.clear()


def record_exposure(key: str, variant: str, unit: str, *,
                    sink: Optional[_Sink] = None,
                    principal: Optional[str] = None,
                    dedup: bool = True) -> Optional[dict[str, Any]]:
    """`experiment_exposed`를 분석 싱크에 append. 토글 off·중복이면 no-op(None 반환).

    - 토글 off → None(요구사항 3.2: off면 노출 미발행).
    - `dedup`이고 (unit,key,variant) 이미 봤으면 → None(요구사항 5.2).
    - props에 `experiment`·`variant` 포함(요구사항 5.3).
    """
    if not experiments_enabled():
        return None
    seen_key = (unit, key, variant)
    if dedup and seen_key in _seen:
        return None
    if dedup:
        _seen.add(seen_key)

    props = {"experiment": key, "variant": variant, "unit": unit or None}
    ts = time.time()

    if sink is not None and hasattr(sink, "record"):
        # BFF AnalyticsSink 등 duck-typed 싱크에 append(기존 record 시그니처 사용).
        try:
            return sink.record(name=EXPOSURE_EVENT, props=props, ts=ts, principal=principal)
        except Exception:
            pass

    # 폴백: 구조화 로그 한 줄(관측성 로거 재사용 — 별도 파이프라인 신설 아님).
    _log.info("analytics_event", extra={
        "ctx_event": EXPOSURE_EVENT,
        "ctx_experiment": key,
        "ctx_variant": variant,
        "ctx_principal": principal,
    })
    return {"name": EXPOSURE_EVENT, "props": props, "ts": ts, "principal": principal}
