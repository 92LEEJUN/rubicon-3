"""대화 워킹 스토어 — 라이브 메시지 + 마지막 활동시각 (user 단위).

컴팩션 대상 메시지(verbatim)와 `last_active`를 보관한다. 컴팩션된 요약/사실은
`ConversationMemory`(영속)로 따로 간다. MVP=인메모리 → 실 전환 시 Redis(TTL)/DB.
"""
from __future__ import annotations

from datetime import datetime, timezone


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._msgs: dict[str, list[dict]] = {}
        self._last_active: dict[str, datetime] = {}

    def messages(self, user_id: str) -> list[dict]:
        return self._msgs.get(user_id, [])

    def append(self, user_id: str, turn: dict, *, now: datetime | None = None) -> None:
        self._msgs.setdefault(user_id, []).append(turn)
        self._last_active[user_id] = now or datetime.now(timezone.utc)

    def last_active(self, user_id: str) -> datetime | None:
        return self._last_active.get(user_id)

    def clear(self, user_id: str) -> None:
        """삭제 cascade(R19) / '새로 시작'."""
        self._msgs.pop(user_id, None)
        self._last_active.pop(user_id, None)
