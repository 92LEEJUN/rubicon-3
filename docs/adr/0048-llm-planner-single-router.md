# ADR-0048: LLM 플래너 단일 라우터 (에스컬레이션 게이트 폐기)

- **상태**: 채택
- **대체**: [ADR-0047](0047-tiered-planning-escalation-gate.md)(티어드 플래닝/게이트) — 폐기
- **관련**: ADR-0046(조언형/행동형), `specs/capability-orchestrator/`(요구사항 4), `test-findings.md`

## 배경
ADR-0047은 규칙 분류기를 1차로 두고 LLM 플래너는 모호·장문 턴만(에스컬레이션 게이트) 호출해 레이턴시를 아꼈다. 그러나 게이트는 **규칙 신뢰도 휴리스틱**(단어 단서·길이)에 의존해 임계 근처에서 취약하고, "어떤 턴이 LLM을 거치는가"가 두 갈래로 갈려 동작이 복잡했다. 사용자는 **모든 질의를 LLM 플래너가 일관되게 라우팅**하는 단순한 모델을 택했다(레이턴시는 수용; 스트리밍 은닉은 별도 옵션).

## 결정
- **LLM 플래너를 모든 자유텍스트 턴의 단일 라우터로 둔다.** 에스컬레이션 게이트(`should_escalate`/`EscalationDecision`/`decide`)를 제거한다.
- **규칙 분류기는 폴백으로 강등** — LLM 플래너 미연결(오프라인·테스트)·호출 실패·빈 결과일 때만 사용(요구사항 14-2). 이로써 오프라인 결정성·테스트는 유지된다.
- LLM은 **조언형만** 고르고, 명시 행동(order)은 규칙 plan에서 보존·병합한다(ADR-0046 불변).
- **F2 목적지 capability를 추가**(§9.3) — `warranty`(보증)·`booking`(예약 슬롯 초안)·`explain`(스펙·가격·비교)·`clarify`(모호 시 되묻기). LLM이 라우팅할 대상을 확장.
- 레이턴시: 매 턴 +1홉을 수용. 완화(결정적 섹션 먼저 스트리밍·빠른 모델)는 §9.2의 별도 작업.

## 실 LLM 검증 (gpt-4o-mini, `verify_llm_planner.py`)
- **F2 완전 해소**: "보증·예약" → `[warranty, booking]`(규칙은 `[diagnose]`로 뭉갬). "스펙·가격" → `explain` 라우팅.
- **모호 처리**: "이거 좀 어떻게 해줘" → `[clarify]`(기기 빠른 선택지).
- **단순 보존**: "세탁기 물 안 빠져요" → `[diagnose]`(규칙과 동일).
- 한계: LLM이 가끔 불필요 capability를 1개 더 고름(예: J5에 recommend 추가). 무해하나 프롬프트 튜닝 여지.

## 대안 / 기각
- **게이트 유지(ADR-0047)** — 임계 취약·이중 경로 복잡, 사용자 선택으로 폐기.
- **게이트를 결정적 숏컷으로 역할 전환** — 단순성 우선으로 미채택(추후 레이턴시 필요 시 재도입 가능).

## 영향
- `should_escalate`/`EscalationDecision`/`decide`/`last_decision` 제거. `route`는 planner 있으면 항상 LLM, 없으면 규칙 폴백. registry에 warranty·booking·explain·clarify 추가. 전체 164 통과.
