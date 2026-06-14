# 요구사항 (Requirements) — S6 비용·캐싱(Cost & Caching)

## 개요
LLM 호출 비용을 **관측·제어·절감**한다(Well-Architected 비용 최적화). 토큰/비용 추정과 메트릭 노출,
결정적 모델 라우팅, 예산 상한 가드, 결정적 응답 캐싱을 추가형으로 도입한다. 전부 **토글 기본 off =
회귀 불변**(스트랭글러)이며, 새 무거운 의존성 없이 stdlib 근사와 S3 `CachePort` 재사용으로 구현한다.

> 참조: [ADR-0062](../../docs/adr/0062-cost-caching.md)(본 스트림 결정), ADR-0034(모델 라우팅),
> ADR-0057(메트릭), ADR-0059(`CachePort`).

## 요구사항 목록

### 요구사항 1: LLM 비용 회계 + 메트릭 노출

**User Story:**
운영자로서, 턴/세션당 LLM 토큰·비용 추정을 메트릭으로 보고 싶다, 그래서 비용 추세를 추적하고
이상 폭증을 조기에 감지할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 텍스트가 주어지면 THEN 시스템은 stdlib만으로 토큰 수를 **근사 추정**해야 한다 (SHALL). (tiktoken 등 무거운 의존성 미사용)
2. WHEN 모델·prompt·completion이 주어지면 THEN 시스템은 모델별 단가표로 **턴당 비용(USD)**을 산출해야 한다 (SHALL).
3. WHEN `COST_TRACKING` on이고 LLM 호출이 성공하면 THEN 시스템은 비용·토큰을 메트릭(`rubicon_llm_cost_usd_total`·`rubicon_llm_tokens_total`)에 누적해야 한다 (SHALL).
4. IF `COST_TRACKING` off THEN 시스템은 비용 계측을 수행하지 않아야 한다(무동작·메트릭 0, 회귀 불변) (SHALL).
5. WHEN 단가 override env(`LLM_PRICE_<MODEL>_IN/_OUT`)가 주어지면 THEN 시스템은 기본 단가 대신 그 값을 사용해야 한다 (SHALL).

### 요구사항 2: 결정적 모델 라우팅 정책

**User Story:**
개발자로서, 단순/대량 요청은 경량 모델로, 복잡 요청은 상위 모델로 결정적으로 라우팅하고 싶다,
그래서 비용/지연을 균형 있게 최적화할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 복잡도·크기 힌트가 주어지면 THEN 시스템은 **결정적으로**(난수 없이) 모델 이름을 선택해야 한다 (SHALL).
2. WHEN 복잡도가 단순이거나 입력이 대량이면 THEN 시스템은 **경량 모델**을 선택해야 한다 (SHALL).
3. WHEN 복잡도가 복잡이면 THEN 시스템은 **상위 모델**을 선택해야 한다 (SHALL).
4. IF `MODEL_ROUTING` off THEN 시스템은 기존 기본 모델(`llm.MODEL`)을 반환해야 한다(회귀 불변) (SHALL).

### 요구사항 3: 예산 가드(일·세션 상한)

**User Story:**
운영자로서, 일·세션 비용 상한을 두고 초과 시 강등 또는 차단하고 싶다,
그래서 비용 폭주(런어웨이 루프·악성 입력)를 막을 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 호출 비용이 기록되면 THEN 시스템은 일·세션 누적 비용을 갱신해야 한다 (SHALL).
2. IF 세션/일 누적이 상한을 초과하면 THEN 시스템은 상위 모델을 경량으로 **강등**하는 결정을 노출해야 한다 (SHALL).
3. IF 누적이 하드 상한을 초과하면 THEN 시스템은 `allow()`로 **차단**을 신호할 수 있어야 한다 (SHALL).
4. IF 상한이 미설정(`COST_*_BUDGET_USD` 없음)이면 THEN 시스템은 항상 허용해야 한다(무제한, 회귀 불변) (SHALL).
5. WHILE 날짜가 바뀌면 시스템은 일 누적을 리셋해야 한다 (SHALL).

### 요구사항 4: 응답 캐싱(S3 CachePort 재사용) + 무효화

**User Story:**
개발자로서, 결정적 응답·플래너 결과를 캐시하고 무효화하고 싶다,
그래서 동일 입력의 중복 LLM 호출을 줄여 비용·지연을 절감할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 모델+정규화된 messages가 주어지면 THEN 시스템은 **결정적 캐시 키**를 산출해야 한다 (SHALL).
2. WHEN `RESPONSE_CACHE` on이고 캐시 히트면 THEN 시스템은 LLM 재호출 없이 캐시 값을 반환해야 한다 (SHALL).
3. WHEN 캐시 미스면 THEN 시스템은 계산 콜백 결과를 TTL과 함께 저장해야 한다 (SHALL).
4. WHEN `invalidate(key)`/`clear()`가 호출되면 THEN 시스템은 해당/전체 항목을 무효화해야 한다 (SHALL).
5. IF `RESPONSE_CACHE` off 또는 백엔드가 `NoopCache`면 THEN 시스템은 항상 콜백을 실행해야 한다(캐시 미동작, 회귀 불변) (SHALL).
6. WHEN 캐시를 구성할 때 THEN 시스템은 **S3 `CachePort`(`adapters/cache.py`)를 재사용**해야 하며 새 캐시 저장소를 만들지 않아야 한다 (SHALL).

### 요구사항 5: 회귀 불변(스트랭글러)

**User Story:**
유지보수자로서, 모든 비용·캐싱 기능이 토글 뒤에 있길 원한다, 그래서 토글 off면 기존 동작·테스트가 그대로 통과한다.

**수용기준 (Acceptance Criteria):**
1. WHEN 모든 신규 토글이 off(기본)면 THEN `llm.chat_completion`/`achat_completion`의 시그니처·반환·동작은 변하지 않아야 한다 (SHALL).
2. WHEN 비용 계측 중 응답 파싱이 실패하면 THEN 시스템은 조용히 무시하고 본 로직을 깨지 않아야 한다 (SHALL).
3. WHEN 본 스트림이 머지되면 THEN 기존 백엔드 테스트 스위트가 전부 green이어야 한다 (SHALL).
