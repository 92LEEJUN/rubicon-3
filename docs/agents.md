# 멀티에이전트 구조 (Agents)

> **기반 문서 (공유).** 슈퍼바이저-워커 멀티에이전트의 **구성·제어·통신·실행**을 정의한다.
> 파이프라인·다단계 스트리밍은 `docs/orchestration.md`(§4·§10), 운영·지연·세션은 `docs/operations.md`(§13·§14),
> 프롬프트·가드레일은 `docs/llm-policy.md`, 우선순위는 `specs/mvp-concierge/design.md` §6.6 을 본다.
> MVP 기본은 **단일 오케스트레이터 tool-loop**(orchestration §1). 본 문서는 **규모/복잡도 증가 시 확장 구조**다.
> 각 결정의 **후보안·근거·기각 이유**는 `docs/adr/`(ADR-0009~0013)에 별도 기록.

## 1. 제어 패턴 — 슈퍼바이저-워커 / 단일 패스 (확정)

- **중앙 Supervisor**가 intent별로 **필요한 워커(에이전트/tool)만 동적 위임**하고 결과를 조립한다.
  (우리 "워크플로 = 코드가 루프 제어"(orchestration §1)와 정합 — 자율 네트워크 아님.)
- **단일 패스** — `위임 → 실행 → (조건부 리뷰) → 조립`. **재계획 루프 없음**(지연 예측성). 실패는 부분 폴백(R13).

## 2. 구성 — 에이전트 vs tool (그래뉼래리티: 중간, 확정)

**에이전트 = 자체 LLM 추론 루프 보유. tool = 결정적 호출.**

**에이전트 (4)**
| 에이전트 | 역할 | 주 tool | 요구사항 |
|---|---|---|---|
| **Supervisor** | intent 분해·우선순위·위임·최종 조립 | (분류 구조화 출력) | R7·§6.6 |
| **Diagnosis(진단)** | 기기 상태 + 증상→해결책(RAG) | `get_device_status`·`search_solutions` | R2·R3·R16 |
| **Commerce(커머스)** | 부품 매칭 + 주문 초안(커밋=ActionGate) | `match_parts`·`create_order`(게이트) | R4·R17 |
| **Recommend(추천)** | 자연어 need 이해 → 후보 비교·근거 설명 (ADR-0044) | `recommend`·`match_parts` | R8 |
| **Review(크리틱·조건부)** | 안전·근거·정책 검수 | — | R23·R16·llm-policy |

**tool (에이전트 아님)** — `booking_slots`/`create_booking`(R18)·`get_history`(R12)·DB 조회.
→ **핸드오프·이력은 전용 에이전트 없이 직접 tool 호출**(결정적 조회·게이트라 추론 루프 불필요).

> 그래뉼래리티 = **1b + Recommend**(ADR-0044) — 진단·커머스에 더해 **추천**도 agent.
> 자연어 추천(need 추론·비교·"왜?")은 비결정적 reasoning이 필요해 tool 단발로는 약하다(ADR-0044 기각 A).
> 단 **선택의 grounding은 결정적 tool**(`recommend`)로 환각 방지. 핸드오프·이력은 결정적이라 tool 유지.

## 3. 리뷰/크리틱 — 조건부 게이트 (확정)

- **발동 조건** — ⓐ 안전 경고 포함(R23) ⓑ 되돌릴 수 없는 커밋(R17, 주문/예약) ⓒ 근거 불확실(R16).
  일반 정보성 응답은 **스킵**(비용·지연 절감).
- **동작** — 최종 직전 **게이트**. 통과 시 방출, 위반 시 해당 부분 **보정/차단**(+커밋이면 ActionGate 확인 유지).
- **단일 패스 정합** — 재실행 루프가 없으므로, 리뷰 위반은 **안전 폴백/사람 연결(R18)** 로 처리(무리한 자동 재생성 금지).

## 4. 계획 / 위임 (단일 패스)

