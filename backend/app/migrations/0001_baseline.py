"""0001 baseline — 데모 마이그레이션(ADR-0059). 실 스키마는 실 DB 전환 시 채운다.

마이그레이션 모듈 패턴 예시: `migration` 객체를 노출하고, 러너에 `[migration]`으로 넘긴다.
"""
from __future__ import annotations

from .runner import Migration


def _up(db: object) -> None:
    # 데모용 placeholder 테이블 — 실 전환 시 도메인 스키마로 대체.
    db.execute(  # type: ignore[attr-defined]
        "CREATE TABLE IF NOT EXISTS backing_baseline ("
        "  id   INTEGER PRIMARY KEY,"
        "  note TEXT"
        ")"
    )


migration = Migration(version="0001", name="baseline", up=_up)
