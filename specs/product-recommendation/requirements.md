# 요구사항 (Requirements) — product-recommendation (선제적 제품 추천)

## 개요

**제품 비전 2 = "선제적 제품 판매 추천"의 본격화.**
MVP(`specs/mvp-concierge/`)는 부품 매칭과 기본 추천(R8·R29)만 갖는다. 이 스펙은 그 위에
**개인화·선제 제품 추천 기능 줄기**를 얹는다: 보유 기기·소모품 수명·이력·구매 주기 등
**트리거 기반으로 사용자가 먼저 물어보지 않아도** 적절한 제품/소모품을 추천하고, 추천 근거를
제시하며, 대화형 CTA로 `/chat`에 재진입해 비교·주문까지 잇는다.

이 스펙은 **새 인프라를 만들지 않는다.** 기존 토대를 재사용·확장한다:
- 개인화 컨텍스트 조립: `docs/operations.md` §4(컨텍스트 소스·조립 규칙)·§4-1(컴패니언 메모리).
- 선제 파이프라인·게이트: `docs/architecture.md` §10(proactive)·**ADR-0042**(엄격 게이트).
- 동의 scope: `docs/data-model.md` §동의 scope·**ADR-0030**(`personalization`·`engagement`·`device_data`).
- 중복 억제·관심 신호: `EngagementRepository`(R29)·**ADR-0029**(Engagement vs Analytics).
- 응답 표현: `docs/response-templates.md`(`recommendation_list`·`product_card`·`product_comparison`).
- 추천 정책·근거·차등 출력: `docs/llm-policy.md` §5·§6.
- 전환 기여: `docs/analytics.md` §5(`correlation_id` attribution).
- 컴패니언 연계: `specs/always-present-companion/`(open-loop·메모리·선제 재관여).
- 카탈로그 경계: `CatalogPort`(`docs/data-model.md` §6, Mock↔실).

> 이 스펙의 요구사항은 MVP의 **R8(개인화 추천)·R29(중복 방지)·R26(빈도)·R27(다중 묶음)·R19(동의)**를
> **확장·구체화**한다. MVP 요구사항을 재정의하지 않고, 추천 줄기에 고유한 요구사항만 새 번호로 둔다.

### 구현 방식 표기 (MVP 마커 계승)
- **[실 기능]** — 동작 가능(내부 도메인/Engagement/추천 로직).
- **[Mock→실]** — 인터페이스는 교체 전제(`CatalogPort` 실데이터·실 알림 채널 등).

---

## 요구사항 목록

### 요구사항 1: 선제 추천 트리거 — [실 기능]

**User Story:**
사용자로서, 내가 먼저 묻지 않아도 내 상황(보유 기기·소모품 수명·이력·구매 주기)에 맞는 제품을
적시에 추천받고 싶다, 그래서 필요한 것을 놓치지 않고 미리 챙길 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 보유 기기의 소모품 수명·사용량이 재주문/교체 시점에 도달하면 THEN 시스템은 해당 소모품·관련 제품 추천을 **선제적으로 생성**해야 한다 (SHALL).
2. WHEN 사용자의 이력(과거 관심·주문)에서 **구매 주기·재구매 시점**이 추정되면 THEN 시스템은 그 시점에 맞춰 추천을 생성해야 한다 (SHALL).
3. WHEN 추천 트리거가 발생하면 THEN 시스템은 어떤 신호(소모품 수명/이력/주기)에서 비롯됐는지 **트리거 근거를 기록**해야 한다 (SHALL).
4. IF 트리거가 될 만한 개인 신호가 없으면 THEN 시스템은 선제 추천을 **생성하지 않아야** 한다 (SHALL) — 무근거 추천 방지.

### 요구사항 2: 선제 게이트 정합 (동의·빈도·중복·묶음) — [Mock→실]

**User Story:**
사용자로서, 선제 추천이 컴패니언의 다른 선제 메시지와 똑같은 규율(동의·빈도·중복)을 따르길 원한다,
그래서 추천 때문에 알림이 과해지거나 중복되지 않는다.

