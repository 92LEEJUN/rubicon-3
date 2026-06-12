# ADR-0045: capability 구조 상세 — 2채널 출력 · LLM 플래너(검증) · 레지스트리 · 블랙보드

- **상태**: 채택 (구현 후속)
- **관련**: ADR-0043(capability 통합)·0044(Recommend agent)·0009(슈퍼바이저)·0025(구조화 Template)·0033(ActionGate)·0017(병렬 보류), `docs/agents.md`

## 배경
capability 통합 오케스트레이터(ADR-0043)를 "실제 동작하는 설계"로 닫으려면 4축이 미정이었다: ① 출력 계약 ② 플래너 ③ capability 간 데이터 ④ 스트리밍/리뷰 위치. 논의로 확정한다.

## 결정

### ① 출력 = 2채널 (delta 내러티브 + section 아티팩트)
capability는 **api-contract §2.1 청크**를 방출한다:
- **delta** — 자유 내러티브(설명·연결문구·"왜 추천?"). **system 프롬프트의 포함/금지 규율**로 통제(아래).
- **section** — 구조화 아티팩트(`product_card`·`recommendation_list`·`guide_steps`·`confirmation` 등). **FE 리치 렌더(ADR-0025) + 커밋 게이트(R17·ADR-0033)** 보존.
- agent capability = LLM tool-loop → delta(설명) + section(구조화 산출). tool/결정적 capability → section.

> 순수 free delta는 리치 템플릿·커밋 안전을 잃어 기각. 순수 구조화 섹션은 자연어 흐름이 약해 기각 → **2채널**.

**포함/금지 규율(프롬프트에 명시):**
- 포함: tool 근거·출처(R16) · 위험 단계 경고(R23) · 추천 근거(R8) · 커밋 전 확인 유도(R17)
- 금지: 가격·사양·재고·해결책 **날조**(환각) · 시스템·대기·순번 언급(ops §11) · 동의 범위 밖·민감정보(R19) · 무확인 커밋

### ② 플래너 = LLM 동적 DAG + 룰 검증/폴백
- **LLM 플래너**: 의도+컨텍스트 → 구조화 plan `{steps:[{capability, depends_on, parallel_group}]}`. 입력은 capability **레지스트리 카탈로그**.
- **검증(룰, "제안→룰 검증")**: 레지스트리에 있는 capability만 허용 · 사이클 금지 · 우선순위(§6.6) 정렬 · 빈/무효 플랜 → **룰 매핑 폴백**.
- **결정성**: 플래너 mock 주입으로 결정적 테스트. LLM 환각 capability는 검증에서 탈락.

### ③ capability 간 데이터 = turn 블랙보드
- 턴 스코프 공유 컨텍스트 `ctx`: capability가 산출(예: `required_parts`·`device_status`·`candidates`)을 **write**, 의존 capability가 **read**. `carried_parts`의 일반형(ADR-0043 핸드오프).

### ④ 스트리밍 / 리뷰
- **다단계 섹션 방출**: 빠른 결정적 capability(`device_status`)를 **먼저**(프리페치 ≤2s) → agent → 병합 연결 delta.
- **조건부 리뷰**: 안전·불확실은 내러티브 보정(단일 패스). **커밋 안전은 structured `confirmation` + ActionGate(R17/409)** 로 결정적 보장 → 스트림 버퍼링 불요(커밋은 별도 결정적 경로).

### 레지스트리
`{name: Capability(kind=agent|tool, intents, tools, prompt?, deps_hint, priority, emits)}` — 추가 = 한 엔트리.

## 결과/영향
- `runtime`/`core`를 **capability 레지스트리 + LLM 플래너(검증) + 2채널 출력 + 블랙보드 + 하이브리드 병합**으로 수렴(후속 리팩터). 결정적 경로는 "룰 플래너 + tool capability"의 특수 케이스로 흡수.
- 구현은 별도 스펙(`specs/capability-orchestrator/`) 후보.
