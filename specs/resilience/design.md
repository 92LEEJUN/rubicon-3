# 설계 (Design) — 신뢰성/회복력(Resilience)

> `requirements.md` 의 요구사항을 **어떻게** 만족시킬지 설명한다.
> 관련 기반 문서: `docs/production-readiness.md`(S2), ADR-0058, ADR-0056(config·wiring 토대),
> ADR-0018(단계 타임아웃 개념). 기존 백오프 패턴: `backend/app/llm.py`.

## 개요
단일 모듈 `backend/app/resilience.py`에 5개 결정적 유틸을 둔다: ① `CircuitBreaker`, ② `run_stage`
(단계 타임아웃+부분 폴백), ③ `ShutdownManager`(graceful 종료 훅), ④ `DegradedMode`(부분 폴백 플래그),
⑤ `retry`/`aretry`(공용 백오프). 외부 의존 없이 stdlib·asyncio만 사용한다. 시계·슬립·지터를 **주입**
가능하게 만들어 실시간 대기 없이 결정적으로 검증한다. 배선은 `wiring.register_shutdown`으로 종료 훅을
**등록만** 하고, `registry.py`에 import 한 줄(`# noqa: F401`)을 append해 모듈이 로드되게 한다.

## 아키텍처
```
api/internal.py ── registry import(부수효과) ── wiring.apply(app)
                                  │
                        app/platform/registry.py
                                  │ (append 1줄)
                          app/resilience.py ──register_shutdown──▶ wiring._SHUTDOWN
                                  │
   ┌────────────┬────────────┬────────────┬─────────────┐
CircuitBreaker  run_stage  ShutdownManager DegradedMode  retry/aretry
```
- 모듈 로드 시 `_RESILIENCE_ENABLED`(env `RESILIENCE_ENABLED`, 기본 off)가 켜져 있을 때만
  `wiring.register_shutdown(...)`로 graceful 훅을 건다. off면 등록 자체가 없어 회귀 불변.
- 유틸 클래스·함수는 import만으로 부수효과가 없다(서비스 코드가 명시적으로 인스턴스화·호출).

## 주요 컴포넌트 / 인터페이스

- **`CircuitState`** (Enum: CLOSED/OPEN/HALF_OPEN) + **`CircuitOpenError`(Exception)**. _(요구사항 1)_
- **`CircuitBreaker`**: 연속 실패 임계·복구 시간 기반 상태기계. _(요구사항 1)_
  - `__init__(failure_threshold=5, recovery_timeout=30.0, *, clock=time.monotonic)`
  - `call(fn, *a, **k)` / `acall(fn, *a, **k)` — 게이트 통과 시 실행, open이면 `CircuitOpenError`.
  - `allow()` → bool — open에서 recovery 경과 시 half-open 전환 후 True. `record_success()`/`record_failure()`.
  - `state` 프로퍼티(현재 상태, half-open 전이 반영).
- **`StageTimeout`(Exception)** + **`run_stage(coro_factory, timeout, *, fallback=_UNSET)`**. _(요구사항 2)_
  - `asyncio.wait_for` 래핑. timeout None/≤0이면 그대로 await(시한 없음). 폴백 주어지면 타임아웃 시 반환.
  - `coro_factory`는 `Callable[[], Awaitable]`(재시도/타임아웃마다 새 코루틴 생성 위함).
- **`ShutdownManager`**: LIFO best-effort 정리 실행기. _(요구사항 3)_
  - `register(fn)` — 동기/코루틴 콜백 등록. `run()`/`arun()` — 역순 실행, 예외는 수집·로그 후 계속.
  - 전역 인스턴스 `SHUTDOWN` + 모듈 함수 `on_shutdown(fn)`(서비스가 정리 콜백 등록).
- **`DegradedMode`**: 기능별 강등 플래그 집합. _(요구사항 4)_
  - `is_degraded(feature)`/`mark(feature)`/`clear(feature)`/`active()`. env `RESILIENCE_DEGRADED`
    (콤마구분)로 초기 집합. 전역 인스턴스 `DEGRADED`.
- **`retry(fn, *, attempts, base_delay, transient, sleep, jitter, ...)`** + **`aretry(...)`**. _(요구사항 5)_
  - 지수 백오프+지터. `transient` 튜플 외 예외는 즉시 전파. `sleep`·`jitter` 주입(테스트 결정성).
  - 기본 `transient=(Exception,)`, `jitter=random.random`. `llm.py`는 변경하지 않되(소유 밖),
    동일 알고리즘을 일반화해 중복을 새로 만들지 않는다.

## 데이터 모델
- `CircuitState`(Enum), `CircuitOpenError`/`StageTimeout`(Exception). 그 외는 평범한 카운터·집합·리스트.
- 상태는 인스턴스 내부에 보관(전역 가변 상태 최소화). 전역 싱글턴은 `SHUTDOWN`·`DEGRADED`뿐.

## 에러 처리
- 서킷 open: `CircuitOpenError`(호출자가 폴백·degraded 전환 가능).
- 단계 타임아웃: `StageTimeout`(폴백 미지정 시) — `asyncio.TimeoutError`를 감싸 의미 명확화.
- shutdown 콜백 예외: best-effort, 수집해 stderr/로그로 남기고 다음 콜백 진행(요구사항 3-2).
- retry: 모든 시도 실패 시 마지막 예외 재던짐. 비대상 예외 즉시 전파(요구사항 5-2).

## 테스트 전략 (`backend/tests/test_resilience.py`)
- **서킷브레이커**: 가짜 시계(mutable list/closure)로 closed→open(임계)→half-open(복구경과)→
  closed/open 전이를 결정적으로 검증. 동기·비동기 `call`/`acall`.
- **run_stage**: 즉시 완료/타임아웃→`StageTimeout`/타임아웃→폴백/`timeout=None` 바이패스.
  실제 대기 없이 작은 `asyncio.sleep`·짧은 timeout으로 빠르게. (전체 < 0.2s)
- **ShutdownManager**: LIFO 순서, 예외 발생해도 나머지 실행, 동기+코루틴 혼합.
- **DegradedMode**: 기본 off, mark/clear, env 초기화.
- **retry/aretry**: transient 재시도 후 성공, 전부 실패 시 재던짐, 비대상 즉시 전파, `sleep` 주입으로
  실대기 0. 호출 횟수·백오프 인자 검증.
- **회귀 불변**: `RESILIENCE_ENABLED` 미설정 시 wiring에 shutdown 훅이 등록되지 않음 확인.

## 설계 결정 / 대안
- **단일 모듈 vs 패키지**: 범위가 작아 `resilience.py` 단일 모듈로 응집. 추후 확장 시 분할 가능.
- **시계·슬립 주입**: 실시간 sleep은 느리고 비결정적 → DI로 제거(요구사항 6-1). `llm.py`는 실시간
  `time.sleep`을 쓰지만 소유 밖이라 손대지 않고, 본 유틸이 일반화 대체재를 제공.
- **`coro_factory` 사용**: 코루틴은 1회성이라 재시도·재시도 후 타임아웃에 새 코루틴이 필요 → 팩토리로 받음.
- **글로벌 1개 타임아웃 기각**: ADR-0018대로 단계별이 한 단계 지연이 전체를 막지 않음. `run_stage`는
  호출 단위 시한이라 단계별 조합이 자유롭다.
- **토글 off 기본**: 모듈 import는 부수효과 없음, 종료 훅 등록만 env 게이트. 회귀 완전 불변.