**수용기준 (Acceptance Criteria):**
1. WHEN 선제 추천을 전달할 때 THEN 시스템은 컴패니언 선제 게이트(ADR-0042)와 **동일한 순서**(`Consent/opted_in → R26 빈도/중요도 → 가치(불확실·중복 억제) → R27 다중기기/항목 묶음`)를 통과한 추천만 전달해야 한다 (SHALL).
2. IF `Notification.opted_in`이 거짓이거나 R26 빈도 한도를 초과하면 THEN 시스템은 선제 추천을 **전달하지 않아야** 한다 (SHALL).
3. WHILE 추천 가치가 낮거나(불확실) 중복일 때 시스템은 해당 추천을 **억제**해야 한다 (SHALL).
4. WHEN 다수의 추천 후보가 동시에 발생하면 THEN 시스템은 R27 규칙으로 **묶거나 상위만** 제시해 알림 피로를 방지해야 한다 (SHALL).

### 요구사항 3: 개인화 추천 — 보유 기기 중복 방지 · 관심·이력 반영 — [실 기능]

**User Story:**
사용자로서, 이미 가진 기기는 다시 추천받지 않고 내 관심·이력에 맞는 보완·대안 제품을 받고 싶다,
그래서 나에게 실제로 맞는 제안만 받는다.

**수용기준 (Acceptance Criteria):**
1. WHEN 추천 대상을 선정할 때 THEN 시스템은 사용자가 **이미 보유한 기기/제품을 중복 추천하지 않고** 보완·대안·소모품을 우선해야 한다 (SHALL). (R8-2 확장)
2. WHEN 추천을 생성할 때 THEN 시스템은 사용자의 **관심 신호·이력**(`EngagementRepository.interests`·대화 이력·`interest_categories`)을 반영해야 한다 (SHALL). (R8-1 확장)
3. WHEN 이미 보거나(`viewed`) 무시한(`dismissed`) 추천이 있으면 THEN 시스템은 이를 **중복 제시하지 않아야** 한다 (SHALL). (R29 확장)

### 요구사항 4: 동의 게이트 · 일반 추천 폴백 — [실 기능]

**User Story:**
사용자로서, 개인화 동의를 하지 않았어도 추천이 막히지 않고 일반 추천으로 도움받고 싶다,
그래서 동의 여부와 무관하게 최소한의 가치를 받는다.

**수용기준 (Acceptance Criteria):**
1. IF `Consent.scopes`에 `personalization`이 없으면 THEN 시스템은 개인화 추천을 하지 않고 **일반 추천으로 폴백**해야 한다 (SHALL). (R8-3 확장)
2. WHEN 일반 추천으로 폴백할 때 THEN 시스템은 **개인화가 제한적임을 사용자가 알 수 있게** 고지해야 한다 (SHALL).
3. IF `personalization`은 없지만 `device_data`만 있으면 THEN 시스템은 보유 기기 기반(중복 방지)까지만 반영하고 이력 기반 개인화는 **제외**해야 한다 (SHALL) — scope별 차등.
4. WHEN 동의가 철회되면 THEN 시스템은 이후 추천에서 즉시 개인화·선제를 **중단**해야 한다 (SHALL). (R19)

### 요구사항 5: 추천 근거 · 대화형 CTA로 /chat 재진입 — [실 기능]

**User Story:**
사용자로서, "왜 이걸 추천했는지" 설명을 보고 바로 비교·질문·주문으로 이어가고 싶다,
그래서 추천을 신뢰하고 다음 행동으로 매끄럽게 넘어간다.

**수용기준 (Acceptance Criteria):**
1. WHEN 추천을 제시할 때 THEN 시스템은 각 항목에 **개인화 근거**(예: "이전에 ○○에 관심을 보이셔서", "△△ 소모품 교체 시기라서")를 함께 제시해야 한다 (SHALL). (R8-4·`recommendation_list.items[].reason`)
2. WHEN 사용자가 추천 항목의 "비교/대안" 또는 "왜 추천?" 대화형 CTA를 누르면 THEN 시스템은 **`/chat`으로 재진입**해 해당 추천 맥락을 주입한 대화를 이어야 한다 (SHALL). (proactive→reactive, architecture §10)
3. WHEN 추천이 카드(`recommendation`)로 노출되고 사용자가 탭하면 THEN 시스템은 간단 정보는 `bridge` 모달, 비교·상담이 필요하면 패널로 BE가 동적 분기해야 한다 (SHALL). (response-templates §9)

