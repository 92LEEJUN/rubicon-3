# ADR-0062: 비용·캐싱(Cost & Caching) — LLM 비용 회계·모델 라우팅·예산 가드·응답 캐싱

- **상태**: 채택
- **관련**: [`specs/cost-caching/`](../../specs/cost-caching/requirements.md),
  [`docs/production-readiness.md`](../production-readiness.md)(S6 비용·캐싱·Well-Architected 비용 최적화),
  ADR-0034(provider-agnostic LLM + 모델 라우팅), ADR-0057(관측성 메트릭),
  ADR-0059(백킹서비스 `CachePort`+Mock), ADR-0056(환경 구성·배선 시임),
  [operations.md](../operations.md) §14(모델 라우팅·비용), [orchestration.md](../orchestration.md) §6.
- **비고**: ADR-0057의 `metrics.Metrics` 위에 LLM 비용 메트릭을, ADR-0059의 `CachePort`/`MockCache`
  위에 응답 캐시 래퍼를 얹는다(중복 구현 금지). 새 pip 의존성 없음(tiktoken 대신 stdlib 근사).

## 배경
프로덕션 준비도 S6(Well-Architected 비용 최적화)는 ⬜이다. MVP는 LLM 호출 비용을 **관측하지도,
상한을 두지도, 결정적 응답을 캐시하지도** 않는다. 구체적 갭:

1. **비용 가시성 부재** — 턴/세션당 토큰·비용 추정이 없어 `/metrics`로 비용 추세를 볼 수 없다.
2. **모델 라우팅 미구현** — ADR-0034가 "단순=경량 / 복잡=상위" 라우팅을 *결정*했으나 `llm.py`는
   단일 `MODEL` 상수만 쓴다. 비용/지연 균형을 코드로 강제할 헬퍼가 없다.
3. **예산 가드 없음** — 일/세션 비용 상한이 없어 폭주(런어웨이 루프·악성 입력)가 비용으로 직결된다.
4. **응답 캐시 미사용** — 결정적 응답(동일 입력)·플래너 결과를 매번 LLM에 재질의한다. S3가 `CachePort`를
   추가했으나 아무도 얹지 않았다.

제약(DoD·소유 경계): **새 무거운 pip 의존성 금지(stdlib 근사 토크나이저)**, **토글 기본 off=회귀
불변(스트랭글러)**, **S3 `CachePort`/`MockCache` 재사용(새 캐시 구현 금지)**, `llm.py`는 비용 계측만
추가하되 **기존 시그니처·동작 불변**, 앱 팩토리(`internal.py`)는 비편집(배선은 registry append).

## 결정
S6를 **4개 직교 컴포넌트**로 추가형 도입한다. 전부 토글 뒤(기본 off), Mock 허용.

- **① LLM 비용 회계(`cost/accounting.py`)** — stdlib 근사 토크나이저(`estimate_tokens`: 공백/구두점
  분할 + 문자수 기반 보정, tiktoken 미사용)로 prompt/completion 토큰을 추정하고, 모델별 단가표
  (`PRICES`: per-1K 토큰 USD, env override 가능)로 **턴당 비용**을 계산한다. `COST_TRACKING` on이면
  비용/토큰을 프로세스 누적기(`CostMetrics`)에 더해 Prometheus 규약(`rubicon_llm_cost_usd_total`·
  `rubicon_llm_tokens_total`·`rubicon_llm_calls_total`)으로 노출한다. **S1 `metrics.py`/`/metrics`는
  소유 밖이라 편집하지 않고**, ADR-0057 관측성 규약을 재사용하되 별도 엔드포인트 `/metrics/llm`(전용
  라우터, `wiring.register_router`)로 내보낸다(같은 텍스트 포맷·신규 시리즈 이름, 기존 시리즈 불변).
  off면 무동작(계측 0).
- **② 모델 라우팅 정책(`cost/routing.py`)** — ADR-0034 위에서 **결정적** 헬퍼 `route_model(complexity,
  size_hint)`를 둔다. 단순/대량 → 경량(`gpt-4o-mini`), 복잡 → 상위(`gpt-4o`). 입력만으로 결정(난수
  없음). `COST_TRACKING`/`MODEL_ROUTING` off면 기존 `llm.MODEL` 그대로(회귀 불변).
