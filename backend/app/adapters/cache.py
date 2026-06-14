"""캐시 인터페이스(Redis 지향) + Mock 구현 — S3 백킹서비스(ADR-0059, 12F#8).

`CachePort`(Protocol)는 get/set(ttl)/delete/clear 시그니처를 고정한다(ADR-0020 경계). 실 전환 시
동일 Protocol을 만족하는 Redis 어댑터로 교체한다. 기본은 `NoopCache`(비활성) — 캐시 미도입 시
기존 동작과 동일(회귀 불변). S6(비용·캐싱)가 이 Port 위에 얹는다.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional, Protocol, runtime_checkable


@runtime_checkable
class CachePort(Protocol):
    """캐시 백킹서비스 계약."""

    def get(self, key: str) -> Optional[Any]:
        """미스/만료 시 None."""
        ...

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """ttl(초) 지정 시 만료. None이면 무기한."""
        ...

    def delete(self, key: str) -> None: ...

    def clear(self) -> None: ...


class MockCache:
    """`CachePort` Mock(dict + per-key 만료). Redis 어댑터 자리표시.

    시계는 주입 가능(`now_fn`)해 TTL 만료를 결정적으로 테스트할 수 있다.
    """

    def __init__(self, now_fn: Callable[[], float] = time.monotonic) -> None:
        self._store: dict[str, tuple[Any, Optional[float]]] = {}  # key -> (value, expires_at|None)
        self._now = now_fn

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and self._now() >= expires_at:
            self._store.pop(key, None)  # 만료 = 미스(지연 삭제)
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expires_at = (self._now() + ttl) if ttl is not None else None
        self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


class NoopCache:
    """캐시 비활성 — 항상 미스. 기본값(캐시 미도입 = 기존 동작)."""

    def get(self, key: str) -> Optional[Any]:
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        return None

    def delete(self, key: str) -> None:
        return None

    def clear(self) -> None:
        return None
