# 설계 (Design)

> 이 문서는 [requirements.md](./requirements.md) 의 요구사항을 **어떻게** 만족시킬지 설명한다.
> 공유 모델·결정은 기반 문서를 **링크 참조**하고 여기서 중복 정의하지 않는다:
> 구조·프롬프트 매핑 [docs/agents.md](../../docs/agents.md),
> 의도분류·다단계 스트리밍 [docs/orchestration.md](../../docs/orchestration.md) §4·§10,
> 지연·동시성·메모리 [docs/operations.md](../../docs/operations.md) §4-1·§11·§14·§14-1,
> 응답 봉투 [docs/api-contract.md](../../docs/api-contract.md) §2.1,
> 결정들 [ADR-0009](../../docs/adr/0009-supervisor-worker.md)·[0011](../../docs/adr/0011-conditional-review.md)·[0012](../../docs/adr/0012-single-pass.md)·[0016](../../docs/adr/0016-async-execution-model.md)·[0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md).

## 개요

설계 접근은 **기존 자산의 재배선**이다. 새 토폴로지를 발명하지 않는다.

- 프롬프트는 [prompts.py](../../backend/app/orchestrator/prompts.py)(`SUPERVISOR/DIAGNOSIS/COMMERCE/REVIEW_PROMPT`)에 캐논 텍스트로 이미 존재 → 그대로 사용.
- 멀티에이전트 구조·단계 분해·조건부 리뷰 로직은 벤치 [multiagent.py](../../backend/app/orchestrator/multiagent.py)(`run_multiagent`·`_agent`)에 동기·계측 형태로 이미 존재 → ① **async 화**(`achat_completion`), ② **스트리밍 제너레이터화**(타이밍 수집 대신 청크 방출), ③ **서빙 경로 디스패치 배선**으로 전환.
- 서빙 진입은 [internal.py](../../backend/app/api/internal.py) `_stream_turn` 디스패치가 `LLM_BACKED`로 경로를 고르는 구조가 이미 있음 → **세 번째 경로(멀티에이전트)** 를 끼워 넣되 결정적 경로([core.Orchestrator](../../backend/app/orchestrator/core.py))는 그대로 공존.

핵심 제약: **순차·단일 패스 유지**(턴 내 병렬화는 [ADR-0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md) 보류 = 비범위), 출력은 항상 [api-contract](../../docs/api-contract.md) §2.1 봉투.

## 아키텍처

```mermaid
flowchart TD
    WS["/internal/turn (WS·HTTP)"] --> REC[_stream_and_record]
    REC --> DISP{_stream_turn 디스패치}
    DISP -->|LLM_BACKED=off| DET[core.Orchestrator<br/>결정적 섹션]
    DISP -->|LLM_BACKED=on, MULTIAGENT=off| LEG[legacy.astream_turn<br/>단일 tool-loop]
    DISP -->|LLM_BACKED=on, MULTIAGENT=on| MA[runtime.astream_multiagent]

    MA --> SUP[Supervisor<br/>분해·우선순위·위임]
    SUP -->|device_status·troubleshoot| DIAG[Diagnosis 워커]
    SUP -->|order| COMM[Commerce 워커]
    SUP -->|recommend·booking·history| TOOLS[직접 tool 호출]
    DIAG -->|required_parts 핸드오프| COMM
    DIAG --> GATE{조건부 Review<br/>안전·커밋·불확실}
    COMM --> GATE
    TOOLS --> GATE
    GATE -->|pass/skip| EMIT[청크 방출 done]
    GATE -->|violation| FB[보정/차단·사람연결]

    SUP -. "delta/section 점진 방출" .-> EMIT
    DIAG -. .-> EMIT
    COMM -. .-> EMIT
```

**제어 흐름**(단일 패스, [docs/agents.md](../../docs/agents.md) §1·§4): `분해 → 우선순위 정렬 → 워커 위임(순차) → 조건부 리뷰 → 조립`. 재계획 루프 없음.

**스트리밍 매핑**([docs/orchestration.md](../../docs/orchestration.md) §10): 빠른 DB/결정적 섹션을 **즉시** 방출(첫 의미있는 섹션 ≤ 2~3s, [docs/operations.md](../../docs/operations.md) §14) → 진단 가이드 → 커머스 카드 → (조건부 리뷰 후) 최종.

## 주요 컴포넌트 / 인터페이스

각 항목 끝에 충족 요구사항 번호 표기.

