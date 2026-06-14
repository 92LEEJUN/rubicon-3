"""세션 상태 외부화 Port — Stateless 프로세스(ADR-0059, 12F#12).

현재 세션/워킹 상태는 인메모리(`conversation_store.py` 등)에 있어 프로세스가 상태를 갖는다. 무상태화
(수평 확장·재시작 보존)를 위해 외부 저장으로 빼낼 수 있는 `SessionStatePort`(Protocol)를 둔다.
실 전환 시 Redis/DB 어댑터로 교체한다. 기본은 인메모리(`InMemorySessionStateStore`) = 기존 동작.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional, Protocol, runtime_checkable


@runtime_checkable
class SessionStatePort(Protocol):
    """세션 상태 백킹서비스 계약 — load/save/delete/touch."""

    def load(self, key: str) -> Optional[Any]:
        """없거나 만료면 None."""
        ...

    def save(self, key: str, state: Any, ttl: Optional[float] = None) -> None: ...

    def delete(self, key: str) -> None: ...

    def touch(self, key: str, ttl: float) -> None:
        """만료시각 연장(슬라이딩). 없는 키는 no-op(멱등)."""
        ...


class InMemorySessionStateStore:
    """`SessionStatePort` 인메모리 구현 — 기본값(기존 인메모리 동작).

    `shared=True`면 클래스 레벨 스토어를 공유해, **새 인스턴스가 같은 키를 복원**하는 외부 저장
    의미(Redis 자리표시)를 Mock으로 표현한다. 기본 `shared=False`는 인스턴스 격리(기존 동작).
    """

    _SHARED: dict[str, tuple[Any, Optional[float]]] = {}

    def __init__(self, *, shared: bool = False, now_fn: Callable[[], float] = time.monotonic) -> None:
        self._store = self._SHARED if shared else {}
        self._now = now_fn

    def load(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        state, expires_at = entry
        if expires_at is not None and self._now() >= expires_at:
            self._store.pop(key, None)
            return None
        return state

    def save(self, key: str, state: Any, ttl: Optional[float] = None) -> None:
        expires_at = (self._now() + ttl) if ttl is not None else None
        self._store[key] = (state, expires_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def touch(self, key: str, ttl: float) -> None:
        entry = self._store.get(key)
        if entry is None:
            return
        state, _ = entry
        self._store[key] = (state, self._now() + ttl)
