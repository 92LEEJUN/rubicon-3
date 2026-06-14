# 작업 (Tasks) — 신뢰성/회복력(Resilience)

> `design.md` 를 실제 구현으로 나눈 체크리스트. 끝에 관련 요구사항 번호 표기.

## 작업 목록

- [x] 1. ADR-0058 작성 + `docs/adr/README.md`는 편집 금지(금지 규칙) — 인덱스는 main이 갱신 _(요구사항 6)_
- [x] 2. `backend/app/resilience.py` 신규 _(요구사항 1~5)_
  - [x] 2.1 `CircuitState`/`CircuitOpenError` + `CircuitBreaker`(clock 주입, call/acall/allow/record) _(요구사항 1)_
  - [x] 2.2 `StageTimeout` + `run_stage`(timeout·fallback·None 바이패스) _(요구사항 2)_
  - [x] 2.3 `ShutdownManager`(LIFO·best-effort·sync/async) + 전역 `SHUTDOWN`·`on_shutdown` _(요구사항 3)_
  - [x] 2.4 `DegradedMode`(env 초기화·mark/clear/is_degraded) + 전역 `DEGRADED` _(요구사항 4)_
  - [x] 2.5 `retry`/`aretry`(지수 백오프+지터·transient·sleep/jitter 주입) _(요구사항 5)_
  - [x] 2.6 `RESILIENCE_ENABLED`(기본 off) 게이트로 `wiring.register_shutdown` 등록 _(요구사항 3, 6)_
- [x] 3. `backend/app/platform/registry.py`에 import 한 줄 append(`# noqa: F401`) _(요구사항 6)_
- [x] 4. `backend/tests/test_resilience.py` — 전 컴포넌트 결정적 단위 테스트 _(요구사항 1~6)_
- [x] 5. 검증: 루트 `ruff check backend/` 클린 + `cd backend && python -m pytest` green _(요구사항 6)_

## 진행 메모
- 시계·슬립·지터는 전부 주입 가능하게 설계해 실시간 대기 0, 결정적.
- `coro_factory`(Callable[[], Awaitable])로 받아 재시도/타임아웃마다 새 코루틴 생성.
- `llm.py`는 소유 밖 — 손대지 않고 백오프 알고리즘만 `resilience.retry/aretry`로 일반화(중복 신설 금지).
- 토글 `RESILIENCE_ENABLED` 기본 off → shutdown 훅 미등록 = 회귀 불변.
