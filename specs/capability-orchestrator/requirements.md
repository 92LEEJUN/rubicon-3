# 요구사항 (Requirements)

## 개요

오케스트레이터를 **단일 capability 기반 구조로 수렴**하되, **조언형/행동형을 분리**해 판매·수리기사 접수 같은 고위험 행동이 **자동으로 라우팅되지 않도록** 한다. 현재 서빙 경로는 결정적 백본([core.Orchestrator](../../backend/app/orchestrator/core.py))과 LLM 멀티에이전트([runtime](../../backend/app/orchestrator/runtime.py))가 토글로 **이원 공존**한다. 이 작업은 둘을 **하나의 오케스트레이터 + capability 레지스트리**로 합치고, "플래너가 **조언형 capability만** 자동 선택 → 정보+CTA 산출 → 되돌릴 수 없는 행동은 **CTA 확정→ActionGate**로만"의 골격으로 만든다.

근거·결정은 기반 문서를 참조한다 — **통합 [ADR-0043](../../docs/adr/0043-capability-orchestrator.md), 추천 agent [ADR-0044](../../docs/adr/0044-recommend-as-agent.md), capability 상세 [ADR-0045](../../docs/adr/0045-capability-structure-detail.md), 조언형/행동형+CTA 브릿지 [ADR-0046](../../docs/adr/0046-advisory-action-cta-bridge.md), [docs/agents.md](../../docs/agents.md) §11·§12**. 추천 도메인은 [specs/product-recommendation/](../product-recommendation/)에 위임한다.

**비범위:** 턴 내 병렬 실행 보류([ADR-0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md)) — `parallel_group` 표기만, 실행 순차. 클라이언트 계약([api-contract](../../docs/api-contract.md) §2.1)·응답 템플릿([response-templates](../../docs/response-templates.md))·도메인 모델은 **불변**(FE 회귀 금지).

## 요구사항 목록

### 요구사항 1: capability 레지스트리 (조언형/행동형 분류)

**User Story:** 운영자로서, 오케스트레이터가 다룰 capability를 한 곳의 레지스트리로 선언하기를 원한다, 그래서 새 capability 추가가 한 엔트리로 끝나고 조언형/행동형 구분이 명시된다.

**수용기준:**
1. WHEN 오케스트레이터가 초기화되면 THEN 시스템은 capability를 `{name: Capability(class=advisory|action, kind=agent|tool, intents, emits, needs, priority, tools, prompt?)}` 레지스트리로 보유해야 한다 (SHALL). ([ADR-0046](../../docs/adr/0046-advisory-action-cta-bridge.md))
2. WHEN 새 capability를 추가할 때 THEN 시스템은 한 엔트리 등록만으로 플래너 후보·실행에 반영해야 한다 (SHALL).
3. IF capability가 `class=action`(order·booking·handoff)이면 THEN 시스템은 플래너 자동 선택 후보에서 제외하고 **CTA 확정 회신으로만** 진입시켜야 한다 (SHALL).

### 요구사항 2: 균일 인터페이스 + 2채널 출력

**User Story:** 개발자로서, 모든 capability가 동일한 입출력 계약을 따르기를 원한다, 그래서 오케스트레이터가 같은 방식으로 실행·병합한다.

**수용기준:**
1. WHEN 어떤 capability가 실행되면 THEN 시스템은 균일 인터페이스 `call(input, ctx) → AsyncIterator[chunk]`로 호출해야 한다 (SHALL).
2. WHEN 청크를 방출할 때 THEN 시스템은 [api-contract](../../docs/api-contract.md) §2.1 봉투의 **2채널**(`delta` 자유 내러티브 + `section` 구조화 아티팩트)만 사용해야 한다 (SHALL). ([ADR-0045](../../docs/adr/0045-capability-structure-detail.md))
3. WHEN `delta`를 생성할 때 THEN 시스템은 프롬프트 포함 규율(근거·출처 R16·위험 R23·추천근거 R8)을 따르고 금지 규율(가격·사양·재고·해결책 날조 / 시스템·대기·순번 / 동의 밖·민감 R19 / 무확인 커밋)을 위반하지 않아야 한다 (SHALL).
4. WHEN 구조화 아티팩트(카드·리스트·CTA·`confirmation`)를 낼 때 THEN 시스템은 `section`(Template)으로 내어 FE 렌더·CTA·커밋 게이트를 보존해야 한다 (SHALL). ([response-templates](../../docs/response-templates.md))

### 요구사항 3: 조언형/행동형 분리 — 자동 커밋·디스패치 금지 (핵심)

**User Story:** 사용자로서, 진단·추천을 받을 때 시스템이 멋대로 결제·기사 접수로 넘어가지 않기를 원한다, 그래서 고위험 행동은 내가 직접 선택한다.