- Supervisor: 분류·분해(구조화 출력, orchestration §4) → **의도별 워커 매핑** → **우선순위(안전/CS 먼저, §6.6)** → 위임.
- **복합(R7)** — 의도별 워커 **fan-out**, 결과를 섹션으로 묶고 **handled/unhandled 구분**.
- **맥락 전달** — Diagnosis의 `required_parts` → Commerce가 이어받음(§6.6 의존 관계).

## 5. 통신 / 상태

- **세션 스크래치패드** — operations §13 `sess:{sid}`(FlowState)에 각 워커가 결과 기록. **워커는 무상태**(컨텍스트는 여기서 로드).
- **스코프 컨텍스트** — 각 에이전트엔 **필요한 부분만** 전달(토큰·격리·프라이버시 R19). 전체 이력 주입 금지(요약, operations §4).
- **구조화 핸드오프** — 에이전트 산출은 **구조화 출력(섹션/Template)**, 자연어 떠넘김 아님(파싱 오류 방지).

## 6. 병렬/직렬 + 스트리밍 매핑

- **병렬** — 독립 워커(진단 · 추천 tool 등) 동시 **fan-out**. **직렬** — 의존(주문은 진단 후), **리뷰는 최종 직전**.
- **다단계 스트리밍**(orchestration §10) — 빠른 DB tool 결과 **즉시 섹션** → 진단 가이드 → 커머스 카드 → (조건부 리뷰) → 최종.
  진행 표시는 **답변 중심 문구**만(operations §11, 시스템·순번 비노출).

## 7. 실패 / 타임아웃 / 폴백 (per agent)

- **에이전트 단계별 타임아웃 + 부분 폴백**(operations §14, R13). 한 워커 실패가 전체를 막지 않는다(부분 degradation).
- 클라이언트 끊김 시 진행 중 워커 **abort**(operations §12).

## 8. 비용 / 관측성

- 워커당 LLM 호출이 누적되므로 **모델 라우팅**(슈퍼바이저·진단 경량, 리뷰 상위 등)·**캐싱**(operations §2)으로 비용·지연 관리.
- **에이전트별 스팬·단계 지연** 추적(operations §14)으로 병목 식별·비용 귀속.

## 9. 테스트 / Mock / 비범위

- 각 에이전트/tool은 **Mock으로 LLM 없이 단위 검증**(orchestration §9). Supervisor 위임 로직은 규칙 기반 분류기로 **결정적 테스트**.
- 실제 프롬프트·평가셋·**리뷰 발동 기준·라우팅 임계**는 구현 단계에서 확정(본 문서는 구조 정의).

## 10. 에이전트별 시스템 프롬프트

프롬프트 **문구의 단일 출처는 `backend/app/orchestrator/prompts.py`** 다(공통 `BASE_POLICY` 프리픽스 + 역할별).
**정책(해야/하지 말아야 할 말·어투·가드레일)의 상위 단일 출처는 `docs/llm-policy.md`** 이며, prompts.py는 이를 에이전트별로 구체화한다.
공통 `BASE_POLICY`는 **안정 프리픽스**라 프롬프트 캐싱에 친화적이다(orchestration §6).

| 에이전트 | 임무(요약) | 핵심 금지 | 출력 |
|---|---|---|---|
| `supervisor` | 의도 분해·우선순위·위임·조립(handled/unhandled) | 도메인 직접 추론·위임 없는 결론 | 위임 계획(구조화) |
| `diagnosis` | 상태 조회 + 해결책 RAG + 출처 + 부품 식별 | 근거 없는 해결책·위험 셀프수리 유도·주문 실행 | device_status·guide_steps(+required_parts) |
| `commerce` | 부품 매칭 + 주문 초안(ActionGate) + 품절 폴백 | 가격/재고 지어내기·무확인 커밋 | product_card·order_summary·confirmation |
| `recommend` | 자연어 need 이해 + 후보 비교·근거 설명 | 가격/사양 날조·근거없는 추천·예산초과 강권 | recommendation_list(근거) |
| `review` | (조건부) 안전·근거·정책 검수 | 새 사실 생성·무리한 재생성 | {pass, issues, action} |

