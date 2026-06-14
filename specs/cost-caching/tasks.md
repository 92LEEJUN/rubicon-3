# 작업 (Tasks) — S6 비용·캐싱(Cost & Caching)

> `design.md`를 실제 구현으로 나눈 체크리스트. 끝의 괄호는 관련 요구사항 번호.

## 작업 목록

- [x] 1. ADR-0062 + 인덱스 append + specs 3종 작성 _(요구사항 전체)_
- [x] 2. 비용 회계 `cost/accounting.py` _(요구사항 1, 5)_
  - [x] 2.1 `estimate_tokens`/`estimate_messages_tokens`(stdlib 근사)
  - [x] 2.2 `PRICES` 단가표 + env override `_price_for`
  - [x] 2.3 `estimate_cost` + `CostRecord`
  - [x] 2.4 `CostMetrics`(프로세스 누적) + `/metrics/llm` 라우터(`cost/router.py`) + registry append
  - [x] 2.5 `maybe_record`(토글·usage 우선·예외 격리·예산 연동)
- [x] 3. 모델 라우팅 `cost/routing.py` _(요구사항 2)_
  - [x] 3.1 LIGHT/HEAVY 상수(env override) + `route_model` 결정적 헬퍼
- [x] 4. 예산 가드 `cost/budget.py` _(요구사항 3)_
  - [x] 4.1 `BudgetGuard`(일/세션 누적·날짜 리셋·allow/should_downgrade)
  - [x] 4.2 `default_guard()` env 팩토리(프로세스 단일)
- [x] 5. 응답 캐싱 `cache_layer.py` _(요구사항 4)_
  - [x] 5.1 `make_key`(결정적 sha256) + `ResponseCache`(CachePort 재사용)
  - [x] 5.2 `get_or_compute`·`invalidate`·`clear`(토글·Noop=항상 compute)
- [x] 6. `llm.py` 계측 한 줄(`_maybe_cost`, 시그니처·동작 불변·예외 격리) _(요구사항 1, 5)_
- [x] 7. 테스트 `backend/tests/test_cost_caching.py` 작성 _(요구사항 1~5)_
- [x] 8. 검증: `ruff check backend/` 클린 + `cd backend && python -m pytest` 전부 green _(요구사항 5)_

## 진행 메모
- 배선: 비용/캐시는 라이브러리(호출부 import). 미들웨어 없음. 비용 메트릭 노출 라우터(`cost/router.py`)만 `registry.py`에 import 1줄 append(`# noqa: F401`) → `/metrics/llm` 부착. `internal.py`·S1 `metrics.py`/`install.py` 비편집.
- `llm.py` 수정 범위: `chat_completion`·`achat_completion` 반환 직전 `_maybe_cost(kwargs, resp)` 1줄씩 + 모듈 하단 `_maybe_cost` 헬퍼. 기존 시그니처·재시도·세마포어 불변.
- 토글명: `COST_TRACKING`·`MODEL_ROUTING`·`RESPONSE_CACHE`(전부 off 기본). 예산 `COST_DAILY_BUDGET_USD`·`COST_SESSION_BUDGET_USD`. 단가 `LLM_PRICE_<MODEL>_IN/_OUT`. 캐시 백엔드는 ADR-0059 `CACHE_BACKEND` 재사용.
- 메트릭은 ADR-0057 `Metrics`에 비용/토큰 누적 필드 추가(공유 인스턴스). 기존 시리즈 불변.
