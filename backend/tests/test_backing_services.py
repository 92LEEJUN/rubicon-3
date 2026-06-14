"""S3 백킹서비스 — Port 인터페이스 + Mock 계약 테스트(ADR-0059, 12F#8·#12).

- DB: ping/execute/query 라운드트립 + 마이그레이션 멱등·순서·재적용 무시.
- 캐시: set/get·TTL 만료(주입 시계)·덮어쓰기·Noop 미스.
- 큐: FIFO·성공 제거·재시도→데드레터.
- 세션 상태: save/load 복원·TTL 만료·delete/touch 멱등.
- 선택 팩토리: 토글 미지정=기본(회귀), mock/memory 지정=해당 구현.

추가형 — 기존 테스트(persistence·multitenant 포함)는 건드리지 않는다.
"""
from __future__ import annotations

from app.adapters.cache import CachePort, MockCache, NoopCache
from app.adapters.queue import MockQueue, QueuePort
from app.migrations import MigrationRunner
from app.migrations.runner import Migration
from app.repositories.backing import (
    select_cache,
    select_database,
    select_queue,
    select_session_state,
)
from app.repositories.db import DatabasePort, MockDatabase
from app.repositories.session_state import InMemorySessionStateStore, SessionStatePort


# ── 가짜 시계(TTL 결정적 테스트용) ───────────────────────────────────────────
class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# ── DB Port ─────────────────────────────────────────────────────────────────
def test_mock_database_satisfies_port():
    db = MockDatabase()
    assert isinstance(db, DatabasePort)


def test_mock_database_ping_execute_query_roundtrip():
    db = MockDatabase()
    assert db.ping() is True
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    db.execute("INSERT INTO t (id, v) VALUES (?, ?)", (1, "hello"))
    rows = db.query("SELECT id, v FROM t")
    assert rows == [{"id": 1, "v": "hello"}]


def test_mock_database_ping_false_after_close():
    db = MockDatabase()
    db.close()
    assert db.ping() is False


# ── 마이그레이션 러너 ─────────────────────────────────────────────────────────
def _mk_migration(version: str, table: str) -> Migration:
    def _up(db: object) -> None:
        db.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")  # type: ignore[attr-defined]

    return Migration(version=version, name=table, up=_up)


def test_migration_runner_applies_pending_in_order():
    db = MockDatabase()
    runner = MigrationRunner(db)
    migs = [_mk_migration("0002", "b"), _mk_migration("0001", "a")]
    applied = runner.apply(migs)
    assert applied == ["0001", "0002"]  # 버전 오름차순
    assert runner.applied() == ["0001", "0002"]
    # 두 테이블이 실제로 생성됨.
    names = {r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"a", "b"} <= names


def test_migration_runner_is_idempotent():
    db = MockDatabase()
    runner = MigrationRunner(db)
    migs = [_mk_migration("0001", "a")]
    assert runner.apply(migs) == ["0001"]
    # 재실행 — 재적용 없음.
    assert runner.apply(migs) == []
    assert runner.applied() == ["0001"]


def test_migration_runner_only_applies_new():
    db = MockDatabase()
    runner = MigrationRunner(db)
    runner.apply([_mk_migration("0001", "a")])
    newly = runner.apply([_mk_migration("0001", "a"), _mk_migration("0002", "b")])
    assert newly == ["0002"]


