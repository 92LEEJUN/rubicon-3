"""선제 재관여 — 엄격 게이트 (컴패니언 spec §3, ADR-0042).

미해결 스레드(open-loop)를 트리거로 "먼저 말 걺"을 생성하되, 과잉 메시지(피로)를 막기 위해
**게이트 순서**로 거른다: ① 동의/opt-in → ② 빈도(R26 cooldown) → ③ 중복/가치 → ④ 묶음(R27).
신규 인프라 없이 기존 선제 파이프라인(§10)·Engagement 중복 게이트를 재사용한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .companion import CompanionService
from .domain import OpenLoop, ReEngagement, User
from .repositories import InMemoryEngagementRepository

# 재관여를 정당화하는 동의 scope(하나라도 있어야)
_RELEVANT_SCOPES = {"device_data", "personalization", "engagement"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ReEngagementService:
    companion: CompanionService
    engagement: InMemoryEngagementRepository
    cooldown_sec: int = 3600                       # R26 빈도 한도(윈도우당 1건)
    _last_sent: dict = field(default_factory=dict)

    # ── 게이트 ────────────────────────────────────────────────────────────────
    def _consent_ok(self, user: User) -> bool:
        return user.preferences.notify_opt_in and bool(_RELEVANT_SCOPES & set(user.consent.scopes))

    @staticmethod
    def _dedup_ref(ref: str) -> str:
        return f"reeng:{ref}"  # Engagement 중복 게이트와 namespace 분리

    def _message(self, loop: OpenLoop, also: int) -> str:
        base = {
            "issue": f"전에 보던 '{loop.label}' 문제, 이어서 도와드릴까요?",
            "order": f"'{loop.label}'은(는) 잘 진행되고 있나요?",
            "flow": f"'{loop.label}'을(를) 이어서 진행할까요?",
        }.get(loop.kind, f"'{loop.label}' 관련해 도와드릴까요?")
        return base + (f" (외 {also}건)" if also else "")

    # ── 후보 생성 ──────────────────────────────────────────────────────────────
    def candidate(self, user: User, *, now: Optional[datetime] = None) -> Optional[ReEngagement]:
        """게이트를 모두 통과한 재관여 1건(묶음). 통과 못 하면 None(억제)."""
        now = now or _utcnow()
        if not self._consent_ok(user):                                       # ① 동의/opt-in
            return None
        last = self._last_sent.get(user.id)
        if last and (now - last).total_seconds() < self.cooldown_sec:        # ② 빈도(R26)
            return None
        fresh = [l for l in self.companion.open_loops(user.id)
                 if not self.engagement.has_seen(user.id, self._dedup_ref(l.ref))]  # ③ 중복/가치
        if not fresh:
            return None
        top = fresh[0]                                                       # ④ 묶음(R27): 우선순위 top + 카운트
        return ReEngagement(primary_ref=top.ref, primary_label=top.label, kind=top.kind,
                            also_count=len(fresh) - 1, message=self._message(top, len(fresh) - 1))

    def mark_sent(self, user: User, *, now: Optional[datetime] = None) -> None:
        """전달 후 호출 — 빈도 윈도우 갱신 + 보낸 loop 중복 기록(다음엔 억제)."""
        now = now or _utcnow()
        self._last_sent[user.id] = now
        for loop in self.companion.open_loops(user.id):
            self.engagement.record(user.id, self._dedup_ref(loop.ref), "acknowledged")
