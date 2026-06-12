# 요구사항 (Requirements)

## 개요

슈퍼바이저-워커 멀티에이전트 구조([docs/agents.md](../../docs/agents.md))를 **실제 서빙 경로에 배선**한다.
현재 서빙 경로는 단일 tool-loop([backend/app/orchestrator/legacy.py](../../backend/app/orchestrator/legacy.py))이고, 멀티에이전트는 지연 실측용 벤치([backend/app/orchestrator/multiagent.py](../../backend/app/orchestrator/multiagent.py))로만 존재한다.
이 작업은 Supervisor·Diagnosis·Commerce·조건부 Review를 실제 스트리밍 턴(`/internal/turn`)에 연결하고, **다단계 진행 스트리밍**으로 빈 대기를 줄이며, 기존 **결정적 경로([core.Orchestrator](../../backend/app/orchestrator/core.py))와 `LLM_BACKED` 토글로 공존**시키는 것이 목표다.
**턴 내 병렬화는 보류([ADR-0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md))이며 본 스펙의 비범위**다 — 순차·단일 패스([ADR-0012](../../docs/adr/0012-single-pass.md))를 유지한다.

## 요구사항 목록

### 요구사항 1: 슈퍼바이저 의도 분해·우선순위·위임

**User Story:**
운영자로서, 하나의 사용자 턴을 의도별로 분해해 적합한 워커에 위임하기를 원한다, 그래서 복합 요청도 누락 없이 우선순위대로 처리할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 사용자 턴이 들어오면 THEN 시스템은 슈퍼바이저로 의도를 분해(구조화 출력: `intents`, `is_compound`)해야 한다 (SHALL).
2. WHEN 의도가 분해되면 THEN 시스템은 안전·CS(`device_status`·`troubleshoot`)를 주문(`order`)보다 먼저 두는 우선순위로 정렬해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §4·§6.6)
3. IF 분해된 의도가 진단/커머스 도메인 추론이 필요한 종류면 THEN 시스템은 해당 워커(Diagnosis·Commerce)에 위임해야 한다 (SHALL).
4. IF 분해된 의도가 단순 조회·게이트(추천·예약·이력)면 THEN 시스템은 전용 워커 없이 슈퍼바이저가 직접 tool로 처리해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §2)
5. IF 주문 같은 민감/되돌릴 수 없는 의도면 THEN 시스템은 LLM 분류에만 의존하지 않고 규칙 가드레일로 한 번 더 검증해야 한다 (SHALL). ([docs/orchestration.md](../../docs/orchestration.md) §4)

### 요구사항 2: 진단 워커 배선

**User Story:**
사용자로서, 기기 상태와 증상에 맞는 근거 기반 해결 가이드를 받기를 원한다, 그래서 스스로 문제를 진단·해결할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 진단 의도가 위임되면 THEN 시스템은 Diagnosis 워커에 `get_device_status`·`search_solutions` tool만 노출해 실행해야 한다 (SHALL).
2. WHEN 진단 워커가 해결책을 산출하면 THEN 시스템은 tool 근거가 있는 내용만 사용하고 출처를 함께 제시해야 한다 (SHALL).
3. IF 해결에 부품이 필요하면 THEN 시스템은 `required_parts`를 식별해 Commerce 워커가 이어받도록 전달해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §4)
4. IF 진단 단계가 위험 작업을 포함하면 THEN 시스템은 위험 경고를 표시하고 무리한 셀프 수리를 유도하지 않아야 한다 (SHALL).

### 요구사항 3: 커머스 워커 배선 (커밋 게이트)

**User Story:**
사용자로서, 필요한 부품을 정확히 매칭받고 주문 초안을 확인 후 진행하기를 원한다, 그래서 잘못된 부품이나 무확인 결제를 피할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 주문 의도가 위임되면 THEN 시스템은 Commerce 워커에 `match_parts` tool로 부품을 매칭해야 한다 (SHALL).
2. IF 진단 워커가 `required_parts`를 넘겼고 명시 부품이 없으면 THEN 시스템은 Commerce가 그 부품을 이어받아 매칭해야 한다 (SHALL). ([core.Orchestrator](../../backend/app/orchestrator/core.py) carried_parts 정합)
3. IF 주문이 되돌릴 수 없는 커밋이면 THEN 시스템은 ActionGate 확인 전에 커밋하지 않아야 한다 (SHALL). (R17)
4. IF 부품이 품절이면 THEN 시스템은 대화를 끊지 않고 입고 알림/대체 안내로 폴백해야 한다 (SHALL).

