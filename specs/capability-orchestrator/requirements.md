# 요구사항 (Requirements)

## 개요

오케스트레이터를 **단일 capability 기반 구조로 수렴**한다. 현재 서빙 경로는 결정적 백본([core.Orchestrator](../../backend/app/orchestrator/core.py))과 LLM 멀티에이전트([runtime](../../backend/app/orchestrator/runtime.py))가 `LLM_BACKED`/멀티에이전트 토글로 **이원 공존**한다([multi-agent-runtime](../multi-agent-runtime/)). 이 작업은 둘을 **하나의 오케스트레이터 + capability 레지스트리**로 합쳐, "필요한 capability(agent|tool)를 플래너가 골라 실행 → 하이브리드 병합 → 조건부 리뷰"의 단일 골격으로 만든다.

근거·결정은 기반 문서를 참조한다 — **통합 구조 [ADR-0043](../../docs/adr/0043-capability-orchestrator.md), 추천 agent [ADR-0044](../../docs/adr/0044-recommend-as-agent.md), capability 상세 4축 [ADR-0045](../../docs/adr/0045-capability-structure-detail.md), [docs/agents.md](../../docs/agents.md) §11·§12**. 본 스펙은 그 위에 **수렴 리팩터의 기능 고유 설계**만 담는다.

**비범위:** 턴 내 병렬 실행은 보류([ADR-0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md)) — 플래너는 `parallel_group`을 *표기*하되 실행은 순차 유지. 새 도메인 capability 추가(예: 신규 워커)는 본 스펙이 아닌 후속. 클라이언트 계약(api-contract §2.1 봉투)·데이터 모델은 **불변**(기존 FE 회귀 금지).

## 요구사항 목록

### 요구사항 1: capability 레지스트리

**User Story:**
운영자로서, 오케스트레이터가 다룰 수 있는 capability를 한 곳의 레지스트리로 선언하기를 원한다, 그래서 새 capability 추가가 한 엔트리로 끝나고 플래너·실행이 동일 목록을 참조할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 오케스트레이터가 초기화되면 THEN 시스템은 capability를 `{name: Capability(kind=agent|tool, intents, tools, prompt?, deps_hint, priority, emits)}` 레지스트리로 보유해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §12)
2. WHEN 새 capability를 추가할 때 THEN 시스템은 레지스트리에 한 엔트리를 더하는 것만으로 플래너 후보·실행 디스패치에 반영해야 한다 (SHALL).
3. IF capability가 `kind=agent`면 THEN 시스템은 자체 LLM tool-loop(프롬프트·허용 tool)로 실행하고, `kind=tool`이면 결정적 호출로 실행해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §2)
4. WHEN 플래너가 capability 카탈로그를 받을 때 THEN 시스템은 레지스트리에서 `name·설명·intents·needs`만 노출(프롬프트 본문 비노출)해야 한다 (SHALL).

### 요구사항 2: 균일 capability 인터페이스 (2채널 출력)

**User Story:**
개발자로서, 모든 capability가 동일한 입출력 계약을 따르기를 원한다, 그래서 오케스트레이터가 agent든 tool이든 같은 방식으로 실행·병합할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 어떤 capability가 실행되면 THEN 시스템은 균일 인터페이스 `call(input, ctx) → AsyncIterator[chunk]`로 호출해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §11)
2. WHEN capability가 청크를 방출할 때 THEN 시스템은 [api-contract](../../docs/api-contract.md) §2.1 봉투의 **2채널** — `delta`(자유 내러티브) + `section`(구조화 아티팩트) — 만 사용해야 한다 (SHALL). ([ADR-0045](../../docs/adr/0045-capability-structure-detail.md) ①)
3. IF capability가 `kind=agent`면 THEN 시스템은 `delta`(설명)와 `section`(구조화 산출)을 모두 낼 수 있고, `kind=tool`이면 `section` 중심으로 내야 한다 (SHALL).
4. WHEN `delta` 내러티브를 생성할 때 THEN 시스템은 프롬프트의 **포함 규율**(tool 근거·출처 R16·위험 경고 R23·추천 근거 R8·커밋 전 확인 R17)을 따라야 한다 (SHALL).
5. WHEN `delta` 내러티브를 생성할 때 THEN 시스템은 프롬프트의 **금지 규율**(가격·사양·재고·해결책 날조 / 시스템·대기·순번 노출 / 동의 밖·민감정보 R19 / 무확인 커밋)을 위반하지 않아야 한다 (SHALL). ([docs/llm-policy.md](../../docs/llm-policy.md), [docs/operations.md](../../docs/operations.md) §11)
6. WHEN 구조화 아티팩트(카드·리스트·`confirmation`)를 낼 때 THEN 시스템은 `section`(Template)으로 내어 FE 리치 렌더·커밋 게이트를 보존해야 한다 (SHALL). ([ADR-0025](../../docs/adr/0025-structured-templates.md), R17)

### 요구사항 3: LLM 플래너 + 룰 검증/폴백

