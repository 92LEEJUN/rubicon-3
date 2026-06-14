# 설계 (Design) — S3 백킹서비스(Backing Services)

> 참조 기반 문서: [ADR-0020](../../docs/adr/0020-port-mock-real-boundary.md)(Port/Mock 경계),
> [ADR-0056](../../docs/adr/0056-environment-config-baseline.md)(환경 구성·배선 시임),
> [ADR-0059](../../docs/adr/0059-backing-services.md)(본 스트림 결정),
> [docs/production-readiness.md](../../docs/production-readiness.md)(S3).
> 데이터 모델·아키텍처는 기반 문서를 따르고, 여기서는 **백킹서비스 고유 설계**만 담는다.

## 개요
실 인프라를 배선하지 않고 **Port 인터페이스 + Mock 구현**을 추가형으로 도입한다. 4개 백킹서비스
(DB·캐시·큐·세션상태)를 각각 Port로 추상화하고, `config.get_settings()`/env 토글로 백엔드를
선택한다. 기본값은 전부 **기존 동작과 동일**(회귀 불변). 기존 repository/adapter 시그니처는
건드리지 않고 새 모듈만 추가한다.

## 아키텍처
```
config.get_settings()/env
        │ (DB_BACKEND / CACHE_BACKEND / QUEUE_BACKEND / SESSION_BACKEND)
        ▼
backing.py (팩토리: select_*)  ──DI──▶  Port 인터페이스 (typing.Protocol)
        │                                   ├─ DatabasePort   (repositories/db.py)
        │                                   ├─ CachePort      (adapters/cache.py)
        │                                   ├─ QueuePort      (adapters/queue.py)
        │                                   └─ SessionStatePort(repositories/session_state.py)
        ▼
migrations/runner.py (경량 마이그레이션 러너 — alembic 흉내, sqlite/Mock)
```
- Port = `typing.Protocol`(런타임 의존 없음, duck-typed). 기존 container의 duck-typing 합성과 동일 철학.
- Mock 구현은 메모리 기반(테스트 결정적). 실 전환 시 동일 Protocol을 만족하는 psycopg/redis 어댑터로 교체.

## 주요 컴포넌트 / 인터페이스

### 1. DB 어댑터 인터페이스 + 마이그레이션 러너 (요구사항 1)
- `repositories/db.py`
  - `DatabasePort`(Protocol): `connect()`·`close()`·`ping() -> bool`·`execute(sql, params)`·
    `query(sql, params) -> list[dict]`.
  - `MockDatabase`: stdlib `sqlite3` 기반(`:memory:` 기본). 실 Postgres 어댑터의 자리표시.
    Postgres 지향 주석으로 매핑 가이드 표기(ACL).
- `migrations/`
  - `runner.py`: `MigrationRunner(db)`. `schema_migrations` 테이블로 적용 버전 추적.
    `apply(migrations)` = 미적용분만 버전 오름차순 적용(멱등). `applied() -> list[str]`.
  - `Migration` 데이터클래스: `version`(정렬 키)·`name`·`up(db)` 콜러블.
  - `migrations/0001_baseline.py`: 데모 baseline 마이그레이션(예시 1개).

### 2. 캐시 인터페이스 (요구사항 2)
- `adapters/cache.py`
  - `CachePort`(Protocol): `get(key)`·`set(key, value, ttl=None)`·`delete(key)`·`clear()`.
  - `MockCache`: dict 기반 + per-key 만료시각. 시계는 주입 가능(`now_fn`)해 테스트 결정적.
  - `NoopCache`: 항상 미스(캐시 비활성 기본 = 기존 동작).

### 3. 큐/배치 인터페이스 + 재시도 (요구사항 3)
- `adapters/queue.py`
  - `QueuePort`(Protocol): `enqueue(job)`·`dequeue() -> job|None`·`size()`.
  - `MockQueue`: FIFO 리스트. `dead_letter` 리스트 보유.
  - `process(handler, max_attempts)`: dequeue→handler 실행. 예외 시 attempts 증가해 재시도,
    `max_attempts` 초과 시 dead_letter 이동. 성공 시 제거. 처리 건수/결과 반환.

### 4. 세션 상태 외부화 Port (요구사항 4)
- `repositories/session_state.py`
  - `SessionStatePort`(Protocol): `load(key)`·`save(key, state, ttl=None)`·`delete(key)`·`touch(key, ttl)`.
  - `InMemorySessionStateStore`: dict + 만료(기본 = 기존 인메모리 동작).
  - 새 인스턴스로 같은 백엔드를 공유하면 복원되는 구조를 Mock으로 표현(클래스 변수 스토어 옵션).

### 5. 환경 기반 선택 + DI (요구사항 5)
- `backing.py`(repositories 패키지 내 신규 모듈)
  - `select_database()`·`select_cache()`·`select_queue()`·`select_session_state()`.
  - 각 토글 env(`DB_BACKEND`·`CACHE_BACKEND`·`QUEUE_BACKEND`·`SESSION_BACKEND`)를 읽고
    미지정이면 **기존 동작 기본**을 반환. `config.get_settings()`로 env parity 일관.
  - container 배선은 **선택적**: 기본 off라 기존 container 경로 불변. 필요 시 한 줄 append만.

## 데이터 모델
- 새 도메인 타입 추가 없음. DB는 SQL 문자열/행 dict, 캐시/세션은 임의 직렬화 가능 값,
  큐는 임의 dict job. 기존 도메인 모델(`domain.py`)은 불변.
- `schema_migrations(version TEXT PRIMARY KEY, name TEXT, applied_at TEXT)`.

## 에러 처리
- DB: `ping()`은 실패 시 `False`(예외 삼킴). `query/execute`는 드라이버 예외를 그대로 전파.
- 캐시: 미스 = `None`(예외 아님). 만료는 미스로 취급.
- 큐: 핸들러 예외는 재시도 루프가 포착. `max_attempts` 초과 → dead_letter(소실 없음).
- 세션: 만료 load = `None`. 없는 키 delete/touch는 멱등(no-op).

## 테스트 전략
- `backend/tests/test_backing_services.py`(신규, 추가형):
  - DB: ping/execute/query 라운드트립, 마이그레이션 멱등·순서·재적용 무시.
  - 캐시: set/get, TTL 만료(주입 시계), 덮어쓰기, Noop 미스.
  - 큐: enqueue/dequeue/size FIFO, 성공 제거, 재시도→dead_letter.
  - 세션: save/load 복원, TTL 만료, delete/touch 멱등.
  - 선택 팩토리: 토글 미지정 = 기본(회귀), `mock`/`memory` 지정 = 해당 구현.
- **기존 테스트 불변**: persistence·multitenant 포함 전 스위트 green 유지.
