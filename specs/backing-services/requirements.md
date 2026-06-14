# 요구사항 (Requirements) — S3 백킹서비스(Backing Services)

## 개요
12-Factor #8(Backing services)·#12(Stateless processes)를 충족하기 위한 **백킹서비스 추상화
토대**를 만든다. 실 인프라(Postgres·Redis·큐)는 배선하지 않고 **Port 인터페이스 + Mock 구현**을
추가형(스트랭글러)으로 도입한다. 기본 동작은 기존과 동일(회귀 불변)하고, `config.get_settings()`
환경/토글에 따라서만 새 백엔드를 선택한다. 모든 추상화는 ADR-0020(Port/Mock 경계)을 따르며,
도메인 로직은 손대지 않는다.

## 요구사항 목록

### 요구사항 1: 실 DB 어댑터 인터페이스 + 마이그레이션 러너 스캐폴드

**User Story:**
플랫폼 엔지니어로서, 실 DB(Postgres 지향) 연결과 스키마 마이그레이션의 **계약**을 원한다,
그래서 실 인프라 배선 전에 도메인/저장소를 그 계약 위에서 검증하고 후속 전환을 최소 변경으로 할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `DatabasePort` 인터페이스가 정의될 때 THEN 시스템은 연결 획득/해제·헬스체크·실행/조회의
   **시그니처를 고정**해야 한다 (SHALL).
2. WHEN Mock(sqlite/메모리) 구현이 주입될 때 THEN 시스템은 동일 시그니처로 **기본 동작과 동일**하게
   동작해야 한다 (SHALL).
3. WHEN 마이그레이션 러너가 실행될 때 THEN 시스템은 적용된 버전을 추적하고 **미적용분만 순서대로**
   적용해야 한다(멱등) (SHALL).
4. IF 동일 마이그레이션을 재실행하면 THEN 시스템은 **재적용하지 않아야** 한다 (SHALL).
5. WHEN `DB_BACKEND`(또는 환경 기본)이 미지정일 때 THEN 시스템은 기존 인메모리/sqlite 경로를
   **그대로 사용**해야 한다(회귀 불변) (SHALL).

### 요구사항 2: 캐시 인터페이스(Redis 지향) + Mock 구현

**User Story:**
백엔드 개발자로서, 캐시(Redis 지향)의 get/set/delete/TTL **계약**을 원한다,
그래서 비용·성능 스트림(S6)이 실 Redis 없이도 캐시 위에서 개발·테스트할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `CachePort`가 정의될 때 THEN 시스템은 `get`·`set(ttl)`·`delete`·`clear` 시그니처를 고정해야 한다 (SHALL).
2. WHEN Mock 캐시에 TTL과 함께 값을 저장할 때 THEN 시스템은 **만료 후 미스**를 반환해야 한다 (SHALL).
3. WHEN 같은 키를 다시 set할 때 THEN 시스템은 **최신 값으로 덮어써야** 한다 (SHALL).
4. WHEN `CACHE_BACKEND`가 미지정일 때 THEN 시스템은 캐시를 **비활성(no-op/메모리 기본)**으로 두어
   기존 동작을 바꾸지 않아야 한다 (SHALL).

### 요구사항 3: 큐/배치 인터페이스 + Mock 구현 + 재시도 훅

**User Story:**
백엔드 개발자로서, 비동기 작업을 적재/소비하는 큐 **계약**과 실패 재시도 훅을 원한다,
그래서 선제 파이프라인·배치 작업을 인프라 없이 구조적으로 검증할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `QueuePort`가 정의될 때 THEN 시스템은 `enqueue`·`dequeue`·`size` 시그니처를 고정해야 한다 (SHALL).
2. WHEN 핸들러가 예외를 던질 때 THEN 시스템은 설정된 **최대 시도 횟수까지 재시도**해야 한다 (SHALL).
3. IF 최대 시도를 초과하면 THEN 시스템은 작업을 **데드레터(dead-letter)**로 이동해야 한다 (SHALL).
4. WHEN 작업이 성공하면 THEN 시스템은 **재시도하지 않고** 큐에서 제거해야 한다 (SHALL).

### 요구사항 4: 세션 상태 외부화 Port (Stateless, 12F#12)

**User Story:**
운영자로서, 현재 인메모리에 있는 세션/워킹 상태를 외부 저장으로 **빼낼 수 있는 Port**를 원한다,
그래서 프로세스가 무상태가 되어 수평 확장·재시작 시 상태가 보존된다.

**수용기준 (Acceptance Criteria):**
1. WHEN `SessionStatePort`가 정의될 때 THEN 시스템은 `load`·`save`·`delete`·`touch` 시그니처를 고정해야 한다 (SHALL).
2. WHEN 외부 저장(Mock) 구현에 상태를 저장한 뒤 새 인스턴스가 같은 키를 load할 때 THEN 시스템은
   저장된 상태를 **복원**해야 한다 (SHALL).
3. WHEN TTL이 지정되고 만료될 때 THEN 시스템은 해당 세션을 **만료(미스)** 처리해야 한다 (SHALL).
4. WHEN `SESSION_BACKEND`가 미지정일 때 THEN 시스템은 **인메모리 기본**(기존 동작)으로 두어야 한다 (SHALL).

### 요구사항 5: 환경 기반 선택 + DI 합성 (회귀 불변)

**User Story:**
플랫폼 엔지니어로서, 모든 백킹서비스 백엔드가 `config.get_settings()`/env로 일관 선택되길 원한다,
그래서 환경별(dev/stg/prd) parity가 생기고 기본값은 기존 동작과 동일하다.

**수용기준 (Acceptance Criteria):**
1. WHEN 어떤 백킹서비스 토글도 지정되지 않을 때 THEN 시스템은 **모든 기본값이 기존 동작과 동일**해야 한다 (SHALL).
2. WHEN 백엔드 토글이 `memory`/`mock`으로 지정될 때 THEN 시스템은 동일 시그니처의 구현을 **DI로 주입**해야 한다 (SHALL).
3. WHEN 기존 테스트(persistence·multitenant 포함)가 실행될 때 THEN 시스템은 **전부 green**이어야 한다 (SHALL).