**User Story:**
운영자로서, 플래너가 의도·맥락에 따라 필요한 capability를 동적으로 선택하되 안전하게 검증되기를 원한다, 그래서 유연함과 결정성을 동시에 얻는다.

**수용기준 (Acceptance Criteria):**
1. WHEN 사용자 턴이 들어오면 THEN 시스템은 LLM 플래너로 의도·맥락을 분석해 구조화 plan `{steps:[{capability, depends_on, parallel_group}]}`을 제안해야 한다 (SHALL). ([ADR-0045](../../docs/adr/0045-capability-structure-detail.md) ②)
2. WHEN 플래너 plan을 받으면 THEN 시스템은 룰로 검증 — 레지스트리에 존재하는 capability만 허용, 의존 사이클 금지, 우선순위(안전·CS 먼저, [specs/mvp-concierge/design.md](../mvp-concierge/design.md) §6.6)로 정렬 — 해야 한다 (SHALL).
3. IF 플래너 plan이 비었거나 무효(미등록 capability·사이클)면 THEN 시스템은 규칙 기반 매핑으로 폴백해야 한다 (SHALL).
4. IF 주문 같은 되돌릴 수 없는 의도면 THEN 시스템은 LLM 플래너에만 의존하지 않고 규칙 가드레일로 한 번 더 검증해야 한다 (SHALL). ([docs/orchestration.md](../../docs/orchestration.md) §4)
5. WHEN 검증된 plan을 실행할 때 THEN 시스템은 `depends_on` 순서를 지키고, 독립 step은 `parallel_group`으로 *표기*하되 실행은 순차로 유지해야 한다 (SHALL). ([ADR-0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md))

### 요구사항 4: turn 블랙보드 (capability 간 데이터)

**User Story:**
개발자로서, capability가 산출한 데이터를 의존 capability가 이어받기를 원한다, 그래서 `carried_parts` 같은 핸드오프를 일반화된 한 메커니즘으로 처리한다.

**수용기준 (Acceptance Criteria):**
1. WHEN capability가 실행될 때 THEN 시스템은 턴 스코프 공유 컨텍스트(블랙보드, `ctx`)를 전달해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §12 ③)
2. WHEN capability가 산출(예: `required_parts`·`device_status`·`candidates`)을 내면 THEN 시스템은 이를 블랙보드에 write해야 한다 (SHALL).
3. IF 의존 capability(예: Commerce)가 선행 산출을 필요로 하면 THEN 시스템은 블랙보드에서 read해 이어받아야 한다 (SHALL). (기존 `carried_parts` 정합)
4. WHEN 블랙보드를 capability에 전달할 때 THEN 시스템은 스코프된 필요한 부분만 주입(전체 이력 금지)해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §5)

### 요구사항 5: 하이브리드 병합

**User Story:**
사용자로서, 여러 capability 산출이 매끄러운 하나의 응답으로 합쳐지기를 원한다, 그래서 끊긴 섹션 나열이 아니라 자연스러운 흐름으로 읽힌다.

**수용기준 (Acceptance Criteria):**
1. WHEN 여러 capability 산출을 병합할 때 THEN 시스템은 근거(섹션 데이터)를 결정적으로 보존하고 우선순위 스택으로 배치해야 한다 (SHALL). ([ADR-0043](../../docs/adr/0043-capability-orchestrator.md))
2. WHEN 섹션을 이을 때 THEN 시스템은 연결문구(인트로/전환)만 얇은 LLM `delta`로 생성해야 한다 (SHALL).
3. WHEN 병합 연결문구를 생성할 때 THEN 시스템은 섹션의 사실을 바꾸거나 새 사실을 만들지 않아야 한다 (SHALL, 무환각).
4. IF 복합 의도(R7)면 THEN 시스템은 의도별 산출을 섹션으로 묶고 handled/unhandled를 구분해야 한다 (SHALL).

### 요구사항 6: 다단계 스트리밍 (빠른 결정적 먼저)

**User Story:**
사용자로서, 느린 LLM capability를 기다리는 동안에도 빠른 결과를 먼저 보기를 원한다, 그래서 빈 대기 없이 응답이 쌓이는 것을 체감한다.

**수용기준 (Acceptance Criteria):**
1. WHEN 턴이 시작되면 THEN 시스템은 빠른 결정적 capability(`device_status` 등) 산출을 먼저 방출(첫 의미있는 섹션 ≤ 2~3s)해야 한다 (SHALL). ([docs/operations.md](../../docs/operations.md) §14, [ADR-0045](../../docs/adr/0045-capability-structure-detail.md) ④)
2. WHILE capability가 실행되는 동안 시스템은 plan 순서대로 `section`/`delta` 청크를 점진 방출해야 한다 (SHALL).
3. WHEN 진행 표시 문구를 낼 때 THEN 시스템은 답변 중심 문구만 사용하고 시스템·대기·순번을 노출하지 않아야 한다 (SHALL). ([docs/operations.md](../../docs/operations.md) §11)

