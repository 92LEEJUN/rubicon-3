# 설계 (Design)

> [requirements.md](./requirements.md) 를 **어떻게** 만족시킬지. 공유 결정·모델은 기반 문서를 참조한다 —
> **통합 [ADR-0043](../../docs/adr/0043-capability-orchestrator.md), 상세 [ADR-0045](../../docs/adr/0045-capability-structure-detail.md), 조언형/행동형+CTA [ADR-0046](../../docs/adr/0046-advisory-action-cta-bridge.md), [docs/agents.md](../../docs/agents.md) §11·§12**. 추천 도메인은 [specs/product-recommendation/](../product-recommendation/)에 위임.

## 개요

세 서빙 경로(결정적 [core](../../backend/app/orchestrator/core.py) · 단일 tool-loop [legacy](../../backend/app/orchestrator/legacy.py) · 멀티에이전트 [runtime](../../backend/app/orchestrator/runtime.py))를 **하나의 capability 오케스트레이터**로 수렴하되, capability를 **조언형/행동형으로 분리**한다(ADR-0046). 핵심: **플래너는 조언형만 자동 선택 → 정보+CTA까지만. 되돌릴 수 없는 행동은 CTA 확정→ActionGate로만.** 전환은 **스트랭글러** — 새 골격을 세우고 기존 `handlers.handle_*`·`runtime` 워커를 capability로 하나씩 감싸 이주하며, 매 단계 "LLM 전부 off = 기존 결정적 봉투 동일" 회귀로 green 유지.

클라이언트 계약(api-contract §2.1)·응답 템플릿(`guide_steps`·`handoff_card`·`booking`·`confirmation`·CTA)·도메인 모델은 **불변**.

## 아키텍처

**두 진입 — 자유텍스트 / CTA 회신**이 갈린다:

```text
[A] 자유텍스트 턴 ("세탁기 물이 안 빠져요")
 → CapabilityOrchestrator.astream
   1) plan : LLMPlanner.propose(advisory_catalog, msg, ctx) → 검증(조언형만·사이클·우선순위·필수보정)
            → 무효/실패 시 rule_plan 폴백
   2) exec : 조언형 capability 순차(depends_on). ctx에 산출 write (required_parts·risk_level·warranty_status·repair_cost)
   3) CTA gating : diagnose가 risk/warranty 보고 부품 CTA 숨김 결정 (결정적, R6)
                   비경제(repair_cost≥교체가)면 중립 교체 CTA 추가 (R7)
   4) merge : 결정적 섹션 스택 + 얇은 연결 delta (판단 금지)
   5) review: should_review(안전·커밋·불확실, 결정적 신호) → 조건부
 → section*(+CTA) · delta* · flow · done

[B] CTA 확정 회신 ("수리기사 접수" / "주문 확정")  ← 구조화 payload(action·id)
 → 플래너 우회. 결정적 라우팅 → 행동 capability(order|booking|handoff) + ActionGate(R17/409)
 → confirmation/booking 확정 → 커밋
```

- **순차 단일 패스**(ADR-0017·0012). 행동형이 자동 실행 안 되니 턴당 LLM capability 수↓ → 지연 완화.
- 기존 결정적 로직(`_PRIORITY`·`plan_workers`·`carried_parts`·`should_review`)은 룰 폴백·검증·블랙보드·리뷰의 토대로 재사용.

## 주요 컴포넌트 / 인터페이스

신규 모듈 `backend/app/orchestrator/capability.py`(+`registry.py`·`planner.py`). 출력은 기존 [domain/models.py](../../backend/app/domain/models.py) 재사용.

- **`Capability`** (dataclass) _(요구사항 1)_
  ```python
  @dataclass(frozen=True)
  class Capability:
      name: str
      cls: Literal["advisory", "action"]      # 행동형은 플래너 자동선택 제외
      kind: Literal["agent", "tool"]
      intents: tuple[str, ...]
      emits: tuple[str, ...] = ()             # 블랙보드 write 슬롯
      needs: tuple[str, ...] = ()             # 블랙보드 read 슬롯
      priority: int = 2
      tools: tuple[str, ...] = ()             # kind=agent 허용 tool
      prompt: Optional[str] = None
      run: CapabilityFn                       # call(input, ctx) → AsyncIterator[chunk]
  ```
- **`CapabilityRegistry`** — `{name: Capability}`. `advisory_catalog()`는 **조언형만**(name·intents·needs·설명) 노출 → 플래너 후보. _(요구사항 1·4)_
- **조언형 capability** _(요구사항 6·8·9)_
  - `diagnose`(agent) — `guide_steps`+`required_parts`+`risk_level`+`warranty_status`(+비경제면 `repair_cost`). 끝에 CTA `connect_agent`·`request_visit`, 조건부 `add_to_cart`·교체.
  - `recommend`(agent) — `RecommendationService` 위임(랭킹·동의 폴백·중복 제외·근거). `recommendation_list`+CTA. 선제/반응형 공유.
  - `status`·`explain`(tool/agent).