### 요구사항 4: 조건부 리뷰 게이트

**User Story:**
운영자로서, 위험·커밋·불확실 응답만 최종 직전에 검수하기를 원한다, 그래서 안전을 지키면서 불필요한 비용·지연을 피할 수 있다.

**수용기준 (Acceptance Criteria):**
1. IF 응답이 안전 경고를 포함(R23)·되돌릴 수 없는 커밋(R17)·근거 불확실(R16) 중 하나에 해당하면 THEN 시스템은 최종 직전 Review 게이트를 발동해야 한다 (SHALL). ([ADR-0011](../../docs/adr/0011-conditional-review.md))
2. IF 위 조건 어디에도 해당하지 않는 일반 정보성 응답이면 THEN 시스템은 Review를 스킵해야 한다 (SHALL).
3. WHEN Review가 통과(`pass`)하면 THEN 시스템은 해당 응답을 방출해야 한다 (SHALL).
4. IF Review가 위반을 발견하면 THEN 시스템은 해당 부분을 보정/차단하고, 보정이 어려우면 안전 폴백/사람 연결로 처리하며 재계획 루프를 돌리지 않아야 한다 (SHALL). ([ADR-0012](../../docs/adr/0012-single-pass.md))

### 요구사항 5: 다단계 진행 스트리밍

**User Story:**
사용자로서, 멀티에이전트가 느려도 진행 상황을 단계적으로 보기를 원한다, 그래서 빈 대기 없이 응답이 쌓이는 것을 체감할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 턴이 시작되면 THEN 시스템은 빠른 DB/결정적 섹션(`device_status` 등)을 먼저 방출해야 한다 (SHALL). ([docs/orchestration.md](../../docs/orchestration.md) §10, [docs/operations.md](../../docs/operations.md) §14: 첫 의미있는 섹션 ≤ 2~3s)
2. WHILE 각 워커가 실행되는 동안 시스템은 산출 순서(진단 → 커머스 → 조건부 리뷰)대로 `section`/`delta` 청크를 점진 방출해야 한다 (SHALL).
3. WHEN 청크를 방출할 때 THEN 시스템은 [api-contract](../../docs/api-contract.md) §2.1 봉투(`section`/`delta`/`flow`/`done`/`error`)를 그대로 사용해야 한다 (SHALL).
4. WHEN 진행 표시 문구를 낼 때 THEN 시스템은 답변 중심 문구만 사용하고 시스템·대기·순번을 노출하지 않아야 한다 (SHALL). ([docs/operations.md](../../docs/operations.md) §11)

### 요구사항 6: 결정적 경로와의 공존 (LLM_BACKED 토글)

**User Story:**
운영자로서, 멀티에이전트 경로를 토글로 켜고 끄기를 원한다, 그래서 기존 결정적 경로를 회귀 없이 유지하며 점진 도입할 수 있다.

**수용기준 (Acceptance Criteria):**
1. IF `LLM_BACKED`가 꺼져 있으면 THEN 시스템은 기존 결정적 경로([core.Orchestrator](../../backend/app/orchestrator/core.py))로 응답해야 한다 (SHALL).
2. IF `LLM_BACKED`가 켜져 있으면 THEN 시스템은 멀티에이전트 경로로 응답해야 한다 (SHALL).
3. WHEN 두 경로 중 무엇이 응답하든 THEN 시스템은 동일한 [api-contract](../../docs/api-contract.md) §2.1 봉투를 방출해 클라이언트 계약을 깨지 않아야 한다 (SHALL).
4. WHEN `_stream_turn` 디스패치가 경로를 고를 때 THEN 시스템은 매 호출마다 토글을 평가(런타임 env·.env 반영)해야 한다 (SHALL). ([api/internal.py](../../backend/app/api/internal.py) `_llm_backed`)

