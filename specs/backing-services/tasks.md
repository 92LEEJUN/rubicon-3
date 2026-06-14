# 작업 (Tasks) — S3 백킹서비스(Backing Services)

> 참조: [requirements.md](requirements.md) · [design.md](design.md) · [ADR-0059](../../docs/adr/0059-backing-services.md)

## 체크리스트

### 문서
- [x] ADR-0059 작성(백킹서비스 결정·대안·기각) (요구사항 1~5)
- [x] specs 3종(requirements/design/tasks) 작성 (요구사항 1~5)

### 구현 — DB + 마이그레이션
- [x] `repositories/db.py` — `DatabasePort`(Protocol) + `MockDatabase`(sqlite3) (요구사항 1.1·1.2)
- [x] `migrations/__init__.py`·`runner.py` — `Migration`·`MigrationRunner`(버전 추적·멱등) (요구사항 1.3·1.4)
- [x] `migrations/0001_baseline.py` — 데모 baseline 마이그레이션 (요구사항 1.3)

### 구현 — 캐시
- [x] `adapters/cache.py` — `CachePort`(Protocol)·`MockCache`(TTL)·`NoopCache` (요구사항 2.1~2.4)

### 구현 — 큐/배치
- [x] `adapters/queue.py` — `QueuePort`(Protocol)·`MockQueue`·`process`(재시도·dead-letter) (요구사항 3.1~3.4)

### 구현 — 세션 상태 외부화
- [x] `repositories/session_state.py` — `SessionStatePort`(Protocol)·`InMemorySessionStateStore`(TTL) (요구사항 4.1~4.4)

### 구현 — 선택/DI
- [x] `repositories/backing.py` — `select_database/cache/queue/session_state`(env 토글·기본 off) (요구사항 5.1·5.2)

### 테스트 / 검증
- [x] `backend/tests/test_backing_services.py` — Port별 계약·TTL·재시도·선택 팩토리 (요구사항 1~5)
- [x] `ruff check backend/` 클린 (요구사항 5.3)
- [x] `cd backend && python -m pytest` 전부 green(기존 persistence·multitenant 포함) (요구사항 5.3)
