"""신호 수집(요구사항 1, ADR-0067) — 개선 루프의 입력.

대화 결과(해결/핸드오프/이탈)·저신뢰 라우팅·clarify 빈발·템플릿 전환·만족도(ADR-0066)·실험(S8)
결과를 정규화된 `Signal`로 모은다. 토글 `SELF_IMPROVE` off면 **수집하지 않는다**(회귀 불변) —
수집 자체를 게이트해 off일 때 어떤 신호도 적재되지 않게 한다.

동의·가명화(R28): `consent_ok=False`인 신호는 적재하지 않는다(개인 식별자는 ref에 담지 않는다 —
의도·템플릿 kind·실험 키 등 **집계 차원**만 보관).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# 신호 종류 — 모두 집계 차원(개인 식별 아님).
SignalKind = (
    "resolution",            # 턴이 해결로 종료(value=1.0)
    "handoff",               # 핸드오프로 종료
    "abandon",               # 이탈(미해결·무응답)
    "low_confidence_route",  # 라우팅 신뢰도 임계 미만(ref=의도)
    "clarify_repeat",        # 같은 의도 clarify 반복(ref=의도)
    "template_conversion",   # 템플릿 CTA 전환(ref=template kind, value∈[0,1])
    "satisfaction",          # CSAT/NPS(ADR-0066; ref=주제, value=점수)
    "experiment_result",     # S8 실험 결과(ref=실험 키)
)


def self_improve_enabled() -> bool:
    """자기개선 토글 — 매 호출 평가(런타임 env 반영), 기본 off=회귀 불변."""
    return os.getenv("SELF_IMPROVE", "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Signal:
    """정규화 신호(불변). ref는 **집계 차원**(의도·템플릿 kind·실험 키 등)만 — 개인 식별 금지."""

    kind: str
    ref: str
    value: float = 1.0
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consent_ok: bool = True
    meta: dict = field(default_factory=dict)


class SignalCollector:
    """신호 sink(요구사항 1). 토글 off면 no-op, 비동의 신호는 드롭(R28)."""

    def __init__(self) -> None:
        self._signals: list[Signal] = []

    def collect(self, signal: Signal) -> bool:
        """신호 적재 — 적재됐으면 True. 토글 off·비동의면 False(드롭)."""
        if not self_improve_enabled():
            return False
        if not signal.consent_ok:
            return False
        self._signals.append(signal)
        return True

    def window(self, kind: Optional[str] = None) -> list[Signal]:
        """수집된 신호(선택적으로 kind 필터)."""
        if kind is None:
            return list(self._signals)
        return [s for s in self._signals if s.kind == kind]

    def clear(self) -> None:
        self._signals.clear()


# 프로세스 단일 sink — 컴패니언(만족도) 등 생산자가 공유한다.
COLLECTOR = SignalCollector()
