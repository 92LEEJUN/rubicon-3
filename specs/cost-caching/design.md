# 설계 (Design) — S6 비용·캐싱(Cost & Caching)

> 참조 기반 문서: [ADR-0062](../../docs/adr/0062-cost-caching.md)(본 스트림 결정),
> [ADR-0034](../../docs/adr/0034-provider-agnostic-llm.md)(모델 라우팅),
> [ADR-0057](../../docs/adr/0057-observability.md)(메트릭),
> [ADR-0059](../../docs/adr/0059-backing-services.md)(`CachePort`+Mock),
> [ADR-0056](../../docs/adr/0056-environment-config-baseline.md)(환경 구성·배선 시임),
> [docs/production-readiness.md](../../docs/production-readiness.md)(S6).
> 공유 데이터 모델·아키텍처는 기반 문서를 따르고, 여기서는 **비용·캐싱 고유 설계**만 담는다.

## 개요
LLM 비용 회계·모델 라우팅·예산 가드·응답 캐싱을 **추가형**으로 도입한다. 전부 토글 뒤(기본 off)이며,
stdlib 근사 토크나이저와 S3 `CachePort` 재사용으로 새 무거운 의존성 없이 구현한다. `llm.py`는 계측
한 줄만 추가하고 시그니처·동작은 불변(회귀 불변).

## 아키텍처
```
                         env 토글 (COST_TRACKING / MODEL_ROUTING / RESPONSE_CACHE)
                                    │
   ┌──────────────┬────────────────┼───────────────────┬─────────────────┐
   ▼              ▼                ▼                   ▼                 ▼
cost/accounting  cost/routing    cost/budget        cache_layer       llm.py
estimate_tokens  route_model     BudgetGuard        ResponseCache     chat_completion
estimate_cost    (결정적)        (일/세션 상한)     get_or_compute    (계측 1줄)
maybe_record ───▶ metrics.Metrics(ADR-0057)         │
   │              rubicon_llm_cost_usd_total         ▼
   │              rubicon_llm_tokens_total      backing.select_cache()  ← ADR-0059
   ▼                                                 │  (재사용, 새 저장소 X)
PRICES(단가표, env override)                    CachePort: MockCache / NoopCache
```
- `cost/`는 패키지. `accounting`(토큰·비용·메트릭 기록)·`routing`(모델 선택)·`budget`(예산 가드).
- `cache_layer.py`는 S3 `CachePort` **위의 얇은 래퍼**. 백엔드 인스턴스는 `select_cache()`로 주입.
- `llm.py`는 호출 성공 후 `accounting.maybe_record(...)` 한 줄 — off면 즉시 return.

## 주요 컴포넌트 / 인터페이스

### 1. 비용 회계 — `cost/accounting.py` (요구사항 1, 5)
- `estimate_tokens(text: str) -> int` — stdlib 근사. 단어/구두점 토큰 분할 카운트와 문자수/4
  추정의 최대값(보수적). 빈 문자열=0. tiktoken 미사용.
- `estimate_messages_tokens(messages) -> int` — OpenAI chat 포맷(role+content)을 합산(+role 오버헤드).
- `PRICES: dict[str, ModelPrice]` — per-1K 토큰 (in, out) USD 기본표. `_price_for(model)`이
  env override(`LLM_PRICE_<MODEL>_IN`/`_OUT`, 모델명 대문자·`-`/`.`→`_`)를 우선 적용. 미지 모델은
  경량 단가로 폴백.
- `estimate_cost(model, prompt_tokens, completion_tokens) -> float` — `(in*pt + out*ct)/1000`.
- `maybe_record(model, messages, response, *, session_id=None) -> CostRecord | None` —
  `COST_TRACKING` off면 즉시 `None`. on이면: response의 `usage`(있으면 정확) 또는 추정 토큰으로
  비용을 계산해 프로세스 `CostMetrics`에 누적하고, `BudgetGuard`에 비용을 더한다. 파싱 실패는
  try/except로 조용히 무시(요구사항 5.2).
- `CostMetrics`(프로세스 단일 누적기, Lock)는 `rubicon_llm_cost_usd_total`·
  `rubicon_llm_tokens_total{kind=prompt|completion}`·`rubicon_llm_calls_total` 시리즈를 Prometheus
  텍스트(version 0.0.4)로 노출한다. **S1 `metrics.py`/`/metrics`는 소유 밖이라 편집하지 않고**,
  전용 라우터 `cost/router.py`가 `/metrics/llm`으로 내보낸다(`wiring.register_router`, registry append).