- **`runtime.astream_multiagent(message, screen_context, memory) -> AsyncIterator[dict]`** (신규, 예: `backend/app/orchestrator/runtime.py`): 멀티에이전트 서빙 진입점. [multiagent.py](../../backend/app/orchestrator/multiagent.py) `run_multiagent`의 단계 흐름을 **async·스트리밍**으로 재구성해 §2.1 봉투 청크를 방출한다. [legacy.py](../../backend/app/orchestrator/legacy.py) `astream_turn`과 같은 시그니처·계약. _(요구사항 1, 5, 7, 8, 9)_

- **Supervisor 단계**: `aclassify`(구조화 출력, [legacy.py](../../backend/app/orchestrator/legacy.py) `INTENT_SCHEMA` 재사용)로 의도 분해 → `_PRIORITY`([core.py](../../backend/app/orchestrator/core.py) 재사용: 안전/CS 먼저, order 뒤)로 정렬 → 의도→워커 매핑. 주문 등 민감 의도는 규칙 가드레일로 재검증. _(요구사항 1)_

- **Diagnosis 워커**: `_agent(DIAGNOSIS_PROMPT, ..., allowed=("get_device_status","search_solutions"))` async 버전. 산출에서 `required_parts`를 추출해 핸드오프 컨텍스트에 적재. _(요구사항 2)_

- **Commerce 워커**: `_agent(COMMERCE_PROMPT, ..., allowed=("match_parts",))` async 버전. 명시 부품이 없으면 Diagnosis의 `required_parts`를 이어받아 매칭. 커밋은 ActionGate 게이트([internal.py](../../backend/app/api/internal.py) `POST /internal/orders` 409 경로) 위임 — 워커는 초안까지만. _(요구사항 3)_

- **조건부 Review 게이트**: `should_review(intents, sections) -> bool` (결정적 판정) + `REVIEW_PROMPT` 검수 호출. 발동 조건 = 안전 경고 포함(R23)·커밋(R17)·근거 불확실(R16). 미해당 시 스킵. 위반 시 보정/차단·사람 연결(재계획 없음). _(요구사항 4)_

- **직접 tool 경로**: 추천·예약·이력은 전용 워커 없이 슈퍼바이저가 [tools.py](../../backend/app/tools.py) `call`로 직접 호출([docs/agents.md](../../docs/agents.md) §2). _(요구사항 1)_

- **디스패치 확장**: [internal.py](../../backend/app/api/internal.py) `_stream_turn`에 멀티에이전트 분기를 추가. 게이트는 두 단계 — `_llm_backed()`(기존) + `_multiagent()`(신규 env 토글). off면 기존 단일 tool-loop/결정적 경로 유지. _(요구사항 6)_

- **컴패니언 주입**: `_stream_turn`이 이미 넘기는 `memory`([internal.py](../../backend/app/api/internal.py) `companion.context`)를 Supervisor/워커 system 노트로 주입([legacy.py](../../backend/app/orchestrator/legacy.py) `_memory_note` 재사용). 워커엔 스코프된 부분만. 종료 후 `_stream_and_record`가 `record_turn` 기록(기존 배선 그대로). _(요구사항 9)_

- **async/세마포어 정합**: 모든 LLM 호출은 [llm.py](../../backend/app/llm.py) `achat_completion`(AsyncOpenAI + async 세마포어 `LLM_MAX_CONCURRENCY` + 백오프) 경유. 실행 순차 유지. _(요구사항 7)_

## 데이터 모델

새 도메인 모델은 도입하지 않는다(공유 모델은 [docs/data-model.md](../../docs/data-model.md)). 런타임 내부 전달용 경량 구조만 둔다.

- **핸드오프 컨텍스트(인메모리, 턴 스코프)**: `{ "required_parts": list[str], "device_status": dict|None }` — Diagnosis → Commerce 전달([docs/agents.md](../../docs/agents.md) §4·§5, [core.py](../../backend/app/orchestrator/core.py) `carried_parts` 정합).
- **워커 입력 스코프**: 각 워커에 `{system, user_msg(+memory note), allowed_tools}` 만 전달(전체 이력 금지, [docs/agents.md](../../docs/agents.md) §5).
- **방출 청크**: [api-contract](../../docs/api-contract.md) §2.1 봉투(`section`/`delta`/`flow`/`done`/`error`) 그대로. 새 타입 추가 없음.
- **Review 판정 결과**: `{pass: bool, issues: list, action: 'emit'|'revise'|'handoff'}`([prompts.py](../../backend/app/orchestrator/prompts.py) `REVIEW_PROMPT` 출력 규약).

## 에러 처리

[docs/operations.md](../../docs/operations.md) §14(단계별 타임아웃 + 부분 폴백) · R13 기준.

