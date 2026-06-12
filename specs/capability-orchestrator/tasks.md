# 작업 (Tasks)

> [design.md](./design.md) 를 구현으로 나눈 체크리스트. 전환 = **스트랭글러**, capability = **조언형/행동형 분리**(ADR-0046).
> **불변 원칙:** 매 단계 후 "LLM 전부 off = 기존 `core.Orchestrator` 봉투 동일" 회귀 green 확인.

## 작업 목록

- [x] 1. capability 골격 + 레지스트리 _(요구사항 1, 2)_ — `backend/app/orchestrator/capability.py`
  - [x] 1.1 `Capability` dataclass(`cls=advisory|action`·`kind`·`intents`·`emits`·`needs`·`priority`·`run`), `CapabilityFn`.
  - [x] 1.2 `build_registry()`/`advisory_catalog()` — **조언형만** 후보 노출.
  - [x] 1.3 `TurnCtx`(블랙보드) — `write/read` + **세션 지속 슬롯**(`required_parts`·`device_status`·`candidates`·`risk_level`·`warranty_status`). _(repair_cost는 5.4 보류분)_

- [x] 2. 결정적 조언형 tool capability 래핑 (1차 이주) _(요구사항 2, 13)_
  - [x] 2.1 `handlers.handle_*`(device_status·troubleshoot→diagnose·recommend·general)을 `advisory/tool` capability로 래핑.
  - [x] 2.2 diagnose가 `required_parts`·`risk_level`·`warranty_status`, recommend가 `candidates` `ctx.write`. _(요구사항 5)_
  - [x] 2.3 레지스트리 등록.

- [x] 3. 룰 플래너 + 검증 (조언형 한정) _(요구사항 4)_
  - [x] 3.1 `rule_plan(intents, registry)` — 의도→capability 매핑·우선순위 정렬 → `Plan`.
  - [x] 3.2 `validate_plan` — 미등록 제거, **행동형 자동선택 차단**(명시 의도일 때만 허용).
  - [ ] 3.3 행동 CTA 회신을 `internal.py`에서 **CTA/ActionGate 경로**로 라우팅(자유텍스트 명시요청은 초안+확정 CTA — 현재 handle_order가 초안 산출까지는 충족, 라우터 배선 미완).

- [x] 4. CapabilityOrchestrator 조립 (결정적 패리티 게이트) _(요구사항 11, 13, 14)_
  - [x] 4.1 `build_turn`/`stream_turn(message, session_id)` — plan(룰)→exec(순차)→ctaGate→done. 세션 carry 포함.
  - [ ] 4.2 다단계 스트리밍 — 빠른 결정적(device_status) 먼저(≤2~3s). _(현재 단일 패스)_
  - [x] 4.3 **회귀 게이트** — 전체 스위트 153 통과(기존 `test_orchestrator.py` 불변). _(요구사항 15-5)_

- [x] 5. 수리 해결 CTA + 위험도·보증 게이팅 _(요구사항 6, 7)_
  - [x] 5.1 `diagnose`가 `guide_steps`+CTA(`connect_agent`·`request_visit`) 산출.
  - [x] 5.2 `risk_level`(R23 안전·step.safety)·`warranty_status`(R22 coverage)를 `ctx.write`.
  - [x] 5.3 `gate_repair_ctas` — risk(danger)/warranty(free)면 `add_to_cart` 숨기고 상담원/기사만 + **이유 설명(cta_notice)**; 단순건만 부품 CTA. _(요구사항 6-3·6-4)_
  - [ ] 5.4 비경제(`repair_cost`≥교체가 임계·반복고장)면 중립 "교체 알아보기" CTA. _(열림: 임계값 결정·repair_cost 데이터 필요 — `_cta_explore_replacement` 훅만 배치)_

- [ ] 6. 행동형 capability + CTA 회신 라우터 _(요구사항 3)_
  - [ ] 6.1 `order`·`booking`·`handoff`를 `class=action` capability로(플래너 후보 제외).
  - [ ] 6.2 `internal.py` CTA 회신 라우터 — 구조화 행동 회신(`confirmation`/`booking` 확정·`cta.action=commit`) 감지 → 플래너 우회 → 행동 capability + ActionGate(409). _(요구사항 3-2·3-3)_
  - [ ] 6.3 자유텍스트 명시 행동요청 → 초안(`confirmation`/`product_card`)+확정 CTA(자동 커밋 금지). _(요구사항 3-4)_
  - [ ] 6.4 `order`가 `required_parts`/`candidates` `ctx.read`로 이어받기(carried_parts 정합). _(요구사항 5-3)_

- [ ] 7. 제품 추천 통합 (RecommendationService 위임) _(요구사항 8)_
  - [ ] 7.1 `recommend` capability가 `RecommendationService`(랭킹·동의 폴백·중복 제외·근거)에 위임.
  - [ ] 7.2 `personalization` 없으면 일반 추천 폴백+고지. _(요구사항 8-3)_
  - [ ] 7.3 선제 진입 — `RecommendationTrigger`+컴패니언 게이트(ADR-0042) 재사용해 흡수. _(요구사항 8-4)_
  - [ ] 7.4 `correlation_id` 전환 기여 보존. _(요구사항 8-5)_