**수용기준:**
1. WHEN 자유텍스트 턴을 처리할 때 THEN 시스템은 **조언형 capability만** 실행하고 정보 + CTA까지만 산출해야 한다 (SHALL). ([ADR-0046](../../docs/adr/0046-advisory-action-cta-bridge.md))
2. IF 응답이 되돌릴 수 없는 행동(주문·예약·기사 접수)을 포함하면 THEN 시스템은 **CTA 확정 회신 + ActionGate(R17/409)** 를 거치기 전에 실행하지 않아야 한다 (SHALL). ([ADR-0033](../../docs/adr/0033-action-gate.md))
3. WHEN 행동 CTA 확정 회신을 받으면 THEN 시스템은 LLM 플래너를 거치지 않고 **payload(action·id) 기반으로 결정적으로** 해당 행동 capability + ActionGate로 라우팅해야 한다 (SHALL).
4. IF 사용자가 자유텍스트로 명시적 행동("주문해줘")을 요청하면 THEN 시스템은 **자동 커밋하지 않고** 초안(`confirmation`/`product_card`) + 확정 CTA를 산출해 ActionGate로 보내야 한다 (SHALL).
5. WHEN 제품/부품 카드(`product_card`·`recommendation_list`)를 **표시하는 시점에** THEN 시스템은 해당 항목의 행동 CTA(`add_to_cart`·`order`)를 **카드에 함께 동봉**해야 한다 (SHALL). 그래야 이후 "주문해줘" 발화가 재확인 마찰 없이 기존 CTA 탭으로 이어진다. ([ADR-0046](../../docs/adr/0046-advisory-action-cta-bridge.md))

### 요구사항 4: LLM 플래너 + 룰 검증/폴백

**User Story:** 운영자로서, 플래너가 의도·맥락에 따라 조언형 capability를 동적 선택하되 안전하게 검증되기를 원한다.

**수용기준:**
1. WHEN 자유텍스트 턴이 들어오면 THEN 시스템은 LLM 플래너로 `Plan{steps:[{capability, depends_on, parallel_group}]}`을 제안해야 한다 (SHALL). 후보는 **조언형 capability**로 한정한다.
2. WHEN plan을 받으면 THEN 시스템은 룰로 검증 — 레지스트리 존재·사이클 금지·우선순위(안전·CS 먼저, [mvp-concierge/design.md](../mvp-concierge/design.md) §6.6)·**행동형 자동선택 차단** — 해야 한다 (SHALL).
3. IF plan이 비었거나 무효면 THEN 시스템은 규칙 매핑으로 폴백해야 한다 (SHALL).
4. IF 안전 의도(R23 위험)인데 plan에 진단/경고 capability가 없으면 THEN 시스템은 이를 **누락으로 보정**(필수 capability 강제 포함)해야 한다 (SHALL).
5. WHEN 검증된 plan을 실행할 때 THEN 시스템은 `depends_on` 순서를 지키고 실행은 순차 유지해야 한다 (SHALL). ([ADR-0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md))

### 요구사항 5: turn 블랙보드

**User Story:** 개발자로서, capability 산출을 의존 capability·CTA 게이팅이 이어받기를 원한다.

**수용기준:**
1. WHEN capability가 실행될 때 THEN 시스템은 턴 스코프 블랙보드(`ctx`)를 스코프 주입(전체 이력 금지)해야 한다 (SHALL).
2. WHEN capability가 산출(`required_parts`·`device_status`·`candidates`·`risk_level`·`warranty_status`·`repair_cost`)을 내면 THEN 시스템은 블랙보드에 write해야 한다 (SHALL).
3. IF CTA 게이팅·의존 capability가 선행 산출을 필요로 하면 THEN 시스템은 블랙보드에서 read해 이어받아야 한다 (SHALL). (기존 `carried_parts` 일반형)

### 요구사항 6: 수리 해결 경로 — 자가진단 + 위험도·보증 게이팅 CTA

**User Story:** 사용자로서, 고장 시 자가진단 가이드를 받고 필요하면 상담원·수리기사로 **내가 선택해** 넘어가기를 원한다, 그래서 불필요·위험한 자가수리나 자동 접수를 피한다.

