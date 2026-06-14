"""신뢰성/회복력(Resilience) 유틸 — Well-Architected 신뢰성 · 12-Factor #7 Disposability(ADR-0058).

5개 결정적·단위 테스트 가능 유틸을 단일 모듈에 응집한다(새 의존성 없이 stdlib·asyncio만):
  ① CircuitBreaker     — closed/open/half-open 상태기계(임계·복구). 빠른 실패.
  ② run_stage          — 단계별 타임아웃 + 부분 폴백(ADR-0018 개념 되살림).
  ③ ShutdownManager    — graceful 종료 훅(LIFO·best-effort·sync/async).
  ④ DegradedMode       — 기능별 강등/부분 폴백 플래그.
  ⑤ retry / aretry     — 공용 지수 백오프+지터(llm.py 알고리즘 일반화, 중복 신설 없이).

설계 원칙: 시계·슬립·지터를 **주입** 가능하게 만들어 실시간 대기 없이 결정적으로 검증한다.
배선은 `wiring.register_shutdown`으로 **등록만** 하고(ADR-0056 시임), 토글 `RESILIENCE_ENABLED`
(기본 off)일 때만 등록한다 → off면 wiring에 아무것도 안 붙어 회귀 불변. 모듈 import 자체는 부수효과
없음(유틸은 서비스가 명시적으로 인스턴스화·호출).
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
import time
from enum import Enum
from typing import Any, Awaitable, Callable, Iterable

__all__ = [
    "CircuitState",
    "CircuitOpenError",
    "CircuitBreaker",
    "StageTimeout",
    "run_stage",
    "ShutdownManager",
    "SHUTDOWN",
    "on_shutdown",
    "DegradedMode",
    "DEGRADED",
    "retry",
    "aretry",
]

_UNSET: Any = object()


def _flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# ── ① 서킷브레이커 ────────────────────────────────────────────────────────────
class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """서킷이 open이라 호출이 즉시 거부됨(빠른 실패)."""


class CircuitBreaker:
    """연속 실패 임계·복구 시간 기반 상태기계(요구사항 1).

    - closed: 정상 통과. 성공 시 실패 카운터 리셋, 실패 누적이 임계 도달 시 open.
    - open: 즉시 거부. 단, recovery_timeout 경과 시 half-open으로 전환해 시험 1회 허용.
    - half-open: 시험 호출 1회. 성공→closed(리셋), 실패→open(타이머 재시작).

    시계(`clock`, 기본 time.monotonic)를 주입해 시간 경과를 결정적으로 검증한다.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        """현재 상태 — open이고 복구 시간이 지났으면 half-open으로 전이해 반영."""
        if self._state is CircuitState.OPEN and self._recovery_elapsed():
            self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failures

    def _recovery_elapsed(self) -> bool:
        return self._opened_at is not None and (self._clock() - self._opened_at) >= self.recovery_timeout

    def allow(self) -> bool:
        """이번 호출을 허용할지 — closed/half-open이면 True, open이면 False(복구 경과 시 half-open)."""
        return self.state is not CircuitState.OPEN

    def record_success(self) -> None:
        """성공 기록 — half-open이면 closed 복귀, closed면 실패 카운터 리셋."""
        self._failures = 0
        self._opened_at = None
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """실패 기록 — half-open이면 즉시 open, closed면 누적이 임계 도달 시 open."""
        if self._state is CircuitState.HALF_OPEN:
            self._trip()
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """게이트를 통과하면 동기 fn 실행, open이면 CircuitOpenError. 성공/실패를 기록한다."""
        if not self.allow():
            raise CircuitOpenError("circuit is open")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result

    async def acall(self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        """게이트를 통과하면 비동기 fn await, open이면 CircuitOpenError. 성공/실패를 기록한다."""
        if not self.allow():
            raise CircuitOpenError("circuit is open")
        try:
            result = await fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result


# ── ② 단계별 타임아웃 + 부분 폴백(ADR-0018 되살림) ──────────────────────────────
class StageTimeout(asyncio.TimeoutError):
    """단계가 주어진 시한을 초과함(asyncio.TimeoutError 하위 — 기존 핸들러 호환)."""


async def run_stage(
    coro_factory: Callable[[], Awaitable[Any]],
    timeout: float | None,
    *,
    fallback: Any = _UNSET,
) -> Any:
    """단계 코루틴을 시한 안에 실행(요구사항 2).

    - `coro_factory`: 인자 없는 호출로 새 코루틴을 만드는 팩토리(타임아웃 시 취소 위해 1회성 회피).
    - `timeout`이 None·0 이하이면 시한 없이 그대로 await(회귀 불변).
    - 시한 초과 시 코루틴을 취소하고 `fallback`이 주어지면 그 값을, 아니면 `StageTimeout`을 낸다.
    """
    coro = coro_factory()
    if timeout is None or timeout <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        if fallback is not _UNSET:
            return fallback
        raise StageTimeout(f"stage exceeded {timeout}s") from None


# ── ③ graceful shutdown 훅 ────────────────────────────────────────────────────
class ShutdownManager:
    """등록된 정리 콜백을 종료 시 역순(LIFO)으로 best-effort 실행한다(요구사항 3).

    동기·코루틴 콜백을 모두 지원. 한 콜백이 예외를 던져도 멈추지 않고 나머지를 계속 실행하며,
    예외는 수집해 stderr로 남긴다(무중단 종료 — Disposability).
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable[[], Any]] = []

    def register(self, fn: Callable[[], Any]) -> Callable[[], Any]:
        """정리 콜백 등록(데코레이터로도 사용 가능). 인자 없는 callable이어야 한다."""
        self._callbacks.append(fn)
        return fn

    def clear(self) -> None:
        self._callbacks.clear()

    def __len__(self) -> int:
        return len(self._callbacks)

    def _drain(self) -> list[Callable[[], Any]]:
        cbs = list(reversed(self._callbacks))  # LIFO
        self._callbacks.clear()
        return cbs

    def run(self) -> list[Exception]:
        """동기 종료 — 코루틴 콜백은 새 이벤트 루프로 구동. 수집된 예외 리스트 반환."""
        errors: list[Exception] = []
        for fn in self._drain():
            try:
                res = fn()
                if asyncio.iscoroutine(res):
                    asyncio.run(res)
            except Exception as exc:  # best-effort: 다음 콜백 계속
                errors.append(exc)
                print(f"[shutdown] callback error: {exc!r}", file=sys.stderr)
        return errors

    async def arun(self) -> list[Exception]:
        """비동기 종료 — 코루틴 콜백을 현재 루프에서 await. 수집된 예외 리스트 반환."""
        errors: list[Exception] = []
        for fn in self._drain():
            try:
                res = fn()
                if asyncio.iscoroutine(res):
                    await res
            except Exception as exc:  # best-effort: 다음 콜백 계속
                errors.append(exc)
                print(f"[shutdown] callback error: {exc!r}", file=sys.stderr)
        return errors


SHUTDOWN = ShutdownManager()


def on_shutdown(fn: Callable[[], Any]) -> Callable[[], Any]:
    """전역 ShutdownManager에 정리 콜백 등록(서비스 코드용 단축)."""
    return SHUTDOWN.register(fn)


# ── ④ degraded / 부분 폴백 모드 플래그 ─────────────────────────────────────────
class DegradedMode:
    """기능별 강등 플래그 집합(요구사항 4) — 부분 장애에서 핵심만 제공.

    기본은 비어 있음(정상). env(콤마구분)로 초기 강등 집합을 줄 수 있다. 기본 off=회귀 불변.
    """

    def __init__(self, initial: Iterable[str] | None = None) -> None:
        self._features: set[str] = {f.strip() for f in (initial or ()) if f.strip()}

    @classmethod
    def from_env(cls, name: str = "RESILIENCE_DEGRADED") -> "DegradedMode":
        raw = os.getenv(name, "")
        return cls(raw.split(",") if raw else ())

    def is_degraded(self, feature: str) -> bool:
        return feature in self._features

    def mark(self, feature: str) -> None:
        self._features.add(feature)

    def clear(self, feature: str | None = None) -> None:
        """특정 기능 강등 해제, 인자 없으면 전체 해제(정상 복귀)."""
        if feature is None:
            self._features.clear()
        else:
            self._features.discard(feature)

    def active(self) -> frozenset[str]:
        return frozenset(self._features)

    @property
    def any_degraded(self) -> bool:
        return bool(self._features)


DEGRADED = DegradedMode.from_env()


# ── ⑤ 공용 재시도/백오프(llm.py 알고리즘 일반화) ───────────────────────────────
_DEFAULT_DELAYS = (0.5, 1.0, 2.0, 4.0)  # llm.py와 동일한 지수 백오프 기본


def _backoff_delay(
    attempt: int, base_delay: float, delays: tuple[float, ...] | None, jitter: Callable[[], float]
) -> float:
    if delays is not None:
        d = delays[min(attempt, len(delays) - 1)]
    else:
        d = base_delay * (2 ** attempt)
    return d * (1 + jitter() * 0.3)  # +지터(llm.py와 동일 비율)


def retry(
    fn: Callable[..., Any],
    *args: Any,
    attempts: int = 4,
    base_delay: float = 0.5,
    delays: tuple[float, ...] | None = None,
    transient: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
    **kwargs: Any,
) -> Any:
    """동기 지수 백오프+지터 재시도(요구사항 5).

    transient 예외에 한해 재시도(그 외 즉시 전파). 모두 실패하면 마지막 예외를 재던진다.
    sleep·jitter를 주입해 실대기 없이 결정적으로 검증할 수 있다.
    """
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn(*args, **kwargs)
        except transient as exc:
            last = exc
            if attempt == attempts - 1:
                raise
            sleep(_backoff_delay(attempt, base_delay, delays, jitter))
    raise last  # pragma: no cover


async def aretry(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    attempts: int = 4,
    base_delay: float = 0.5,
    delays: tuple[float, ...] | None = None,
    transient: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    jitter: Callable[[], float] = random.random,
    **kwargs: Any,
) -> Any:
    """비동기 지수 백오프+지터 재시도(요구사항 5) — retry의 async 변형."""
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return await fn(*args, **kwargs)
        except transient as exc:
            last = exc
            if attempt == attempts - 1:
                raise
            await sleep(_backoff_delay(attempt, base_delay, delays, jitter))
    raise last  # pragma: no cover


# ── 배선(ADR-0056 시임) — 토글 on일 때만 graceful shutdown 훅 등록 ───────────────
def _register_wiring() -> None:
    """RESILIENCE_ENABLED가 켜져 있으면 전역 SHUTDOWN을 앱 종료 훅으로 등록한다.

    off(기본)면 등록하지 않아 wiring/앱 동작이 불변(회귀 불변). 앱 팩토리는 직접 편집하지 않고
    wiring.register_shutdown으로 등록만 한다(병렬 충돌 회피).
    """
    if not _flag("RESILIENCE_ENABLED", False):
        return
    try:
        from .platform import wiring
    except Exception:  # 배선 모듈 부재(테스트 등) — 조용히 스킵
        return

    @wiring.register_shutdown(priority=900)  # 다른 훅 뒤에서 정리(높은 priority=나중)
    async def _resilience_shutdown(_app: Any) -> None:
        await SHUTDOWN.arun()


_register_wiring()
