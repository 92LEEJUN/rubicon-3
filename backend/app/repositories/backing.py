"""백킹서비스 선택 팩토리 — 환경/토글 기반 DI(ADR-0059·ADR-0056, 12F#8·#12).

각 백킹서비스(DB·캐시·큐·세션상태)를 env 토글로 선택한다. **미지정이면 기존 동작 기본**(캐시 비활성·
세션 인메모리·큐 인프로세스 Mock·DB sqlite Mock) — 회귀 불변(스트랭글러). `config.get_settings()`로
환경 parity를 맞춘다(현재는 토글 자체가 env이므로 settings는 환경 해석/일관성 용도로 참조).

토글:
- `DB_BACKEND`      ∈ {mock} (기본 mock=sqlite). 실 postgres는 후속.
- `CACHE_BACKEND`   ∈ {noop, memory|mock} (기본 noop=비활성).
- `QUEUE_BACKEND`   ∈ {mock} (기본 mock).
- `SESSION_BACKEND` ∈ {memory} (기본 memory=인메모리). 외부(redis)는 후속.
"""
from __future__ import annotations

import os

from ..adapters.cache import CachePort, MockCache, NoopCache
from ..adapters.queue import MockQueue, QueuePort
from ..config import get_settings
from .db import DatabasePort, MockDatabase
from .session_state import InMemorySessionStateStore, SessionStatePort


def _toggle(name: str, default: str) -> str:
    return (os.environ.get(name) or default).strip().lower()


def select_database() -> DatabasePort:
    """DB 백엔드 선택 — 기본 mock(sqlite, :memory:). 실 postgres는 후속 전환."""
    get_settings()  # 환경 해석 일관성(parity) — 토글은 env가 직접.
    backend = _toggle("DB_BACKEND", "mock")
    db_path = os.environ.get("DB_PATH", ":memory:")
    # 현재는 mock만 — 미지의 값도 안전 기본(mock)으로 폴백(회귀 불변).
    _ = backend
    return MockDatabase(db_path)


def select_cache() -> CachePort:
    """캐시 백엔드 선택 — 기본 noop(비활성=기존 동작). memory/mock이면 인메모리 TTL 캐시."""
    backend = _toggle("CACHE_BACKEND", "noop")
    if backend in ("memory", "mock"):
        return MockCache()
    return NoopCache()


def select_queue() -> QueuePort:
    """큐 백엔드 선택 — 기본 mock(인프로세스 FIFO + 재시도/데드레터)."""
    _ = _toggle("QUEUE_BACKEND", "mock")
    return MockQueue()


def select_session_state() -> SessionStatePort:
    """세션 상태 백엔드 선택 — 기본 memory(인메모리=기존 동작).

    `shared`(외부 저장 의미·복원)는 `SESSION_SHARED=1`로 켤 수 있다(Redis 자리표시·테스트용).
    """
    _ = _toggle("SESSION_BACKEND", "memory")
    shared = (os.environ.get("SESSION_SHARED") or "").strip().lower() in ("1", "true", "yes", "on")
    return InMemorySessionStateStore(shared=shared)
