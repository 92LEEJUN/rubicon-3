"""신뢰성/회복력 유틸(ADR-0058) — 결정적 단위 검증(실시간 대기·네트워크 없음)."""
import asyncio

import pytest

from app import resilience as R


# ── ① 서킷브레이커(요구사항 1) ────────────────────────────────────────────────
class _Clock:
    """주입 가능한 가짜 단조 시계 — 결정적 시간 경과 제어."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_circuit_opens_after_threshold():
    cb = R.CircuitBreaker(failure_threshold=3, recovery_timeout=10.0, clock=_Clock())
    assert cb.state is R.CircuitState.CLOSED and cb.allow()
    for _ in range(3):
        cb.record_failure()
    assert cb.state is R.CircuitState.OPEN
    assert not cb.allow()


def test_circuit_call_rejects_when_open():
    cb = R.CircuitBreaker(failure_threshold=1, recovery_timeout=10.0, clock=_Clock())
    cb.record_failure()  # open
    with pytest.raises(R.CircuitOpenError):
        cb.call(lambda: 42)


def test_circuit_half_open_after_recovery_then_close_on_success():
    clk = _Clock()
    cb = R.CircuitBreaker(failure_threshold=1, recovery_timeout=10.0, clock=clk)
    cb.record_failure()  # open at t=0
    assert cb.state is R.CircuitState.OPEN
    clk.advance(10.0)  # recovery elapsed
    assert cb.state is R.CircuitState.HALF_OPEN and cb.allow()
    cb.record_success()  # test call ok → closed
    assert cb.state is R.CircuitState.CLOSED and cb.failure_count == 0


def test_circuit_half_open_failure_reopens():
    clk = _Clock()
    cb = R.CircuitBreaker(failure_threshold=1, recovery_timeout=5.0, clock=clk)
    cb.record_failure()
    clk.advance(5.0)
    assert cb.state is R.CircuitState.HALF_OPEN
    cb.record_failure()  # test call fails → open again
    assert cb.state is R.CircuitState.OPEN
    assert cb._opened_at == clk.t  # timer restarted


def test_circuit_success_resets_failures_in_closed():
    cb = R.CircuitBreaker(failure_threshold=3, clock=_Clock())
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.failure_count == 0 and cb.state is R.CircuitState.CLOSED


def test_circuit_call_records_failure_and_reraises():
    cb = R.CircuitBreaker(failure_threshold=2, clock=_Clock())

    def boom():
        raise ValueError("x")

    with pytest.raises(ValueError):
        cb.call(boom)
    assert cb.failure_count == 1


def test_circuit_acall(event_loop_policy=None):
    cb = R.CircuitBreaker(failure_threshold=1, recovery_timeout=1.0, clock=_Clock())

    async def ok():
        return "ok"

    async def bad():
        raise RuntimeError("nope")

    assert asyncio.run(cb.acall(ok)) == "ok"
    with pytest.raises(RuntimeError):
        asyncio.run(cb.acall(bad))
    assert cb.state is R.CircuitState.OPEN
    with pytest.raises(R.CircuitOpenError):
        asyncio.run(cb.acall(ok))


# ── ② 단계 타임아웃 + 부분 폴백(요구사항 2) ────────────────────────────────────
def test_run_stage_returns_value_within_timeout():
    async def fast():
        return 7

    assert asyncio.run(R.run_stage(lambda: fast(), 1.0)) == 7


def test_run_stage_raises_stage_timeout():
    async def slow():
        await asyncio.sleep(1.0)

    with pytest.raises(R.StageTimeout):
        asyncio.run(R.run_stage(lambda: slow(), 0.01))


def test_run_stage_uses_fallback_on_timeout():
    async def slow():
        await asyncio.sleep(1.0)
        return "real"

    assert asyncio.run(R.run_stage(lambda: slow(), 0.01, fallback="fb")) == "fb"


def test_run_stage_none_timeout_bypasses():
    async def work():
        return "done"

    assert asyncio.run(R.run_stage(lambda: work(), None)) == "done"
    assert asyncio.run(R.run_stage(lambda: work(), 0)) == "done"


def test_stage_timeout_is_asyncio_timeout_subclass():
    assert issubclass(R.StageTimeout, asyncio.TimeoutError)


# ── ③ graceful shutdown(요구사항 3) ───────────────────────────────────────────
def test_shutdown_runs_lifo():
    mgr = R.ShutdownManager()
    order = []
    mgr.register(lambda: order.append("a"))
    mgr.register(lambda: order.append("b"))
    mgr.register(lambda: order.append("c"))
    errs = mgr.run()
    assert order == ["c", "b", "a"] and errs == []
    assert len(mgr) == 0  # drained


def test_shutdown_continues_on_error():
    mgr = R.ShutdownManager()
    seen = []

    def boom():
        raise RuntimeError("fail")

    mgr.register(lambda: seen.append(1))
    mgr.register(boom)
    mgr.register(lambda: seen.append(2))
    errs = mgr.run()  # order: append2, boom, append1
    assert seen == [2, 1]  # both non-failing ran
    assert len(errs) == 1 and isinstance(errs[0], RuntimeError)


def test_shutdown_supports_coroutines():
    mgr = R.ShutdownManager()
    seen = []

    async def acb():
        seen.append("async")

    def scb():
        seen.append("sync")

    mgr.register(scb)
    mgr.register(acb)
    asyncio.run(mgr.arun())
    assert seen == ["async", "sync"]  # LIFO


def test_global_on_shutdown_registers():
    R.SHUTDOWN.clear()
    flag = []
    R.on_shutdown(lambda: flag.append(1))
    assert len(R.SHUTDOWN) == 1
    R.SHUTDOWN.run()
    assert flag == [1]
    R.SHUTDOWN.clear()


# ── ④ degraded 모드(요구사항 4) ───────────────────────────────────────────────
def test_degraded_default_off():
    dm = R.DegradedMode()
    assert not dm.any_degraded and not dm.is_degraded("anything")


def test_degraded_mark_and_clear():
    dm = R.DegradedMode()
    dm.mark("recommend")
    assert dm.is_degraded("recommend") and dm.any_degraded
    assert dm.active() == frozenset({"recommend"})
    dm.clear("recommend")
    assert not dm.is_degraded("recommend")


def test_degraded_clear_all():
    dm = R.DegradedMode(["a", "b"])
    dm.clear()
    assert not dm.any_degraded


def test_degraded_from_env(monkeypatch):
    monkeypatch.setenv("RESILIENCE_DEGRADED", "rag, vision ,")
    dm = R.DegradedMode.from_env()
    assert dm.active() == frozenset({"rag", "vision"})


def test_degraded_from_env_empty(monkeypatch):
    monkeypatch.delenv("RESILIENCE_DEGRADED", raising=False)
    assert not R.DegradedMode.from_env().any_degraded


# ── ⑤ 공용 재시도/백오프(요구사항 5) ──────────────────────────────────────────
def test_retry_succeeds_after_transient():
    calls = {"n": 0}
    slept = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("transient")
        return "ok"

    out = R.retry(flaky, attempts=4, transient=(ValueError,), sleep=slept.append, jitter=lambda: 0.0)
    assert out == "ok" and calls["n"] == 3
    assert len(slept) == 2  # slept before retries 2,3


def test_retry_reraises_last_after_exhaustion():
    def always():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        R.retry(always, attempts=3, transient=(ValueError,), sleep=lambda _: None, jitter=lambda: 0.0)


def test_retry_does_not_retry_non_transient():
    calls = {"n": 0}

    def bad():
        calls["n"] += 1
        raise KeyError("not transient")

    with pytest.raises(KeyError):
        R.retry(bad, attempts=5, transient=(ValueError,), sleep=lambda _: None)
    assert calls["n"] == 1  # no retry


def test_retry_backoff_grows():
    slept = []

    def always():
        raise ValueError("x")

    with pytest.raises(ValueError):
        R.retry(
            always,
            attempts=4,
            delays=(0.5, 1.0, 2.0, 4.0),
            transient=(ValueError,),
            sleep=slept.append,
            jitter=lambda: 0.0,
        )
    assert slept == [0.5, 1.0, 2.0]  # 3 sleeps before final attempt, no jitter


def test_aretry_succeeds_after_transient():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ValueError("t")
        return "done"

    async def noop_sleep(_):
        return None

    out = asyncio.run(
        R.aretry(flaky, attempts=3, transient=(ValueError,), sleep=noop_sleep, jitter=lambda: 0.0)
    )
    assert out == "done" and calls["n"] == 2


def test_aretry_non_transient_immediate():
    async def bad():
        raise KeyError("x")

    async def noop_sleep(_):
        return None

    with pytest.raises(KeyError):
        asyncio.run(R.aretry(bad, attempts=5, transient=(ValueError,), sleep=noop_sleep))


# ── ⑥ 배선 회귀 불변(요구사항 3, 6) ───────────────────────────────────────────
def test_wiring_not_registered_when_toggle_off(monkeypatch):
    from app.platform import wiring

    wiring._reset()
    monkeypatch.delenv("RESILIENCE_ENABLED", raising=False)
    R._register_wiring()  # toggle off → no registration
    app_handlers = []

    class _App:
        def add_event_handler(self, ev, fn):
            app_handlers.append((ev, fn))

    wiring.apply(_App())
    assert app_handlers == []  # 회귀 불변
    wiring._reset()


def test_wiring_registers_shutdown_when_toggle_on(monkeypatch):
    from app.platform import wiring

    wiring._reset()
    monkeypatch.setenv("RESILIENCE_ENABLED", "1")
    R._register_wiring()
    handlers = []

    class _App:
        def add_event_handler(self, ev, fn):
            handlers.append((ev, fn))

    wiring.apply(_App())
    assert any(ev == "shutdown" for ev, _ in handlers)
    wiring._reset()
