"""SQLite 백엔드 Repository — user 단위 영속(stdlib `sqlite3`, 무의존성).

`PERSISTENCE=db` 토글 시 인메모리 Repository를 대체한다(인터페이스 불변).
인메모리 구현(`conversation_memory.py`·`open_loop.py`·`memory.py`)과 **동일한
메서드 시그니처**를 가지며, 도메인 객체는 pydantic JSON으로 직렬화해 컬럼에 보관한다.

영속성 주의: `:memory:` DB는 커넥션 간 공유되지 않으므로(토글/재시작 복원 불가),
실 영속은 파일 경로를 쓴다(container는 `SQLITE_PATH` 또는 기본 파일 경로 주입).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..domain import (
    ConversationMemory,
    EngagementRecord,
    EngagementState,
    OpenLoop,
)


def _connect(db_path: str) -> sqlite3.Connection:
    # check_same_thread=False: 서비스가 단일 커넥션을 여러 코루틴/스레드에서 재사용해도
    # 안전하도록(스크립트성 단일 프로세스 MVP). autocommit 동작은 매 write 후 commit으로 보장.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class SqliteConversationMemoryRepository:
    """대화 메모리 — user 단위. JSON 1컬럼에 `ConversationMemory` 저장."""

    def __init__(self, db_path: str = "rubicon.db") -> None:
        self._conn = _connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS conversation_memory ("
            "  user_id TEXT PRIMARY KEY,"
            "  data    TEXT NOT NULL"
            ")"
        )
        self._conn.commit()

    def get(self, user_id: str) -> ConversationMemory:
        """없으면 빈 메모리(첫 방문 = 깨끗한 시작)."""
        row = self._conn.execute(
            "SELECT data FROM conversation_memory WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return ConversationMemory()
        return ConversationMemory.model_validate_json(row["data"])

    def save(self, user_id: str, memory: ConversationMemory) -> None:
        self._conn.execute(
            "INSERT INTO conversation_memory (user_id, data) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data",
            (user_id, memory.model_dump_json()),
        )
        self._conn.commit()

    def delete(self, user_id: str) -> None:
        """삭제 요청 cascade(R19)."""
        self._conn.execute(
            "DELETE FROM conversation_memory WHERE user_id = ?", (user_id,)
        )
        self._conn.commit()


class SqliteOpenLoopRepository:
    """미해결 스레드(OpenLoop) — (user_id, ref) 단위 upsert(멱등). JSON으로 저장."""

    def __init__(self, db_path: str = "rubicon.db") -> None:
        self._conn = _connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS open_loops ("
            "  user_id TEXT NOT NULL,"
            "  ref     TEXT NOT NULL,"
            "  data    TEXT NOT NULL,"
            "  PRIMARY KEY (user_id, ref)"
            ")"
        )
        self._conn.commit()

    def upsert(self, user_id: str, loop: OpenLoop) -> None:
        self._conn.execute(
            "INSERT INTO open_loops (user_id, ref, data) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, ref) DO UPDATE SET data = excluded.data",
            (user_id, loop.ref, loop.model_dump_json()),
        )
        self._conn.commit()

    def get(self, user_id: str, ref: str) -> OpenLoop | None:
        row = self._conn.execute(
            "SELECT data FROM open_loops WHERE user_id = ? AND ref = ?",
            (user_id, ref),
        ).fetchone()
        if row is None:
            return None
        return OpenLoop.model_validate_json(row["data"])

    def list_open(self, user_id: str) -> list[OpenLoop]:
        rows = self._conn.execute(
            "SELECT data FROM open_loops WHERE user_id = ?", (user_id,)
        ).fetchall()
        loops = [OpenLoop.model_validate_json(r["data"]) for r in rows]
        loops = [loop for loop in loops if loop.status == "open"]
        # 우선순위·최근순(인메모리 구현과 동일 정렬).
        return sorted(loops, key=lambda loop: (loop.priority, loop.last_touch), reverse=True)

    def set_status(self, user_id: str, ref: str, status: str) -> OpenLoop | None:
        loop = self.get(user_id, ref)
        if loop is None:
            return None
        updated = loop.model_copy(update={"status": status})
        self._conn.execute(
            "UPDATE open_loops SET data = ? WHERE user_id = ? AND ref = ?",
            (updated.model_dump_json(), user_id, ref),
        )
        self._conn.commit()
        return updated

    def clear(self, user_id: str) -> None:
        self._conn.execute("DELETE FROM open_loops WHERE user_id = ?", (user_id,))
        self._conn.commit()


class SqliteEngagementRepository:
    """Engagement(R29) — (user_id, ref) 단위 열람/무시/관심 상태. JSON으로 저장."""

    _SEEN_STATES = ("viewed", "acknowledged", "dismissed")

    def __init__(self, db_path: str = "rubicon.db") -> None:
        self._conn = _connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS engagement ("
            "  user_id TEXT NOT NULL,"
            "  ref     TEXT NOT NULL,"
            "  data    TEXT NOT NULL,"
            "  PRIMARY KEY (user_id, ref)"
            ")"
        )
        self._conn.commit()

    def record(self, user_id: str, ref: str, state: EngagementState) -> EngagementRecord:
        rec = EngagementRecord(
            user_id=user_id, ref=ref, state=state,
            updated_at=datetime.now(timezone.utc),
        )
        self._conn.execute(
            "INSERT INTO engagement (user_id, ref, data) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, ref) DO UPDATE SET data = excluded.data",
            (user_id, ref, rec.model_dump_json()),
        )
        self._conn.commit()
        return rec

    def get(self, user_id: str, ref: str) -> EngagementRecord | None:
        row = self._conn.execute(
            "SELECT data FROM engagement WHERE user_id = ? AND ref = ?",
            (user_id, ref),
        ).fetchone()
        if row is None:
            return None
        return EngagementRecord.model_validate_json(row["data"])

    def list(self, user_id: str) -> list[EngagementRecord]:
        rows = self._conn.execute(
            "SELECT data FROM engagement WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [EngagementRecord.model_validate_json(r["data"]) for r in rows]

    def has_seen(self, user_id: str, ref: str) -> bool:
        """이미 열람/확인/무시했는지 — 중복 노출 억제용."""
        rec = self.get(user_id, ref)
        return rec is not None and rec.state in self._SEEN_STATES
