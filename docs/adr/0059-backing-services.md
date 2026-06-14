# ADR-0059: 백킹서비스(Backing Services) = Port 인터페이스 + Mock + 환경 토글

- **상태**: 채택
- **관련**: [`specs/backing-services/`](../../specs/backing-services/requirements.md),
  [`docs/production-readiness.md`](../production-readiness.md)(S3), ADR-0020(Port/Mock 경계),
  ADR-0056(환경 구성·배선 시임), ADR-0035(데이터 모델 계층), 12-Factor(VIII Backing services·XII Stateless).
- **비고**: 0053~0058은 동시 진행 스트림이 점유 — 본 스트림은 0059를 쓴다.

## 배경
프로덕션 준비도 S3(12-Factor #8 Backing services·#12 Stateless)는 외부 자원(DB·캐시·큐·세션 저장)을
**부착 가능한 자원(attached resource)**으로 다루고, 프로세스를 무상태로 만들 것을 요구한다. 현재는
실 DB(sqlite 옵션)·인메모리 repository만 있고 캐시·큐·세션 외부화의 **계약**이 없다. 실 인프라
(Postgres·Redis·메시지 브로커)는 이번 범위가 아니며(Mock 허용), 새 pip 의존성도 금지다. 따라서
**인터페이스를 먼저 고정**하고 Mock으로 구조적 구현·검증을 끝내, 후속 실 전환이 도메인을 건드리지
않게 한다.

## 결정
- **Port = `typing.Protocol`** — DB·캐시·큐·세션상태 각각을 Protocol로 추상화(ADR-0020 경계).
  런타임 상속 강제 없이 duck-typed로 합성(기존 container 철학과 동일). 실 어댑터는 동일 Protocol을
  만족시키기만 하면 교체된다.
- **Mock 구현(무의존성)** — `MockDatabase`(stdlib sqlite3), `MockCache`/`NoopCache`(dict+TTL),
  `MockQueue`(FIFO+dead-letter+재시도 훅), `InMemorySessionStateStore`(dict+TTL). 새 pip 의존성 없음.
- **경량 마이그레이션 러너** — alembic 흉내 수준. `schema_migrations` 테이블로 적용 버전 추적,
  미적용분만 순서대로 멱등 적용(admin process, 12F#10 부분). 실 alembic은 후속.
- **환경 토글 + 기본 off** — `DB_BACKEND`·`CACHE_BACKEND`·`QUEUE_BACKEND`·`SESSION_BACKEND`를
  `config.get_settings()`/env로 읽되, 미지정이면 **기존 동작 기본**(캐시 비활성·세션 인메모리·DB는
  기존 PERSISTENCE 경로). 회귀 불변(스트랭글러).
- **추가형, 시그니처 불변** — 기존 repository/adapter(`sqlite.py`·`mock.py`)는 손대지 않고 신규
  모듈만 추가한다. container 배선은 선택적(기본 off라 기존 경로 불변).

## 대안 / 기각
- **실 psycopg/redis 직접 도입** — 새 의존성·인프라 필요, 이번 범위 밖(Mock 허용 DoD). **기각**.
- **추상 기반 클래스(ABC) 상속 강제** — 기존 duck-typed 합성과 어긋나고 결합 증가. **기각**(Protocol 채택).
- **기존 repository에 캐시/큐 메서드 추가** — 시그니처 오염·금지 사항 위반. **기각**(직교 Port 분리).
- **세션 즉시 외부화(인메모리 제거)** — 회귀 위험·범위 큼. **기각** — Port만 추가, 기본은 인메모리 유지.

## 영향
- **production-readiness.md** — S3(#8 Backing services·#12 Stateless·#10 admin process 부분)의 구조적
  토대 마련. 실 클라우드 배선은 후속 웨이브.
- **이후 스트림** — S6(비용·캐싱)는 `CachePort` 위에, 선제 파이프라인은 `QueuePort` 위에 얹는다.
- **계약** — 외부 노출 API/응답 계약 변경 없음(런타임 내부 자원). 기본 off라 3계층 동기 불필요.