> 발동·라우팅 임계(리뷰 조건, 모델 라우팅)는 구현 단계에서 확정(operations §14, orchestration §10).

## 11. 통합 capability 오케스트레이터 + 하이브리드 병합 (재확정, ADR-0043)

구현이 진행되며 구조를 재확정했다(ADR-0043). 핵심: **오케스트레이터는 하나**이고, "필요한 capability(agent|tool)를 호출 → 병합·정리"한다.

```text
사용자 입력
 → Orchestrator(planner): 의도 분해 + 우선순위(§6.6)
 → capability 선택·실행   [균일 인터페이스 call(input) → result]
      agent : Diagnosis(상태+RAG) · Commerce(매칭+주문초안) · Recommend(자연어 추천, ADR-0044)
      tool  : recommend(grounding) · O2O(Store/Quote) · Handoff(booking) · History
      의존(진단 required_parts → 커머스)은 순차, 독립은 병렬 후보(ADR-0017 보류)
 → Merge(하이브리드): 결정적 섹션 우선순위 스택 + 얇은 LLM 연결문구
 → 조건부 Review(안전 R23·커밋 R17·불확실 R16) → done(빠른 결정적 섹션 먼저)
```

- **그래뉼래리티 = 1b + Recommend**(§2, ADR-0044) — 진단·커머스에 더해 **추천**도 agent(자연어 need 추론·비교·설명). 단 추천의 **선택(랭킹·필터)은 결정적 tool**(`recommend`)로 grounding. O2O·핸드오프·이력은 결정적이라 tool 유지.
- **병합 = 하이브리드(2c)** — 근거(섹션 데이터)는 결정적으로 보존하고, **연결문구(인트로/전환)만 LLM**. 결정적 병합(2a)의 무환각·근거보존 + 자연어 흐름을 절충(2b 신서사이저의 환각·지연 회피).
- **통합** — `core.Orchestrator`(결정적 섹션 백본)가 capability+merge의 골격, `runtime`의 LLM 워커는 그 위의 agent capability. `LLM_BACKED`/`MULTIAGENT` 토글은 "어떤 capability가 LLM-backed인가"로 수렴(후속 리팩터).
- 근거·후보안·기각: **ADR-0043**.

## 12. capability 구조 상세 (ADR-0045)

§11 통합 구조를 동작 수준으로 닫은 상세. 4축 확정.

- **① 출력 = 2채널** — capability는 api-contract §2.1 청크 방출: **delta**(자유 내러티브, 프롬프트 포함/금지 규율로 통제) + **section**(구조화 아티팩트: 카드·리스트·`confirmation`, FE 렌더·커밋 게이트 보존). 순수 free delta(템플릿·커밋 약화)·순수 섹션(자연어 약함) 모두 기각.
  - **포함**: tool 근거·출처(R16)·위험 경고(R23)·추천 근거(R8)·커밋 전 확인(R17).
  - **금지**: 가격/사양/재고/해결책 날조·시스템/대기/순번(ops §11)·동의 밖/민감(R19)·무확인 커밋.
- **② 플래너 = LLM 동적 DAG + 룰 검증** — LLM이 `{steps:[{capability, depends_on, parallel_group}]}` 제안 → 룰이 검증(레지스트리 capability만·사이클 금지·우선순위 정렬·무효시 룰 폴백). 플래너 mock으로 결정적 테스트.
- **③ capability 간 데이터 = turn 블랙보드** — 턴 스코프 `ctx`에 산출(required_parts·device_status·candidates) write/read. `carried_parts`의 일반형.
- **④ 스트리밍/리뷰** — 빠른 결정적 capability(device_status) 먼저 방출(프리페치 ≤2s) → agent → 병합 delta. 커밋 안전은 structured `confirmation`+ActionGate(R17/409)로 보장(스트림 버퍼링 불요).
- **레지스트리** — `{name: Capability(kind=agent|tool, intents, tools, prompt?, deps_hint, priority, emits)}`, 추가=한 엔트리.

> 구현(runtime/core 수렴)은 별도 스펙 후보. 근거·기각: ADR-0045.
