"""대화 메모리 Repository — **user 단위** 영속(ADR-0040, 교차기기 연속).

MVP=인메모리 → 실 전환 시 Postgres/Redis(영속). 세션이 아니라 user 키라
다른 기기/세션에서도 같은 기억으로 이어진다(컴패니언 spec 요구 4).
"""
from __future__ import annotations

from ..domain import ConversationMemory


class InMemoryConversationMemoryRepository:
    def __init__(self) -> None:
        self._store: dict[str, ConversationMemory] = {}

    def get(self, user_id: str) -> ConversationMemory:
        """없으면 빈 메모리(첫 방문 = 깨끗한 시작)."""
        return self._store.get(user_id) or ConversationMemory()

    def save(self, user_id: str, memory: ConversationMemory) -> None:
        self._store[user_id] = memory

    def delete(self, user_id: str) -> None:
        """삭제 요청 cascade(R19)."""
        self._store.pop(user_id, None)
