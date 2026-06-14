"""경량 마이그레이션 러너 — alembic 흉내(sqlite/Mock로 동작, S3·ADR-0059, 12F#10 부분).

실 alembic은 후속. 이 스캐폴드는 `schema_migrations` 테이블로 적용 버전을 추적하고, 미적용분만
버전 오름차순으로 멱등 적용한다(admin process).
"""
from .runner import Migration, MigrationRunner  # noqa: F401