**수용기준:**
1. WHEN 수리/진단 의도면 THEN 시스템은 `diagnose`(조언형)로 `guide_steps`(자가진단) + `required_parts`를 산출해야 한다 (SHALL).
2. WHEN 해결 가이드를 제시할 때 THEN 시스템은 끝에 CTA `connect_agent`(상담원)·`request_visit`(수리기사 접수)를 제공해야 한다 (SHALL). ([response-templates](../../docs/response-templates.md) `handoff_card`·`booking`)
3. IF 해결책이 **안전 위험**(R23)이거나 기기가 **보증 중**(R22)이면 THEN 시스템은 **부품 자가주문 CTA(`add_to_cart`)를 숨기고** 상담원/수리기사 CTA만 노출해야 한다 (SHALL). 이때 시스템은 **버튼을 숨긴 이유를 짧은 설명 문구로 동반**해야 한다("이 증상은 직접 수리가 위험해 전문 점검을 권해요" / "보증 기간 내라 무상 수리 대상이에요"). 버튼만 사라져 생기는 혼란을 막는다. ([ADR-0046](../../docs/adr/0046-advisory-action-cta-bridge.md))
4. IF 단순·안전한 부품 교체 건이면 THEN 시스템은 `add_to_cart` CTA를 함께 제공하되 **커밋은 ActionGate**를 거쳐야 한다 (SHALL).

### 요구사항 7: 수리↔교체 브릿지 — 비경제일 때만 중립 CTA

**User Story:** 사용자로서, 수리비가 과할 때만 교체 선택지를 중립적으로 보고 스스로 판단하기를 원한다, 그래서 원치 않는 판매 푸시를 받지 않는다.

**수용기준:**
1. IF 진단이 **수리 불가/비경제**(수리비 ≥ 교체가 임계, 또는 반복 고장)로 판정되면 THEN 시스템은 중립 "교체 알아보기" CTA를 1개 추가해야 한다 (SHALL).
2. IF 수리가 경제적이면 THEN 시스템은 교체 추천 CTA를 **추가하지 않아야** 한다 (SHALL).
3. WHEN 교체 선택지를 제시할 때 THEN 시스템은 수리/교체 **판단을 단정하지 않고** 사용자 선택으로 남겨야 한다 (SHALL). (판매 푸시·과잉판매 금지, [llm-policy](../../docs/llm-policy.md))

### 요구사항 8: 제품 추천 통합 (RecommendationService 위임 · 선제/반응형)

**User Story:** 사용자로서, 추천이 동의·보유기기·관심·근거를 반영하고 선제/요청 모두에서 일관되기를 원한다.

**수용기준:**
1. WHEN 추천을 산출할 때 THEN 시스템은 `recommend` capability가 기존 `RecommendationService`(개인화 랭킹·동의 scope 폴백·보유/중복 제외·근거 부착)에 위임해야 한다 (SHALL). ([specs/product-recommendation/](../product-recommendation/))
2. WHEN 추천을 제시할 때 THEN 시스템은 `recommendation_list` + 각 항목 근거 + CTA까지(조언형)만 내고 구매는 별도 ActionGate를 거쳐야 한다 (SHALL).
3. IF `personalization` 동의가 없으면 THEN 시스템은 일반 추천으로 폴백하고 제한적임을 고지해야 한다 (SHALL). ([product-recommendation](../product-recommendation/) 요구 4)
4. WHEN 선제 추천 트리거(소모품 수명·구매 주기)가 발생하면 THEN 시스템은 `RecommendationTrigger` + 컴패니언 게이트(ADR-0042)를 재사용해 선제 진입을 흡수해야 한다 (SHALL).
5. WHEN 추천이 노출·클릭→주문으로 이어지면 THEN 시스템은 `correlation_id` 전환 기여를 보존해야 한다 (SHALL). ([analytics](../../docs/analytics.md) §5)

### 요구사항 9: 복합 쿼리 처리

**User Story:** 사용자로서, 한 번에 여러 요청을 해도 누락·억지 판단 없이 각각 적절히 처리되기를 원한다.

**수용기준:**
1. WHEN 복합 의도면 THEN 시스템은 조언형 capability를 우선순위(안전·CS 먼저)로 fan-out하고 의도별 `MessageSection`(handled/unhandled 표기)으로 묶어야 한다 (SHALL). (R7)
2. WHEN capability를 가로지르는 결정(예: 수리 vs 교체)이 필요하면 THEN 시스템은 **CTA 선택지로 제시**하고 LLM이 평결을 내리지 않아야 한다 (SHALL). ([ADR-0046](../../docs/adr/0046-advisory-action-cta-bridge.md))
3. IF capability 산출이 서로 충돌(예: 부품 단종)하면 THEN 시스템은 조언형은 CTA까지만 두고, **충돌 해소를 행동 CTA 턴으로 지연**해 폴백 CTA(상담원/대체)로 처리해야 한다 (SHALL).
4. WHEN 복합 산출을 병합할 때 THEN 시스템은 부분 실패 capability를 unhandled로 표기하고 나머지를 반환해야 한다 (SHALL). (R13)

### 요구사항 10: 하이브리드 병합 (연결문구만, 판단 금지)

