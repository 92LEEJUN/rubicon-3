"""멀티테넌트 slice 3 — DB 영속(sqlite) Repository 테스트.

- 계약 동등성: 인메모리/Sqlite 구현이 동일 동작(save/get 라운드트립, user 격리, list/open).
- 영속/복원: Sqlite로 쓴 뒤 같은 파일로 새 인스턴스를 만들면 데이터가 복원된다.
- 토글: PERSISTENCE 환경변수로 build_container()가 어떤 백엔드를 주입하는지.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain import ConversationMemory, OpenLoop
from app.repositories.conversation_memory import InMemoryConversationMemoryRepository
from app.repositories.memory import InMemoryEngagementRepository
from app.repositories.open_loop import InMemoryOpenLoopRepository
from app.repositories.sqlite import (
    SqliteConversationMemoryRepository,
    SqliteEngagementRepository,
    SqliteOpenLoopRepository,
)


def _loop(ref: str, *, status: str = "open", priority: int = 0) -> OpenLoop:
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    return OpenLoop(
        id=f"loop-{ref}", kind="issue", ref=ref, label=f"label-{ref}",
        status=status, priority=priority, opened_at=now, last_touch=now,
    )


# ── 팩토리: 인메모리는 인자 없음, Sqlite는 tmp 파일 경로 주입 ──────────────────
def _make_conv_mem(kind: str, tmp_path):
    if kind == "memory":
        return InMemoryConversationMemoryRepository()
    return SqliteConversationMemoryRepository(str(tmp_path / "conv.db"))


def _make_open_loop(kind: str, tmp_path):
    if kind == "memory":
        return InMemoryOpenLoopRepository()
    return SqliteOpenLoopRepository(str(tmp_path / "loops.db"))


def _make_engagement(kind: str, tmp_path):
    if kind == "memory":
        return InMemoryEngagementRepository()
    return SqliteEngagementRepository(str(tmp_path / "eng.db"))


BACKENDS = ["memory", "db"]


# ── ConversationMemory 계약 ────────────────────────────────────────────────
@pytest.mark.parametrize("kind", BACKENDS)
def test_conv_memory_roundtrip_and_default(kind, tmp_path):
    repo = _make_conv_mem(kind, tmp_path)
    # 없으면 빈 메모리(첫 방문).
    assert repo.get("alice") == ConversationMemory()
    mem = ConversationMemory(summary="hi", facts={"order": "o-1"}, summarized_through=3)
    repo.save("alice", mem)
    got = repo.get("alice")
    assert got.summary == "hi"
    assert got.facts == {"order": "o-1"}
    assert got.summarized_through == 3


@pytest.mark.parametrize("kind", BACKENDS)
def test_conv_memory_user_isolation(kind, tmp_path):
    repo = _make_conv_mem(kind, tmp_path)
    repo.save("alice", ConversationMemory(summary="A-only"))
    # B는 A의 데이터를 보지 못함 — 빈 메모리.
    assert repo.get("bob") == ConversationMemory()
    assert repo.get("alice").summary == "A-only"


@pytest.mark.parametrize("kind", BACKENDS)
def test_conv_memory_delete(kind, tmp_path):
    repo = _make_conv_mem(kind, tmp_path)
    repo.save("alice", ConversationMemory(summary="x"))
    repo.delete("alice")
    assert repo.get("alice") == ConversationMemory()
    repo.delete("alice")  # 멱등.


# ── OpenLoop 계약 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("kind", BACKENDS)
def test_open_loop_upsert_get_and_idempotent(kind, tmp_path):
    repo = _make_open_loop(kind, tmp_path)
    assert repo.get("alice", "r1") is None
    repo.upsert("alice", _loop("r1", priority=1))
    repo.upsert("alice", _loop("r1", priority=5))  # 같은 ref 덮어쓰기(멱등).
    got = repo.get("alice", "r1")
    assert got is not None and got.priority == 5


@pytest.mark.parametrize("kind", BACKENDS)
def test_open_loop_list_open_sorted_and_filtered(kind, tmp_path):
    repo = _make_open_loop(kind, tmp_path)
    repo.upsert("alice", _loop("low", priority=1))
    repo.upsert("alice", _loop("high", priority=9))
    repo.upsert("alice", _loop("closed", status="resolved", priority=99))
    open_loops = repo.list_open("alice")
    # resolved는 제외, 우선순위 내림차순.
    assert [l.ref for l in open_loops] == ["high", "low"]


@pytest.mark.parametrize("kind", BACKENDS)
def test_open_loop_set_status_and_isolation(kind, tmp_path):
    repo = _make_open_loop(kind, tmp_path)
    repo.upsert("alice", _loop("r1"))
    updated = repo.set_status("alice", "r1", "resolved")
    assert updated is not None and updated.status == "resolved"
    assert repo.list_open("alice") == []
    # 없는 ref면 None.
    assert repo.set_status("alice", "nope", "open") is None
    # user 격리: bob은 alice의 loop를 못 봄.
    assert repo.get("bob", "r1") is None
    assert repo.list_open("bob") == []


@pytest.mark.parametrize("kind", BACKENDS)
def test_open_loop_clear(kind, tmp_path):
    repo = _make_open_loop(kind, tmp_path)
    repo.upsert("alice", _loop("r1"))
    repo.clear("alice")
    assert repo.get("alice", "r1") is None


# ── Engagement 계약 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("kind", BACKENDS)
def test_engagement_record_get_has_seen(kind, tmp_path):
    repo = _make_engagement(kind, tmp_path)
    assert repo.get("alice", "ref1") is None
    assert repo.has_seen("alice", "ref1") is False
    rec = repo.record("alice", "ref1", "viewed")
    assert rec.user_id == "alice" and rec.ref == "ref1" and rec.state == "viewed"
    assert repo.has_seen("alice", "ref1") is True
    # interested는 'seen'(중복 억제)에 해당하지 않음.
    repo.record("alice", "ref2", "interested")
    assert repo.has_seen("alice", "ref2") is False


@pytest.mark.parametrize("kind", BACKENDS)
def test_engagement_list_and_isolation(kind, tmp_path):
    repo = _make_engagement(kind, tmp_path)
    repo.record("alice", "ref1", "viewed")
    repo.record("alice", "ref2", "dismissed")
    repo.record("bob", "ref3", "viewed")
    alice = {r.ref for r in repo.list("alice")}
    assert alice == {"ref1", "ref2"}
    # user 격리: bob의 데이터는 alice 목록에 없음.
    assert {r.ref for r in repo.list("bob")} == {"ref3"}


@pytest.mark.parametrize("kind", BACKENDS)
def test_engagement_record_overwrites(kind, tmp_path):
    repo = _make_engagement(kind, tmp_path)
    repo.record("alice", "ref1", "viewed")
    repo.record("alice", "ref1", "dismissed")  # 같은 키 최신 상태로 덮어씀.
    assert repo.get("alice", "ref1").state == "dismissed"
    assert len(repo.list("alice")) == 1


# ── 영속/복원: 새 인스턴스가 같은 파일에서 데이터를 복원 ─────────────────────
def test_sqlite_conv_memory_persists_across_instances(tmp_path):
    db = str(tmp_path / "p.db")
    SqliteConversationMemoryRepository(db).save("alice", ConversationMemory(summary="kept"))
    restored = SqliteConversationMemoryRepository(db)  # 새 인스턴스, 같은 파일.
    assert restored.get("alice").summary == "kept"


def test_sqlite_open_loop_persists_across_instances(tmp_path):
    db = str(tmp_path / "p.db")
    SqliteOpenLoopRepository(db).upsert("alice", _loop("r1", priority=7))
    restored = SqliteOpenLoopRepository(db)
    got = restored.get("alice", "r1")
    assert got is not None and got.priority == 7


def test_sqlite_engagement_persists_across_instances(tmp_path):
    db = str(tmp_path / "p.db")
    SqliteEngagementRepository(db).record("alice", "ref1", "viewed")
    restored = SqliteEngagementRepository(db)
    assert restored.has_seen("alice", "ref1") is True


# ── 토글: build_container()가 PERSISTENCE에 따라 백엔드를 주입 ────────────────
def test_container_default_is_in_memory(monkeypatch):
    monkeypatch.delenv("PERSISTENCE", raising=False)
    from app.container import build_container

    c = build_container()
    assert isinstance(c.conversation_memory, InMemoryConversationMemoryRepository)
    assert isinstance(c.engagement, InMemoryEngagementRepository)


def test_container_db_toggle_uses_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE", "db")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "container.db"))
    from app.container import build_container

    c = build_container()
    assert isinstance(c.conversation_memory, SqliteConversationMemoryRepository)
    assert isinstance(c.engagement, SqliteEngagementRepository)
