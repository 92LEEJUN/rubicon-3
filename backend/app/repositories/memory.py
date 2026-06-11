"""인메모리 Repository 구현(MVP). 실 전환 시 DB 백엔드로 교체(인터페이스 불변)."""
from __future__ import annotations

from datetime import datetime, timezone

from ..domain import EngagementRecord, EngagementState


class InMemoryEngagementRepository:
    """Engagement(R29) — (user_id, ref) 단위로 열람/무시/관심 상태를 보관.

    중복 알림 억제(J2·J3)·관심 반영(추천)에 쓰인다. 같은 키는 최신 상태로 덮어쓴다.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], EngagementRecord] = {}

    def record(self, user_id: str, ref: str, state: EngagementState) -> EngagementRecord:
        rec = EngagementRecord(user_id=user_id, ref=ref, state=state,
                               updated_at=datetime.now(timezone.utc))
        self._store[(user_id, ref)] = rec
        return rec

    def get(self, user_id: str, ref: str) -> EngagementRecord | None:
        return self._store.get((user_id, ref))

    def list(self, user_id: str) -> list[EngagementRecord]:
        return [r for (u, _), r in self._store.items() if u == user_id]

    def has_seen(self, user_id: str, ref: str) -> bool:
        """이미 열람/확인/무시했는지 — 중복 노출 억제용."""
        rec = self._store.get((user_id, ref))
        return rec is not None and rec.state in ("viewed", "acknowledged", "dismissed")
