# ADR-0046: 조언형/행동형 capability 분리 + CTA 브릿지 (자동 라우팅 금지)

- **상태**: 채택 (capability-orchestrator 스펙 개정)
- **관련**: ADR-0043(통합)·0044(Recommend agent)·0045(capability 상세)·0033(ActionGate)·0011(조건부 리뷰)·0042(엄격 게이트), `docs/response-templates.md`, `specs/product-recommendation/`, `specs/capability-orchestrator/`

## 배경
capability-orchestrator 초안(ADR-0043~0045)은 LLM 플래너가 **자유텍스트 의도에서 `order`/`booking` 같은 행동형 capability를 자동 선택**하도록 설계됐다. 이는 모호한 질의("세탁기 이상해요")에서 곧장 **제품 판매·수리기사 접수 루트로 자동 진입**해 사용자 동의 없이 상거래·디스패치를 푸시하는 위험이 있다. 또한 추천을 `recommend` capability 하나로 납작하게 만들어 기존 `specs/product-recommendation/`의 동의·개인화·중복·근거·전환 고려를 전부 무시했고, **복합 쿼리**(가로지르는 판단·충돌)에 대한 처리가 없었다.

## 결정

### 1. capability를 조언형 / 행동형으로 분리
- **조언형(Advisory)** — 읽기 전용. 정보 템플릿 + **CTA**만 산출. **커밋하지 않는다.** 플래너가 자유텍스트에서 자동 선택 가능. (`diagnose`·`recommend`·`status`·`explain`)
- **행동(Action)** — 되돌릴 수 없는 상태 변경·상거래. **오직 ActionGate(R17)** — `confirmation`/`booking` 확정 **CTA 회신**으로만 진입. (`order`·`booking`·`handoff`)
- **대원칙**: 어떤 capability도 조언·초안까지만. **자동 커밋·자동 디스패치 없음.** 플래너는 초안·CTA까지만 생성하고, 실행은 CTA 확정→ActionGate가 결정적으로 처리한다.

### 2. 수리 해결 — 자가진단 + 위험도·보증 게이팅
- `diagnose`는 `guide_steps`(자가진단) + `required_parts`를 내고 끝에 CTA: `add_to_cart`(부품)·`connect_agent`(상담원)·`request_visit`(수리기사 접수).
- **CTA 게이팅(결정적)**: 해결책이 **안전 위험**(R23, 가스·감전 등)이거나 기기가 **보증 중**(R22)이면 **부품 자가주문 CTA를 숨기고** 상담원/수리기사 CTA만 노출한다.

### 3. 수리↔교체 브릿지 — 비경제일 때만 중립 CTA
- 진단이 **수리 불가/비경제**(수리비 ≥ 교체가 임계)로 판정될 때만 중립 "교체 알아보기" CTA를 1개 추가한다. 수리/교체 **판단은 LLM이 내리지 않고 사용자에게** 넘긴다(판매 푸시 금지).

### 4. 추천 통합 — RecommendationService 위임 + 선제/반응형 흡수
- `recommend` capability는 얇은 래퍼로, 코어는 기존 `RecommendationService`(개인화 랭킹·동의 scope 폴백·보유/중복 제외·근거 부착)에 위임한다(`specs/product-recommendation/`).
- **선제·반응형 두 진입을 모두 흡수**한다. 선제는 `RecommendationTrigger` + 컴패니언 게이트(ADR-0042)를 재사용. 추천도 조언형 — `recommendation_list` + CTA까지, 구매는 별도 ActionGate.

### 5. 복합 쿼리 처리
- 조언형 **fan-out**(우선순위: 안전·CS 먼저). 각 capability는 자기 `MessageSection` + 스코프 CTA를 내고 handled/unhandled 표기.
- **capability를 가로지르는 판단은 CTA 선택지로 제시한다 — LLM 평결 금지**(예: "고칠까 살까" → 수리 가이드 + 비경제면 교체 CTA).
- **충돌(품절·단종 등)은 행동 턴으로 지연 해소** — 조언형은 CTA까지만, 사용자가 행동 CTA를 누르는 턴에서 충돌을 폴백 CTA(상담원/대체)로 처리.

## 대안 / 기각
- **플래너 자동 라우팅(초안 그대로)** — 모호 질의에서 판매·디스패치 자동 진입 위험으로 기각.
- **병합이 가로지르는 판단을 합성** — 환각·과잉판매·R5(무환각) 위반으로 기각. 판단은 CTA 선택지로 사용자에게.
- **추천을 capability 안에서 재정의** — 기존 product-recommendation 스펙과 중복·표류로 기각. 위임 채택.

## 영향
- `specs/capability-orchestrator/`의 requirements/design/tasks를 본 결정으로 개정. 블랙보드 슬롯에 `risk_level`·`warranty_status`·`repair_cost` 추가. 기존 계약(`guide_steps`·`handoff_card`·`booking`·`confirmation`·ActionGate)·도메인 모델은 불변.