- **행동형 capability** — `order`·`booking`·`handoff`. 플래너 후보 아님. **CTA 회신 라우터**가 payload로 직접 디스패치 → ActionGate. _(요구사항 3)_
- **`ctaGate(sections, ctx)`** — 결정적 CTA 게이팅. `risk_level`/`warranty_status`면 `add_to_cart` 제거·상담원/기사만; `repair_cost≥threshold`면 중립 교체 CTA 추가. _(요구사항 6·7)_
- **`LLMPlanner.propose(advisory_catalog, msg, ctx) -> Plan`** — 구조화 출력, `achat_completion` 경유, 주입형(테스트 스텁). _(요구사항 4)_
- **`PlanValidator.validate(plan, registry) -> Plan|None`** — 미등록·사이클 제거, `priority` 위상정렬, **행동형 선택 차단**, 안전의도 필수 capability 누락 보정. _(요구사항 4-2·4-4)_
- **`rule_plan(intents) -> Plan`** — `core._ordered_intents`+`plan_workers` 매핑(조언형). 폴백·결정적 경로 본체. _(요구사항 4-3)_
- **`TurnCtx`** (블랙보드) — `write/read`, 스코프 주입. 슬롯: `required_parts`·`device_status`·`candidates`·`risk_level`·`warranty_status`·`repair_cost`. _(요구사항 5)_
- **`merge(sections, ctx)`** — 우선순위 스택 + 연결 delta만(판단/평결 금지). _(요구사항 10)_
- **CTA 회신 라우터** ([internal.py](../../backend/app/api/internal.py)) — 구조화 행동 회신(`confirmation`/`booking` 확정·`cta.action="commit"`) 감지 → 플래너 우회 → 행동 capability + ActionGate. _(요구사항 3-3)_
- **`CapabilityOrchestrator.astream(...)`** — 자유텍스트 경로 1)~5) 조립. `astream_multiagent` 드롭인 시그니처. _(요구사항 11·14)_

## 데이터 모델
- **재사용(불변):** `MessageSection`·`Template`·`Cta`(`action`·`kind`·`payload`)·`AssistantTurn`. `guide_steps`·`handoff_card`·`booking`·`confirmation`·`recommendation_list` 템플릿. (response-templates)
- **신규(오케스트레이터 내부 전용):** `Capability`·`Plan`/`Step`·`TurnCtx`. 클라이언트로 새지 않음.
- **블랙보드 슬롯:** `required_parts`(진단→주문)·`device_status`·`candidates`(추천→주문)·`risk_level`·`warranty_status`·`repair_cost`(CTA 게이팅).

## 에러 처리 _(요구사항 14)_
- step 실패 → 그 step만 폴백, unhandled 표기, 부분결과 유지.
- 플래너 실패/무효 → `rule_plan` 폴백.
- capability 충돌(품절) → 조언 턴에선 CTA까지만, 행동 CTA 턴으로 지연 해소(폴백 CTA).
- 턴 회복 불가 → `error` 봉투(비중단).

## 테스트 전략 _(요구사항 15)_
- **회귀(핵심)** — LLM 전부 off에서 새 경로 = 기존 `core.Orchestrator` 봉투 동일. 기존 `test_orchestrator.py`(J1·compound·envelope) 재실행.
- **조언형/행동형** — 플래너가 행동형을 자동선택 못 함(검증 차단) 단언. CTA 회신→행동 capability→ActionGate 경로 단언.
- **수리 CTA 게이팅** — risk/warranty면 `add_to_cart` 제거·상담원/기사만; 단순건만 부품 CTA; 비경제만 교체 CTA. 결정적 단언.
- **추천 위임** — `RecommendationService` 동의 폴백·중복 제외·근거를 Mock으로 단언.
- **복합** — fan-out 섹션·handled/unhandled·가로지르는 결정=CTA·충돌 지연 단언.
- **스트리밍·병합** — 청크 종류·순서 결정적 단언. 픽스처는 기존 `conftest.container`+Mock 유지, 레지스트리 주입 추가.

## 설계 결정 / 대안
- **조언형/행동형 + CTA 브릿지(ADR-0046)** — 플래너 자동 라우팅(판매·디스패치 위험)·병합 판단합성(환각·과잉판매) 기각. 가로지르는 판단은 CTA 선택지로.
- **전환 = 스트랭글러** — 빅뱅(회귀 위험)·어댑터통째(중복 유지) 기각.
- **추천 위임** — capability 내 재정의(중복·표류) 기각, `RecommendationService` 재사용.
- **기존 로직 재배치** — `_PRIORITY`·`plan_workers`·`carried_parts`·`should_review`·`_run_worker`·`achat_completion` 재사용.