### 요구사항 6: 전환 기여 추적 (추천 → 장바구니 → 주문) — [Mock→실]

**User Story:**
운영자로서, 어떤 추천이 장바구니·주문으로 이어졌는지 알고 싶다,
그래서 추천 품질을 데이터로 개선할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 추천이 노출·클릭되고 이후 장바구니·주문이 일어나면 THEN 시스템은 동일 `correlation_id`로 **추천→장바구니→주문 기여**를 추적할 수 있어야 한다 (SHALL). (analytics §5)
2. WHEN 추천 관련 분석 이벤트를 수집할 때 THEN 시스템은 `Consent.scopes`에 `analytics`가 있을 때만 수집하고 식별자를 가명화해야 한다 (SHALL). (R28·R19)
3. WHEN 추천 이벤트를 emit할 때 THEN 시스템은 정의된 택소노미(`recommendation` `card_type`·`cta_clicked`·`order_confirmed` 등)를 따라야 한다 (SHALL) — 신규 이벤트는 `analytics.md` 갱신 후 추가.

### 요구사항 7: 컴패니언 메모리 / open-loop 연계 — [실 기능]

**User Story:**
사용자로서, 지금 당장 사지 않은 추천을 에이전트가 기억했다가 적절할 때 다시 챙겨주길 원한다,
그래서 미뤄둔 추천을 놓치지 않는다.

**수용기준 (Acceptance Criteria):**
1. WHEN 사용자가 추천을 **보류**(나중에·관심만 표시)하면 THEN 시스템은 이를 **open-loop**로 추적할 수 있어야 한다 (SHALL). (companion R2)
2. WHEN 사용자가 돌아올 때 THEN 시스템은 보류된 추천 open-loop를 우선순위 요약(resume)에 포함할 수 있어야 한다 (SHALL). (companion R1·R2)
3. WHEN 추천이 주문·dismiss·만료로 해소되면 THEN 시스템은 해당 open-loop를 **닫아야** 한다 (SHALL). (companion R2-3)
4. WHEN 추천 개인화에 이력을 쓸 때 THEN 시스템은 `ConversationMemory`(요약·사실)의 관심·미해결 신호를 컨텍스트로 활용할 수 있어야 한다 (SHALL). (operations §4-1)

### 요구사항 8: 카탈로그 Mock↔실 경계 — [Mock→실]

**User Story:**
개발자로서, 추천이 의존하는 제품 데이터 소스를 Mock에서 실데이터로 교체해도 추천 로직이
바뀌지 않길 원한다, 그래서 데이터 성숙도와 무관하게 기능을 먼저 통합할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 추천 후보 제품을 조회할 때 THEN 시스템은 `CatalogPort`(추천·by-id 조회)만 통해 접근하고 추천 도메인 로직은 Port 구현(Mock/실)에 의존하지 않아야 한다 (SHALL). (data-model §6)
2. IF 카탈로그 조회가 빈 결과·부분 응답·실패이면 THEN 시스템은 흐름을 끊지 않고 일반 추천 또는 안내로 폴백해야 한다 (SHALL). (R13·PortError)
3. WHEN 카탈로그 데이터가 demand-driven 경계(전체 나열/브라우즈 없음)를 따를 때 THEN 시스템은 추천을 **카드·대화로만** 노출해야 한다 (SHALL). (Product 모델 주석)

---

## 미해결 질문 / 검증 필요 (design 단계 입력)
- 구매 주기 추정에 쓸 **이력 데이터의 범위·정확도**(주문 이력만 vs 관심 신호 포함) **확인 필요**.
- `CatalogPort`가 "보유 기기 보완·대안" 추천에 충분한 **카테고리·관계 메타데이터**를 제공하는지 **검증 필요**.
- 선제 추천을 컴패니언 `ReEngagementService`에 **트리거로 합칠지**, 추천 전용 트리거 소스를 둘지 **결정 필요**(design에서 ADR 후보).
- 신규 분석 이벤트(추천 노출·보류·전환 단계) 정의 시 `docs/analytics.md` 갱신 범위 **결정 필요**.