- **③ 예산 가드(`cost/budget.py`)** — `BudgetGuard`가 일/세션 누적 비용을 인메모리로 추적하고, 상한
  (`COST_DAILY_BUDGET_USD`·`COST_SESSION_BUDGET_USD`) 초과 시 **강등(상위→경량 라우팅 다운그레이드)**
  또는 **차단**(`allow()` False) 훅을 노출한다. off(상한 미설정)면 항상 허용. 결정·훅만 제공하고 호출
  강제는 하지 않는다(호출부가 선택적으로 소비 — 회귀 불변).
- **④ 응답 캐싱(`cache_layer.py`)** — S3 `CachePort`(`adapters/cache.py`)를 **재사용**하는 얇은 래퍼
  `ResponseCache`. 결정적 키(모델+정규화 messages 해시)로 응답/플래너 결과를 캐시하고 TTL·무효화
  (`invalidate(key)`·`clear()`)를 제공한다. 백엔드는 `repositories/backing.select_cache()`로 선택
  (기본 `NoopCache`=항상 미스=회귀 불변). `RESPONSE_CACHE` on + `CACHE_BACKEND=memory`일 때만 실제 캐시.
- **`llm.py` 계측(최소 침습)** — `chat_completion`/`achat_completion`은 시그니처·반환·재시도·세마포어
  로직 **불변**. 호출 성공 후 `cost.maybe_record(model, messages, response)`를 **한 줄** 호출해
  `COST_TRACKING` on일 때만 비용을 기록한다(off면 즉시 return = 무동작). 응답 파싱 실패는 조용히 무시
  (계측이 본로직을 깨지 않음).
- **배선은 시임으로만** — 비용 회계·라우팅·예산·캐시는 라이브러리(호출부가 import)다. 미들웨어 없음.
  비용 메트릭 노출 라우터(`cost/router.py`)만 `registry.py`에 **import 한 줄 append**(`# noqa: F401`)로
  로드해 `wiring.register_router`로 `/metrics/llm`을 부착한다. `internal.py`·`metrics.py`·`install.py`는
  비편집(앱 팩토리·S1 소유 불변).

> 본 ADR은 **비용 최적화 토대** 결정이다. 토글 기본 off라 메트릭·캐시·라우팅·가드는 동작을 바꾸지
> 않는다(응답·토큰 경로 불변). 실 단가 동기화·분산 캐시(Redis)·실시간 쿼터 차단은 후속(범위 외).

## 대안 / 기각
- **tiktoken 도입(정확 토큰)** — 정확하나 **무거운 pip 의존성·공급망 표면**(DoD 위반). **기각** —
  stdlib 근사로 비용 *추세*는 충분(절대 청구가 아닌 관측·가드 목적). 실 정산은 provider usage 필드로 후속.
- **새 캐시 구현(별도 dict/LRU)** — S3 `CachePort`와 중복·이중 진실. **기각** — `CachePort` 재사용,
  래퍼만 추가(키 정규화·무효화 정책).
- **모델 라우팅을 LLM에게 위임(메타 분류 호출)** — 비결정·추가 비용·지연. **기각** — 입력 기반 결정적 헬퍼.
- **예산 초과 시 항상 하드 차단** — UX 회귀(정상 사용자 차단). **기각** — 강등 우선 + 차단은 옵션 훅.
- **`llm.py` 호출부 전부를 라우팅으로 교체** — 광범위 변경·회귀 위험·소유 경계 밖. **기각** — `llm.py`는
  계측 한 줄만, 라우팅은 헬퍼 제공(호출부가 점진 채택).

## 영향
- **production-readiness.md** — S6(비용 최적화) 셀의 구조적 토대(메트릭·라우팅·가드·캐시) 마련. main이
  통합 시 ⬜→✅/🟡 갱신(본 ADR이 근거). 본 스트림은 해당 파일 비편집.
- **operations.md** §14 — 모델 라우팅·비용 캐싱의 운영 면(단가표·예산 상한·캐시 무효화)과 연결. 본 ADR이 근거.
- **계약** — 외부 노출 API/응답 봉투 **변경 없음**(런타임 내부 비용/캐시). `/metrics` 텍스트에 비용/토큰
  시리즈가 늘 뿐(표현 부가, 기존 필드 불변) → 3계층 동기화 불필요.
- **토글 env** — `COST_TRACKING`(비용 회계·메트릭)·`MODEL_ROUTING`(라우팅 활성)·`RESPONSE_CACHE`
  (응답 캐시), 전부 기본 off. 예산 상한 `COST_DAILY_BUDGET_USD`·`COST_SESSION_BUDGET_USD`(미설정=무제한),
  단가 override `LLM_PRICE_<MODEL>_IN`/`_OUT`(미설정=기본표). 캐시 백엔드는 ADR-0059 `CACHE_BACKEND` 재사용.
