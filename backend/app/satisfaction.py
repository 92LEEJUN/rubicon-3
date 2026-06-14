"""만족도 수집(컴패니언·리텐션 §3, ADR-0066) — CSAT/NPS 인라인.

해결 확인(R25) 시점에 가벼운 만족도(CSAT 1~5 / NPS 0~10)를 **선택 응답**으로 수집한다. 미해결이면
재진단/핸드오프 힌트를 돌려준다(흐름 전환은 FE/BFF가 수행). 수집 결과·미해결·이탈 신호는 자기개선
엔진(ADR-0067)의 **입력 신호**로 emit한다(토글 off면 sink가 no-op = 회귀 불변).

**추가형(additive):** 신규 엔드포인트·신규 스토어로 기존 경로를 바꾸지 않는다. 수집은 동의(engagement
scope) 인지 — 신호 emit 시 `consent_ok`로 전달해 R28 가명화·동의 범위를 따른다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from .domain import User
from .improve.signals import Signal

# 신호 sink 시그니처(개선 엔진 COLLECTOR.collect와 호환). 주입 가능(테스트·디커플).
SignalSink = Callable[[Signal], bool]

_RELEVANT_SCOPES = {"personalization", "engagement"}  # 가명 집계 신호 emit 허용 scope


@dataclass
class SatisfactionRecord:
    user_id: str
    topic: str                 # 집계 차원(의도·기기군 등 — 개인 식별 아님)
    score: float
    kind: str                  # "csat"(1~5) | "nps"(0~10)
    resolved: bool
    comment: Optional[str] = None
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {"user_id": self.user_id, "topic": self.topic, "score": self.score,
                "kind": self.kind, "resolved": self.resolved, "comment": self.comment,
                "at": self.at.isoformat(),
                "next_action": None if self.resolved else "rediagnose"}


@dataclass
class SatisfactionService:
    """CSAT/NPS 수집 + 신호 emit. engagement 기록(중복·개인화 재사용), sink는 개선 엔진."""

    engagement: object                          # InMemoryEngagementRepository (duck-typed)
    signal_sink: Optional[SignalSink] = None    # 기본 None=emit 안 함(테스트·off)
    _records: list[SatisfactionRecord] = field(default_factory=list)

    def collect(self, user: User, topic: str, score: float, *, kind: str = "csat",
                resolved: bool = True, comment: Optional[str] = None,
                now: Optional[datetime] = None) -> SatisfactionRecord:
        """만족도 1건 수집(요구사항 3). 미해결이면 next_action='rediagnose'를 돌려준다."""
        rec = SatisfactionRecord(user_id=user.id, topic=topic, score=float(score), kind=kind,
                                 resolved=resolved, comment=comment,
                                 at=now or datetime.now(timezone.utc))
        self._records.append(rec)
        # Engagement 기록(중복 수집 억제·개인화 재사용, R29).
        try:
            self.engagement.record(user.id, f"sat:{topic}", "acknowledged")
        except Exception:
            pass
        # 개선 엔진 신호 emit — 동의 scope 인지(R28). sink가 토글 off면 no-op.
        if self.signal_sink is not None:
            consent_ok = bool(_RELEVANT_SCOPES & set(user.consent.scopes))
            self.signal_sink(Signal(kind="satisfaction", ref=topic, value=rec.score,
                                    at=rec.at, consent_ok=consent_ok))
            if not resolved:
                self.signal_sink(Signal(kind="handoff", ref=topic, value=1.0,
                                        at=rec.at, consent_ok=consent_ok))
        return rec

    def records(self, user_id: Optional[str] = None) -> list[SatisfactionRecord]:
        if user_id is None:
            return list(self._records)
        return [r for r in self._records if r.user_id == user_id]