### 2. 모델 라우팅 — `cost/routing.py` (요구사항 2)
- `LIGHT_MODEL`(`gpt-4o-mini`)·`HEAVY_MODEL`(`gpt-4o`) 상수(env override 가능).
- `route_model(complexity: str = "simple", *, size_hint: int = 0) -> str` — `MODEL_ROUTING` off면
  `llm.MODEL` 반환(회귀). on이면: `complexity in {"complex","heavy"}` and `size_hint < BIG_THRESHOLD`
  → HEAVY, 그 외(단순·대량) → LIGHT. 입력만으로 결정(결정적·난수 없음).

### 3. 예산 가드 — `cost/budget.py` (요구사항 3)
- `BudgetGuard(daily_usd=None, session_usd=None, now_fn=…)` — 인메모리 누적. `add(session_id, cost)`로
  일·세션 누적 갱신(날짜 경계 시 일 리셋). `allow(session_id) -> bool`(하드 상한 초과 시 False),
  `should_downgrade(session_id) -> bool`(소프트 상한[상한의 일정 비율] 초과 시 True). 상한 미설정이면
  항상 allow=True·downgrade=False(무제한, 회귀). env(`COST_DAILY_BUDGET_USD`·`COST_SESSION_BUDGET_USD`)로
  구성하는 `default_guard()` 팩토리(프로세스 단일).

### 4. 응답 캐싱 — `cache_layer.py` (요구사항 4)
- `make_key(model, messages, *, namespace="resp") -> str` — 모델+정규화 messages를 JSON 직렬화 후
  sha256. 결정적.
- `ResponseCache(cache: CachePort | None = None, ttl: float | None = None)` — `cache` 미지정 시
  `backing.select_cache()`로 주입(기본 NoopCache=미스). `get_or_compute(model, messages, compute) ->`:
  `RESPONSE_CACHE` off면 항상 `compute()`. on이면 키로 get→히트면 반환, 미스면 `compute()` 후 set(ttl).
  `invalidate(key)`·`clear()`로 무효화. **새 저장소 없음 — `CachePort` 재사용**(요구사항 4.6).

### 5. `llm.py` 계측 (요구사항 1, 5)
- `chat_completion`/`achat_completion`은 기존 로직 유지. `return get_client()...create(**kwargs)`를
  `resp = ...; _maybe_cost(kwargs, resp); return resp` 형태로 바꾸되, `_maybe_cost`는 지연 import한
  `cost.accounting.maybe_record`를 try/except로 감싼다(off면 무동작, 실패면 무시). 시그니처·반환 불변.

## 데이터 모델
- `ModelPrice(in_per_1k: float, out_per_1k: float)`(frozen dataclass).
- `CostRecord(model, prompt_tokens, completion_tokens, cost_usd)`(frozen dataclass).
- 메트릭은 ADR-0057 `Metrics` 인스턴스에 비용/토큰 누적 필드 추가(공유 인스턴스 `get_shared()`).

## 에러 처리
- 비용 계측 전 구간은 try/except로 감싸 **본 LLM 경로를 절대 깨지 않는다**(요구사항 5.2).
- 단가 미지 모델·usage 누락은 추정/폴백으로 처리(예외 없음).
- 캐시 백엔드가 NoopCache면 자연히 미스(예외 없음).

## 테스트 전략 (`backend/tests/test_cost_caching.py`)
- **토큰/비용**: 근사 추정 단조성·빈 문자열 0·단가표/override·usage 우선 경로.
- **라우팅**: off=기본 모델, on=단순/대량 경량·복잡 상위·결정성(동일 입력 동일 출력).
- **예산**: 누적·세션/일 상한 차단·강등·일 리셋(주입 시계)·상한 미설정=무제한.
- **캐시**: 키 결정성·히트/미스·TTL·무효화·off/Noop=항상 compute·`CachePort` 재사용 확인.
- **메트릭**: `COST_TRACKING` on에서 prometheus 텍스트에 비용/토큰 시리즈 노출, off=무동작.
- **회귀**: 토글 off에서 `chat_completion` 시그니처·동작 불변(Mock client 주입), 계측 예외 격리.