### 요구사항 7: 비동기 정합 (achat_completion · 세마포어)

**User Story:**
운영자로서, 멀티에이전트의 누적 LLM 호출이 동시성·이벤트 루프를 해치지 않기를 원한다, 그래서 다수 사용자를 동시에 처리할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 멀티에이전트 경로가 LLM을 호출할 때 THEN 시스템은 비동기 래퍼(`achat_completion`)를 사용해 이벤트 루프를 비차단으로 유지해야 한다 (SHALL). ([ADR-0016](../../docs/adr/0016-async-execution-model.md), [backend/app/llm.py](../../backend/app/llm.py))
2. WHILE LLM 호출이 진행되는 동안 시스템은 동시성 세마포어(`LLM_MAX_CONCURRENCY`)와 일시적 오류 백오프를 경유해야 한다 (SHALL).
3. WHEN 한 턴이 워커별로 다회 LLM을 호출할 때 THEN 시스템은 실행을 순차로 유지(턴 내 병렬화 비도입)해야 한다 (SHALL). ([ADR-0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md))

### 요구사항 8: 단계별 실패·부분 폴백

**User Story:**
사용자로서, 한 워커가 실패해도 가능한 부분 응답이라도 받기를 원한다, 그래서 대화가 통째로 끊기지 않는다.

**수용기준 (Acceptance Criteria):**
1. IF 한 워커 단계가 실패/예외면 THEN 시스템은 그 단계만 폴백/생략하고 나머지 부분결과를 반환해야 한다 (SHALL). (R13, [docs/operations.md](../../docs/operations.md) §14)
2. IF Review 단계가 실패면 THEN 시스템은 검수 전 초안이라도 안전 범위에서 제공해야 한다 (SHALL).
3. WHEN 전체 턴이 회복 불가 예외에 빠지면 THEN 시스템은 `error` 봉투(폴백 텍스트)를 방출하고 대화를 중단하지 않아야 한다 (SHALL). ([api-contract](../../docs/api-contract.md) §2.1)

### 요구사항 9: 컴패니언 메모리 정합

**User Story:**
사용자로서, 이전 대화 맥락이 멀티에이전트 응답에도 이어지기를 원한다, 그래서 매번 처음부터 설명하지 않아도 된다.

**수용기준 (Acceptance Criteria):**
1. IF 컴패니언 워킹 컨텍스트(요약+사실)가 있으면 THEN 시스템은 멀티에이전트 경로에서도 이를 이어가기로 주입해야 한다 (SHALL). ([docs/operations.md](../../docs/operations.md) §4-1, [ADR-0040](../../docs/adr/0040-conversation-continuity-compaction.md))
2. WHEN 멀티에이전트 턴이 종료되면 THEN 시스템은 사용자 입력과 어시스턴트 응답을 컴팩션 기록(`record_turn`)에 남겨야 한다 (SHALL). ([api/internal.py](../../backend/app/api/internal.py) `_stream_and_record`)
3. WHEN 맥락을 워커에 전달할 때 THEN 시스템은 전체 이력이 아니라 스코프된 부분만 주입해야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §5)

### 요구사항 10: Mock/결정적 테스트 가능성

**User Story:**
개발자로서, LLM 없이 멀티에이전트 배선을 검증하기를 원한다, 그래서 빠르고 결정적인 회귀 테스트를 돌릴 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 슈퍼바이저 위임을 테스트할 때 THEN 시스템은 규칙 기반 분류기를 주입해 LLM 없이 위임 매핑을 검증할 수 있어야 한다 (SHALL). ([docs/agents.md](../../docs/agents.md) §9)
2. WHEN 리뷰 게이트를 테스트할 때 THEN 시스템은 발동 조건(안전·커밋·불확실)을 LLM 없이 결정적으로 검증할 수 있어야 한다 (SHALL).
3. WHEN 워커/tool을 테스트할 때 THEN 시스템은 Mock tool로 단위 검증할 수 있어야 한다 (SHALL).
4. WHEN 다단계 스트리밍을 테스트할 때 THEN 시스템은 방출 청크의 종류·순서를 결정적으로 단언할 수 있어야 한다 (SHALL).
