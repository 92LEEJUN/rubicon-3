"""DB 어댑터 인터페이스(Postgres 지향) + Mock 구현 — S3 백킹서비스(ADR-0059, 12F#8).

`DatabasePort`(Protocol)는 연결/헬스/실행/조회 시그니처를 고정한다(ADR-0020 경계). 실 전환 시
동일 Protocol을 만족하는 Postgres(psycopg) 어댑터로 교체하면 도메인/저장소는 불변이다.

이번 범위는 Mock 허용 — `MockDatabase`는 stdlib `sqlite3`(무의존성)로 Postgres 어댑터의 자리표시를
한다. SQL 방언 차이(파라미터 `?` vs `%s`·시퀀스·UPSERT 문법)는 실 어댑터에서 ACL로 흡수한다.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class DatabasePort(Protocol):
    """DB 백킹서비스 계약 — 부착 가능한 자원(attached resource, 12F#8)."""

    def connect(self) -> None: ...

    def close(self) -> None: ...

    def ping(self) -> bool:
        """헬스체크 — 연결 가능하면 True, 아니면 False(예외 삼킴)."""
        ...

    def execute(self, sql: str, params: tuple = ()) -> None:
        """쓰기(DDL/DML). 커밋까지 수행."""
        ...

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """조회 — 행을 dict 리스트로 반환."""
        ...


class MockDatabase:
    """`DatabasePort` Mock(stdlib sqlite3, 무의존성).

    실 Postgres 어댑터의 자리표시 — 동일 Protocol을 만족한다. 기본은 `:memory:`(프로세스 내),
    파일 경로를 주면 영속한다(마이그레이션 러너 검증용).
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self.connect()

    def connect(self) -> None:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def ping(self) -> bool:
        try:
            assert self._conn is not None
            self._conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def execute(self, sql: str, params: tuple = ()) -> None:
        assert self._conn is not None
        self._conn.execute(sql, params)
        self._conn.commit()

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        assert self._conn is not None
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
