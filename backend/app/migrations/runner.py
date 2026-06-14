"""마이그레이션 러너 — 적용 버전 추적 + 미적용분만 멱등 적용(ADR-0059, 12F#10 부분).

alembic 흉내 수준의 경량 스캐폴드. `DatabasePort`(repositories/db.py) 위에서 동작하므로 Mock/sqlite로
검증 가능하고, 실 Postgres 전환 시에도 동일 Port로 그대로 돈다(시그니처 불변).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable


@dataclass(frozen=True)
class Migration:
    """단일 마이그레이션 — `version`은 정렬 키(오름차순 적용). `up(db)`가 스키마를 변경한다."""

    version: str
    name: str
    up: Callable[[object], None]


class MigrationRunner:
    """`schema_migrations` 테이블로 적용 이력을 추적한다.

    `apply()`는 미적용 마이그레이션만 버전 오름차순으로 적용하고, 이미 적용된 것은 건너뛴다(멱등).
    """

    _TABLE = "schema_migrations"

    def __init__(self, db: object) -> None:
        self._db = db
        # db는 DatabasePort 덕타이핑(execute/query 보유) — 테이블 보장.
        db.execute(  # type: ignore[attr-defined]
            f"CREATE TABLE IF NOT EXISTS {self._TABLE} ("
            "  version    TEXT PRIMARY KEY,"
            "  name       TEXT NOT NULL,"
            "  applied_at TEXT NOT NULL"
            ")"
        )

    def applied(self) -> list[str]:
        """적용된 버전 목록(오름차순)."""
        rows = self._db.query(  # type: ignore[attr-defined]
            f"SELECT version FROM {self._TABLE} ORDER BY version ASC"
        )
        return [r["version"] for r in rows]

    def apply(self, migrations: Iterable[Migration]) -> list[str]:
        """미적용분만 버전 오름차순 적용. 새로 적용한 버전 목록을 반환(멱등)."""
        done = set(self.applied())
        newly: list[str] = []
        for mig in sorted(migrations, key=lambda m: m.version):
            if mig.version in done:
                continue
            mig.up(self._db)
            self._db.execute(  # type: ignore[attr-defined]
                f"INSERT INTO {self._TABLE} (version, name, applied_at) VALUES (?, ?, ?)",
                (mig.version, mig.name, datetime.now(timezone.utc).isoformat()),
            )
            newly.append(mig.version)
        return newly