- **워커 단계 실패**: 해당 단계만 try/except로 감싸 폴백/생략하고 **이미 방출한 부분결과는 유지**, 나머지 단계 계속. _(요구사항 8-1)_
- **Review 실패**: 검수 전 초안을 안전 범위에서 방출(리뷰 타임아웃 = 초안 제공). _(요구사항 8-2)_
- **턴 전체 회복 불가**: `error` 봉투(폴백 텍스트)를 방출하고 대화를 끊지 않음([legacy.py](../../backend/app/orchestrator/legacy.py) `astream_turn` 폴백 패턴 재사용). _(요구사항 8-3)_
- **커밋 안전**: 주문은 워커가 직접 커밋하지 않고 게이트로(미확인 시 409 ConfirmationRequired). _(요구사항 3-3)_
- **단계별 타임아웃 도입은 본 스펙 범위**(글로벌 1개 → 단계별)이되, fine-grained abort([ADR-0018](../../docs/adr/0018-stage-timeout-abort-deferred.md))는 보류 유지.

## 테스트 전략

[docs/agents.md](../../docs/agents.md) §9 · [docs/orchestration.md](../../docs/orchestration.md) §9 기준 — **LLM 없이 결정적 검증** 우선.

- **슈퍼바이저 위임 매핑(단위)**: 규칙 기반 분류기(또는 분류 결과 스텁) 주입 → 의도별 워커/직접-tool 매핑·우선순위 정렬을 LLM 없이 단언. _(요구사항 10-1)_
- **리뷰 게이트(단위)**: `should_review` 결정 함수를 안전/커밋/불확실 케이스로 직접 호출해 발동/스킵을 단언(LLM 미발동). _(요구사항 10-2)_
- **워커·tool(단위)**: Mock tool([tools.py](../../backend/app/tools.py) `call`)로 진단·커머스 실행, `required_parts` 핸드오프 정합 검증. _(요구사항 10-3)_
- **다단계 스트리밍(통합)**: 방출 청크의 **종류·순서**(빠른 섹션 → 진단 → 커머스 → 리뷰 → done)를 결정적으로 단언. _(요구사항 10-4, 5)_
- **공존(회귀)**: `LLM_BACKED`/멀티에이전트 토글 off에서 기존 결정적 경로 테스트가 그대로 통과(봉투 동일). _(요구사항 6)_
- **부분 폴백**: 한 워커가 예외를 던지도록 패치 → 나머지 부분결과 + 비중단 단언. _(요구사항 8)_
- **메모리 정합**: `memory` 주입 시 워커 system 노트 포함, 턴 종료 후 `record_turn` 호출 단언. _(요구사항 9)_

## 설계 결정 / 대안

- **벤치 재사용 vs 신규 구현**: [multiagent.py](../../backend/app/orchestrator/multiagent.py)는 동기·계측용이라 그대로 서빙 불가(스트리밍 계약 없음, blocking `chat_completion`). 구조·단계 분해 로직을 **이식**하되 런타임은 별도 모듈로 분리(벤치는 지연 실측 자산으로 보존). 대안(벤치를 직접 개조)은 계측 자산을 잃어 기각.
- **순차 유지(병렬 미도입)**: [ADR-0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md) 보류를 따른다. 진단∥커머스 병렬은 의존 위반·일관성·동시성 예산 리스크 → 슈퍼바이저 의존 그래프 선행 시 재검토. **본 스펙 비범위.**
- **조건부 리뷰(항상 아님)**: [ADR-0011](../../docs/adr/0011-conditional-review.md) — 안전·커밋·불확실만 발동, 일반 정보성은 스킵(비용·지연 절감). 위반은 단일 패스([ADR-0012](../../docs/adr/0012-single-pass.md))라 재실행 대신 폴백/사람 연결.
- **공존 토글**: 기존 `_llm_backed()` 패턴을 따른 **매 호출 평가** env 토글(런타임 반영). 결정적 경로를 기본값으로 두어 회귀 위험 0.
- **스트리밍으로 지연 흡수**: 실측 복합 ~21s([docs/operations.md](../../docs/operations.md) §14-1)는 완료 시간이 길다 → 다단계 스트리밍으로 **체감(첫 섹션 ≤2~3s)** 을 개선(총 완료 단축은 병렬화 몫, 보류).
- **프롬프트 단일 출처**: 문구는 [prompts.py](../../backend/app/orchestrator/prompts.py)([ADR-0013](../../docs/adr/0013-prompt-single-source.md)) — 런타임은 참조만, 재정의 금지.
