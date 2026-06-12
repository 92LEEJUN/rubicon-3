"""미해결 스레드(OpenLoop) Repository — user 단위(컴패니언 spec 요구 2·4).

`ref`로 upsert(중복 방지·멱등). 열린 loop는 우선순위·최근순으로 정렬해 resume에 노출.
MVP=인메모리 → 실 전환 시 DB(영속).
"""
from __future__ import annotations

from ..domain import OpenLoop


class InMemoryOpenLoopRepository:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, OpenLoop]] = {}  # user_id -> ref -> loop

    def upsert(self, user_id: str, loop: OpenLoop) -> None:
        self._store.setdefault(user_id, {})[loop.ref] = loop

    def get(self, user_id: str, ref: str) -> OpenLoop | None:
        return self._store.get(user_id, {}).get(ref)

    def list_open(self, user_id: str) -> list[OpenLoop]:
        loops = [l for l in self._store.get(user_id, {}).values() if l.status == "open"]
        return sorted(loops, key=lambda l: (l.priority, l.last_touch), reverse=True)  # 우선순위·최근순

    def set_status(self, user_id: str, ref: str, status: str) -> OpenLoop | None:
        loop = self.get(user_id, ref)
        if loop is None:
            return None
        updated = loop.model_copy(update={"status": status})
        self._store[user_id][ref] = updated
        return updated

    def clear(self, user_id: str) -> None:
        self._store.pop(user_id, None)