def test_baseline_migration_applies():
    import importlib

    mod = importlib.import_module("app.migrations.0001_baseline")
    db = MockDatabase()
    runner = MigrationRunner(db)
    assert runner.apply([mod.migration]) == ["0001"]
    names = {r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "backing_baseline" in names


# ── 캐시 Port ─────────────────────────────────────────────────────────────────
def test_mock_cache_satisfies_port():
    assert isinstance(MockCache(), CachePort)
    assert isinstance(NoopCache(), CachePort)


def test_mock_cache_set_get_overwrite_delete():
    c = MockCache()
    assert c.get("k") is None
    c.set("k", 1)
    assert c.get("k") == 1
    c.set("k", 2)  # 덮어쓰기
    assert c.get("k") == 2
    c.delete("k")
    assert c.get("k") is None


def test_mock_cache_ttl_expiry():
    clock = _Clock()
    c = MockCache(now_fn=clock)
    c.set("k", "v", ttl=10)
    assert c.get("k") == "v"
    clock.advance(10)  # 만료시각 도달
    assert c.get("k") is None


def test_noop_cache_always_miss():
    c = NoopCache()
    c.set("k", "v")
    assert c.get("k") is None


# ── 큐 Port ───────────────────────────────────────────────────────────────────
def test_mock_queue_satisfies_port():
    assert isinstance(MockQueue(), QueuePort)


def test_mock_queue_fifo():
    q = MockQueue()
    assert q.dequeue() is None
    q.enqueue({"n": 1})
    q.enqueue({"n": 2})
    assert q.size() == 2
    assert q.dequeue()["n"] == 1
    assert q.dequeue()["n"] == 2
    assert q.size() == 0


def test_mock_queue_process_success_removes():
    q = MockQueue()
    q.enqueue({"n": 1})
    q.enqueue({"n": 2})
    seen = []
    res = q.process(lambda job: seen.append(job["n"]))
    assert seen == [1, 2]
    assert res == {"succeeded": 2, "dead_lettered": 0}
    assert q.size() == 0
    assert q.dead_letter == []


def test_mock_queue_retry_then_dead_letter():
    q = MockQueue()
    q.enqueue({"n": 1})

    def _always_fail(job):
        raise RuntimeError("boom")

    res = q.process(_always_fail, max_attempts=3)
    assert res == {"succeeded": 0, "dead_lettered": 1}
    assert q.size() == 0
    assert len(q.dead_letter) == 1
    assert q.dead_letter[0]["_attempts"] == 3


def test_mock_queue_retry_eventually_succeeds():
    q = MockQueue()
    q.enqueue({"n": 1})
    calls = {"c": 0}

    def _flaky(job):
        calls["c"] += 1
        if calls["c"] < 2:
            raise RuntimeError("transient")

    res = q.process(_flaky, max_attempts=3)
    assert res == {"succeeded": 1, "dead_lettered": 0}
    assert q.dead_letter == []


# ── 세션 상태 Port ────────────────────────────────────────────────────────────
def test_session_state_satisfies_port():
    assert isinstance(InMemorySessionStateStore(), SessionStatePort)


def test_session_state_save_load_delete():
    s = InMemorySessionStateStore()
    assert s.load("u1") is None
    s.save("u1", {"step": 3})
    assert s.load("u1") == {"step": 3}
    s.delete("u1")
    assert s.load("u1") is None
    s.delete("u1")  # 멱등


def test_session_state_ttl_expiry_and_touch():
    clock = _Clock()
    s = InMemorySessionStateStore(now_fn=clock)
    s.save("u1", "x", ttl=10)
    clock.advance(5)
    s.touch("u1", ttl=10)  # 슬라이딩 연장
    clock.advance(8)
    assert s.load("u1") == "x"  # 연장 덕에 아직 유효
    clock.advance(3)
    assert s.load("u1") is None  # 만료
    s.touch("nope", ttl=10)  # 없는 키 no-op(멱등)


def test_session_state_shared_restores_across_instances():
    InMemorySessionStateStore._SHARED.clear()
    a = InMemorySessionStateStore(shared=True)
    a.save("u1", {"v": 1})
    b = InMemorySessionStateStore(shared=True)  # 새 인스턴스, 같은 외부 저장
    assert b.load("u1") == {"v": 1}
    InMemorySessionStateStore._SHARED.clear()


# ── 선택 팩토리(env 토글·기본 off) ────────────────────────────────────────────
def test_select_defaults_are_regression_safe(monkeypatch):
    for k in ("DB_BACKEND", "CACHE_BACKEND", "QUEUE_BACKEND", "SESSION_BACKEND", "SESSION_SHARED"):
        monkeypatch.delenv(k, raising=False)
    assert isinstance(select_database(), MockDatabase)
    assert isinstance(select_cache(), NoopCache)  # 캐시 비활성 = 기존 동작
    assert isinstance(select_queue(), MockQueue)
    assert isinstance(select_session_state(), InMemorySessionStateStore)


def test_select_cache_memory_toggle(monkeypatch):
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    assert isinstance(select_cache(), MockCache)
    monkeypatch.setenv("CACHE_BACKEND", "mock")
    assert isinstance(select_cache(), MockCache)


def test_select_session_shared_toggle(monkeypatch):
    monkeypatch.setenv("SESSION_SHARED", "1")
    s = select_session_state()
    assert isinstance(s, InMemorySessionStateStore)