### 요구사항 7: 조건부 리뷰 + 커밋 안전

**User Story:**
운영자로서, 위험·커밋·불확실 응답만 검수하면서 커밋 안전은 결정적으로 보장하기를 원한다, 그래서 안전을 지키며 불필요한 비용·지연을 피한다.

**수용기준 (Acceptance Criteria):**
1. IF 응답이 안전 경고(R23)·되돌릴 수 없는 커밋(R17)·근거 불확실(R16) 중 하나면 THEN 시스템은 최종 직전 Review 게이트를 발동해야 한다 (SHALL). ([ADR-0011](../../docs/adr/0011-conditional-review.md))
2. IF 위 조건 어디에도 해당하지 않으면 THEN 시스템은 Review를 스킵해야 한다 (SHALL).
3. WHEN 되돌릴 수 없는 커밋을 처리할 때 THEN 시스템은 structured `confirmation` 섹션 + ActionGate(R17/409)로 안전을 보장하고, 이를 위해 스트림을 버퍼링하지 않아야 한다 (SHALL). ([ADR-0033](../../docs/adr/0033-action-gate.md), [ADR-0045](../../docs/adr/0045-capability-structure-detail.md) ④)
4. IF Review가 위반을 발견하면 THEN 시스템은 보정/차단·사람 연결로 처리하고 재계획 루프를 돌리지 않아야 한다 (SHALL). ([ADR-0012](../../docs/adr/0012-single-pass.md))

### 요구사항 8: 토글 수렴 (이원 공존 → 단일 경로)

**User Story:**
운영자로서, `LLM_BACKED`/멀티에이전트 토글을 "어떤 capability가 LLM-backed인가"로 수렴하기를 원한다, 그래서 두 오케스트레이터를 유지하지 않고 한 경로로 점진 전환한다.

**수용기준 (Acceptance Criteria):**
1. WHEN 오케스트레이터가 capability를 실행할 때 THEN 시스템은 토글을 **capability 단위 LLM-backed 여부**로 평가해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §11)
2. IF 모든 LLM capability가 꺼져 있으면 THEN 시스템은 결정적 tool capability만으로 기존 결정적 경로와 동등한 응답을 내야 한다 (SHALL). (회귀 금지)
3. WHEN 어느 토글 상태든 THEN 시스템은 동일한 [api-contract](../../docs/api-contract.md) §2.1 봉투를 방출해 클라이언트 계약을 깨지 않아야 한다 (SHALL).
4. WHEN 디스패치가 토글을 평가할 때 THEN 시스템은 매 호출마다 런타임 env를 반영해야 한다 (SHALL). ([backend/app/api/internal.py](../../backend/app/api/internal.py) `_llm_backed` 패턴)

### 요구사항 9: 단계별 실패·부분 폴백

**User Story:**
사용자로서, 한 capability가 실패해도 가능한 부분 응답이라도 받기를 원한다, 그래서 대화가 통째로 끊기지 않는다.

**수용기준 (Acceptance Criteria):**
1. IF 한 capability step이 실패/예외면 THEN 시스템은 그 step만 폴백/생략하고 나머지 부분결과를 반환해야 한다 (SHALL). (R13, [docs/operations.md](../../docs/operations.md) §14)
2. IF 플래너 LLM 호출이 실패면 THEN 시스템은 규칙 폴백 plan으로 계속해야 한다 (SHALL). (요구사항 3-3 정합)
3. WHEN 전체 턴이 회복 불가 예외에 빠지면 THEN 시스템은 `error` 봉투(폴백 텍스트)를 방출하고 대화를 중단하지 않아야 한다 (SHALL). ([api-contract](../../docs/api-contract.md) §2.1)

### 요구사항 10: Mock/결정적 테스트 가능성

**User Story:**
개발자로서, LLM 없이 capability 오케스트레이션을 검증하기를 원한다, 그래서 빠르고 결정적인 회귀 테스트를 돌릴 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 플래너를 테스트할 때 THEN 시스템은 plan을 스텁 주입해 LLM 없이 plan 검증·폴백을 결정적으로 단언할 수 있어야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §9)
2. WHEN 룰 검증을 테스트할 때 THEN 시스템은 미등록 capability·사이클·빈 plan에 대한 폴백을 LLM 없이 검증할 수 있어야 한다 (SHALL).
3. WHEN capability를 테스트할 때 THEN 시스템은 Mock tool/스텁 LLM으로 단위 검증하고, 블랙보드 핸드오프(`required_parts`)를 단언할 수 있어야 한다 (SHALL).
4. WHEN 다단계 스트리밍·병합을 테스트할 때 THEN 시스템은 방출 청크의 종류·순서를 결정적으로 단언할 수 있어야 한다 (SHALL).
5. WHEN 토글 수렴을 테스트할 때 THEN 시스템은 모든 LLM capability off에서 결정적 경로와 동등한 봉투를 내는지 회귀 단언할 수 있어야 한다 (SHALL). (요구사항 8-2)