**User Story:** 사용자로서, 여러 산출이 매끄러운 응답으로 합쳐지되 없는 판단이 끼지 않기를 원한다.

**수용기준:**
1. WHEN 산출을 병합할 때 THEN 시스템은 근거(섹션)를 결정적으로 보존하고 우선순위 스택으로 배치해야 한다 (SHALL).
2. WHEN 섹션을 이을 때 THEN 시스템은 연결문구(인트로/전환)만 얇은 LLM `delta`로 생성하고 **섹션 사실을 바꾸거나 새 판단·평결을 만들지 않아야** 한다 (SHALL).

### 요구사항 11: 다단계 스트리밍

**수용기준:**
1. WHEN 턴이 시작되면 THEN 시스템은 빠른 결정적 산출(`device_status` 등)을 먼저 방출(첫 섹션 ≤ 2~3s)해야 한다 (SHALL). ([operations](../../docs/operations.md) §14)
2. WHILE capability가 실행되는 동안 시스템은 plan 순서대로 `section`/`delta`를 점진 방출해야 한다 (SHALL).
3. WHEN 진행 문구를 낼 때 THEN 시스템은 답변 중심 문구만 쓰고 시스템·대기·순번을 노출하지 않아야 한다 (SHALL). ([operations](../../docs/operations.md) §11)

### 요구사항 12: 조건부 리뷰 + 커밋 안전

**수용기준:**
1. IF 응답이 안전(R23)·커밋(R17)·불확실(R16) 중 하나면 THEN 시스템은 최종 직전 Review를 발동해야 한다 (SHALL). 불확실/안전은 **결정적 신호**(tool 근거 부재·`risk_level`)로 탐지해야 한다 (SHALL). ([ADR-0011](../../docs/adr/0011-conditional-review.md))
2. IF 위 조건이 아니면 THEN 시스템은 Review를 스킵해야 한다 (SHALL).
3. WHEN 되돌릴 수 없는 커밋을 처리할 때 THEN 시스템은 `confirmation`/`booking` 확정 + ActionGate(409)로 보장하고 스트림을 버퍼링하지 않아야 한다 (SHALL).
4. IF Review가 위반을 발견하면 THEN 시스템은 보정/차단·사람 연결로 처리하고 재계획 루프를 돌리지 않아야 한다 (SHALL). ([ADR-0012](../../docs/adr/0012-single-pass.md))

### 요구사항 13: 토글 수렴 (이원 공존 → 단일 경로)

**수용기준:**
1. WHEN capability를 실행할 때 THEN 시스템은 토글을 **capability 단위 LLM-backed 여부**로 평가(매 호출 env 반영)해야 한다 (SHALL).
2. IF 모든 LLM capability가 꺼져 있으면 THEN 시스템은 결정적 tool capability만으로 기존 결정적 경로와 동등한 봉투를 내야 한다 (SHALL). (회귀 금지)
3. WHEN 어느 토글 상태든 THEN 시스템은 동일한 §2.1 봉투를 방출해야 한다 (SHALL).

### 요구사항 14: 단계별 실패·부분 폴백

**수용기준:**
1. IF 한 capability step이 실패면 THEN 시스템은 그 step만 폴백/생략하고 부분결과를 반환해야 한다 (SHALL). (R13)
2. IF 플래너 LLM이 실패면 THEN 시스템은 규칙 폴백 plan으로 계속해야 한다 (SHALL).
3. WHEN 턴 전체가 회복 불가면 THEN 시스템은 `error` 봉투를 방출하고 대화를 중단하지 않아야 한다 (SHALL).

### 요구사항 15: Mock/결정적 테스트 가능성

**수용기준:**
1. WHEN 플래너를 테스트할 때 THEN 시스템은 plan 스텁 주입으로 검증·폴백·**행동형 자동선택 차단**을 LLM 없이 단언할 수 있어야 한다 (SHALL).
2. WHEN 수리 CTA 게이팅을 테스트할 때 THEN 시스템은 위험도·보증 분기(부품 CTA 숨김)를 결정적으로 단언할 수 있어야 한다 (SHALL).
3. WHEN 블랙보드 핸드오프·CTA 회신 라우팅을 테스트할 때 THEN 시스템은 `required_parts` 이어받기와 행동 CTA→ActionGate 경로를 단언할 수 있어야 한다 (SHALL).
4. WHEN 다단계 스트리밍·병합·복합을 테스트할 때 THEN 시스템은 방출 청크 종류·순서를 결정적으로 단언할 수 있어야 한다 (SHALL).
5. WHEN 토글 수렴을 테스트할 때 THEN 시스템은 LLM 전부 off에서 결정적 경로와 동등한 봉투를 회귀 단언할 수 있어야 한다 (SHALL).