- [ ] 8. agent capability 래핑 (2차 이주) _(요구사항 2)_
  - [ ] 8.1 `diagnose`·`recommend`를 `runtime._run_worker` 위에 `kind=agent`로 감싸 delta+section.
  - [ ] 8.2 모든 LLM 호출 `achat_completion`(async·세마포어) 경유, 순차.
  - [ ] 8.3 포함/금지 규율 프롬프트 검증. _(요구사항 2-3)_

- [~] 9. LLM 플래너 (티어드, ADR-0047) _(요구사항 4-1, 11)_
  - [x] 9.0 **에스컬레이션 게이트**(`should_escalate`/`EscalationDecision`/`decide`/`route`) — 규칙 1차(홉0), 장문/모호 신호일 때만 LLM. LLM 미연결 시 규칙 폴백. 코퍼스 측정(8턴 중 3턴만 홉). _완료_
  - [x] 9.1 `LLMPlanner.propose/apropose(catalog, message)` 구조화 출력(json_schema·enum), `get_client`/`achat_completion`, 주입형. `route`에서 LLM 조언형 + 규칙 행동형 병합, 실패 시 규칙 폴백. _실 LLM 검증 `verify_llm_planner.py`: F1 교정 확인, clean은 홉0._
  - [ ] 9.2 비동기 서빙 경로(`apropose`) 배선 + 결정적 섹션 먼저 스트리밍으로 홉 지연 은닉(요구사항 11-1). _현재 `apropose` 구현·미배선._
  - [ ] 9.3 F2 목적지 capability(`warranty`·`booking`·`explain`) 추가 — LLM 플래너가 고를 대상 확장(검증서 부분교정 한계 입증).

- [ ] 10. 복합 쿼리 + 하이브리드 병합 _(요구사항 9, 10)_
  - [ ] 10.1 조언형 fan-out, 의도별 `MessageSection`(handled/unhandled).
  - [ ] 10.2 가로지르는 결정(수리 vs 교체)=CTA 선택지, LLM 평결 금지.
  - [ ] 10.3 충돌(품절)=조언 CTA까지만, 행동 턴 지연 해소(폴백 CTA).
  - [ ] 10.4 병합 — 우선순위 스택 + 연결 delta만(사실·판단 불변).

- [ ] 11. 조건부 리뷰 + 커밋 안전 _(요구사항 12)_
  - [ ] 11.1 `should_review` — 안전·커밋·불확실 발동, **불확실/안전을 결정적 신호**(tool 근거 부재·`risk_level`)로 탐지.
  - [ ] 11.2 커밋 = `confirmation`/`booking` 확정 + ActionGate(409), 버퍼링 없음.
  - [ ] 11.3 위반시 보정/차단·사람연결, 재계획 금지.

- [ ] 12. 디스패치 수렴 + 토글 _(요구사항 13)_
  - [ ] 12.1 `_stream_turn`을 capability 경로로 흡수, 토글을 capability 단위 LLM-backed로 평가(매 호출 env).
  - [ ] 12.2 어느 상태든 §2.1 봉투 동일 보장.
  - [ ] 12.3 패리티 증명 후 `legacy`·`runtime`·`core` 옛 경로 제거(스트랭글러 마무리).

- [ ] 13. 실패·부분 폴백 _(요구사항 14)_
  - [ ] 13.1 step별 try/except·타임아웃, 실패 step만 폴백.
  - [ ] 13.2 플래너 실패→룰 폴백, 턴 회복불가→`error` 봉투.

- [x] 14. Mock/결정적 테스트 _(요구사항 15)_ — `backend/tests/test_capability.py`(9), `backend/verify_multiturn.py`
  - [x] 14.1 플래너 **행동형 자동선택 차단**·명시 order 허용 단언.
  - [x] 14.2 수리 CTA 게이팅(risk danger·warranty free 부품 숨김 + 설명, 단순건 부품 CTA) 단언. _(비경제 교체 CTA는 5.4 보류)_
  - [x] 14.3 블랙보드 크로스턴 carry(다음 턴 order가 required_parts 이어받음)·세션 격리 단언. _(CTA 회신→ActionGate 라우팅은 3.3와 함께 후속)_
  - [ ] 14.4 추천 위임(동의 폴백·중복) 단언. _(현 recommend는 기존 RecommendationService 경유 — 위임 단언 후속)_
  - [ ] 14.5 복합 fan-out·결정=CTA·충돌 지연, 스트리밍·병합 청크 순서 단언. _(verify_multiturn에서 수동 확인, 자동 단언 후속)_
  - [x] 14.6 봉투 패리티(section→flow→done) 회귀 단언.

## 진행 메모
- 스트랭글러 순서: **1→2→3→4(결정적 패리티 게이트)** 가 "회귀 없이 골격 수렴" 1차. **5~7**에서 수리 CTA 게이팅·행동형 분리·추천 위임(ADR-0046 핵심), **8~11**에서 LLM capability·플래너·복합·리뷰, **12.3**에서 옛 경로 삭제.
- 기존 자산 재사용: `_PRIORITY`·`plan_workers`·`carried_parts`·`should_review`·`_run_worker`·`achat_completion`·`RecommendationService`·기존 템플릿. 새로 만들지 말고 재배치.
- 구현 중 설계와 달라지면 design.md·본 파일 동시 갱신.
