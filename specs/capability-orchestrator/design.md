# 설계 (Design)

> [requirements.md](./requirements.md) 의 요구사항을 **어떻게** 만족시킬지 설명한다.
> 공유 결정·모델은 기반 문서를 참조한다 — **통합 [ADR-0043](../../docs/adr/0043-capability-orchestrator.md), 추천 agent [ADR-0044](../../docs/adr/0044-recommend-as-agent.md), 상세 4축 [ADR-0045](../../docs/adr/0045-capability-structure-detail.md), [docs/agents.md](../../docs/agents.md) §11·§12**. 여기선 수렴 리팩터 고유 설계만 담는다.

## 개요

세 서빙 경로(결정적 [core.Orchestrator](../../backend/app/orchestrator/core.py) · 단일 tool-loop [legacy.astream_turn](../../backend/app/orchestrator/legacy.py) · 멀티에이전트 [runtime.astream_multiagent](../../backend/app/orchestrator/runtime.py))를 **하나의 capability 오케스트레이터**로 수렴한다. 전환은 **스트랭글러** — 새 골격(레지스트리·플래너·블랙보드·균일 인터페이스)을 세우고, 기존 `handlers.handle_*`(결정적)과 `runtime` 워커(LLM)를 **capability 단위로 하나씩 감싸 이주**하며, 매 단계 "LLM 전부 off = 기존 결정적 봉투 동일" 회귀로 green을 유지한다. 옛 경로는 패리티 증명 후 마지막에 삭제한다.

핵심: 클라이언트 계약([api-contract](../../docs/api-contract.md) §2.1 봉투)·도메인 모델([MessageSection](../../backend/app/domain/models.py))은 **불변**. capability는 이 봉투를 방출하는 **2채널**(delta+section) 단위일 뿐이다.

## 아키텍처

```text
/internal/turn (WS)  →  _stream_turn  →  CapabilityOrchestrator.astream(message, screen_context, memory)
                                          │
  ┌───────────────────────────────────────┴────────────────────────────────────────┐
  │ 1) plan      : LLMPlanner.propose(catalog, message, ctx) → Plan{steps[...]}       │
  │               → PlanValidator.validate(plan, registry)  (미등록·사이클·우선순위)  │
  │               → 무효/실패 시 rule_plan(intents)  폴백                              │
  │ 2) execute   : for step in plan (depends_on 순서, 순차):                          │
  │                  cap = registry[step.capability]                                 │
  │                  async for chunk in cap.call(input, ctx):  yield chunk           │
  │                  ctx.write(cap.emits)        ← turn 블랙보드                       │
  │ 3) merge     : 결정적 section 우선순위 스택 + 얇은 LLM 연결 delta (무환각)         │
  │ 4) review    : should_review(intents, safety, uncertain) → 조건부 게이트          │
  │               (커밋 안전 = confirmation section + ActionGate/409, 버퍼링 없음)     │
  └──────────────────────────────────────────────────────────────────────────────────┘
                                          │
                              section* · delta* · flow · done (또는 error)
```

- **순차 단일 패스** 유지 — `parallel_group`은 *표기*만, 실행은 순차([ADR-0017](../../docs/adr/0017-intra-turn-parallelism-deferred.md)·[ADR-0012](../../docs/adr/0012-single-pass.md)).
- 기존 결정적 로직(`_PRIORITY`·`plan_workers`·`carried_parts`)은 **버리지 않고** 룰 폴백·검증·블랙보드의 토대로 재사용한다.

## 주요 컴포넌트 / 인터페이스

새 모듈 **`backend/app/orchestrator/capability.py`** (+ 레지스트리 `registry.py`, 플래너 `planner.py`). 시그니처는 기존 타입에 정합.

- **`Capability`** (dataclass) — 레지스트리 엔트리 _(요구사항 1, 2)_
  ```python
  Chunk = dict  # api-contract §2.1 봉투: {"type":"delta"|"section"|"flow"|...}

  @dataclass(frozen=True)
  class Capability:
      name: str
      kind: Literal["agent", "tool"]
      intents: tuple[str, ...]          # 이 capability가 처리하는 의도
      emits: tuple[str, ...]            # 블랙보드에 쓰는 슬롯 (예: "required_parts")
      needs: tuple[str, ...] = ()       # 블랙보드에서 읽는 슬롯 (의존)
      priority: int = 2                 # _PRIORITY 정합 (안전·CS 먼저)
      tools: tuple[str, ...] = ()       # kind=agent: 허용 tool (TOOLS 부분집합)
      prompt: Optional[str] = None      # kind=agent: prompts.py 참조 (본문 비주입)
      run: CapabilityFn                 # 균일 인터페이스 (아래)
  ```
- **균일 인터페이스** `CapabilityFn = Callable[[CapInput, TurnCtx], AsyncIterator[Chunk]]` _(요구사항 2-1)_
  - `kind=tool` 래퍼: 기존 `handlers.handle_*` 호출 → `MessageSection` → `{"type":"section", ...}` 방출(결정적, delta 없음). _(요구사항 2-3, 8-2)_
  - `kind=agent` 래퍼: 기존 `runtime._run_worker(prompt, msg, allowed)` 호출 → 설명 `delta` + 구조화 `section`. _(요구사항 2-3·2-4·2-5)_
- **`CapabilityRegistry`** — `{name: Capability}`, `catalog()`는 `name·intents·needs·설명`만 노출(프롬프트 비노출). 추가=한 엔트리 등록. _(요구사항 1)_
- **`LLMPlanner.propose(catalog, message, ctx) -> Plan`** — 구조화 출력 `Plan{steps:[Step{capability, depends_on, parallel_group}]}`. `achat_completion`(async·세마포어) 경유. 주입형(테스트 스텁). _(요구사항 3-1, 7=async)_
- **`PlanValidator.validate(plan, registry) -> Plan | None`** — 미등록 capability·의존 사이클 거르고 `priority`로 위상정렬. 무효면 `None`. _(요구사항 3-2)_
- **`rule_plan(intents) -> Plan`** — 기존 `core._ordered_intents`+`runtime.plan_workers` 매핑을 Plan으로. 플래너 폴백·결정적 경로의 본체. _(요구사항 3-3, 8)_
- **`TurnCtx`** (turn 블랙보드) — `write(slot, value)` / `read(slot)`. `carried_parts`의 일반형. capability엔 스코프된 부분만 노출. _(요구사항 4)_
- **`merge(sections, ctx) -> AsyncIterator[Chunk]`** — 결정적 section 우선순위 스택 보존 + 연결 delta만 얇은 LLM(섹션 사실 불변). _(요구사항 5)_
- **`CapabilityOrchestrator.astream(...)`** — 위 1)~4) 조립. `astream_multiagent`와 동일 시그니처(드롭인). _(요구사항 6, 8)_

**디스패치 수렴** ([internal.py](../../backend/app/api/internal.py) `_stream_turn`) — 세 경로를 capability 경로로 흡수. 토글은 **capability 단위 LLM-backed 여부**로 평가(매 호출 env 반영). 이주 중에는 미이주 의도만 옛 경로로 위임하는 분기를 임시 유지. _(요구사항 8)_

## 데이터 모델

신규 도메인 타입은 최소화 — 출력은 기존 [domain/models.py](../../backend/app/domain/models.py)를 그대로 쓴다.
- **재사용(불변):** `MessageSection`·`Template`·`Cta`·`AssistantTurn` — section 채널. `{"type":"delta","text"}` — delta 채널. (api-contract §2.1)
- **신규(오케스트레이터 내부 전용, 봉투 아님):** `Capability`·`Plan`/`Step`·`TurnCtx`. 클라이언트로 새지 않는다.
- **블랙보드 슬롯 초기 집합:** `required_parts`(진단→커머스, 기존 정합)·`device_status`·`candidates`(추천). 등록 시 `emits`/`needs`로 선언.

## 에러 처리 _(요구사항 9)_
- **step 실패** — 해당 step만 try/except 폴백/생략, 부분결과 유지(기존 `runtime` 스테이지 패턴 재사용, R13).
- **플래너 LLM 실패/무효** — `rule_plan` 폴백으로 계속(요구사항 3-3 정합).
- **턴 전체 회복 불가** — `{"type":"error", "fallback":...}` 봉투(비중단, core.stream_turn 패턴).
- **리뷰 실패** — 검수 전 초안 안전 범위 제공.

## 테스트 전략 _(요구사항 10)_
- **회귀(핵심)** — 모든 LLM capability off에서 `CapabilityOrchestrator` 출력이 기존 `core.Orchestrator`와 **동일 봉투**임을 단언. 기존 `test_orchestrator.py`(J1 carried_parts·compound·stream envelope·fallback)를 새 경로로 재실행. _(요구사항 10-5, 8-2)_
- **플래너/검증** — Plan 스텁 주입으로 미등록·사이클·빈 plan→`rule_plan` 폴백을 LLM 없이 단언. _(요구사항 10-1, 10-2)_
- **블랙보드 핸드오프** — `required_parts` write→read(진단→커머스)를 Mock tool로 단언(기존 `test_runtime.test_extract_required_parts` 계승). _(요구사항 10-3)_
- **스트리밍·병합** — 방출 청크 종류·순서 결정적 단언(기존 `test_streaming_order_compound` 계승). _(요구사항 10-4)_
- 픽스처는 기존 `conftest.container`+Mock 어댑터 패턴 유지, capability 레지스트리 주입 추가.

## 설계 결정 / 대안

- **전환 = 스트랭글러(A).** handler/worker를 capability 단위로 감싸 레지스트리(ADR-0045)로 수렴하며 매 단계 green. 대안 B(빅뱅)는 기존 테스트 대비 회귀 위험·중간 배포 불가로 기각. 대안 C(오케스트레이터 통째 어댑터)는 그래뉼래리티가 굵어 레지스트리 비전과 어긋나고 중복을 오래 끌어 기각.
- **출력 2채널·LLM 플래너(검증)·블랙boards·하이브리드 병합**의 근거·기각은 ADR-0043/0044/0045에 있음(여기서 재논증 안 함).
- **기존 로직 재사용** — `_PRIORITY`·`plan_workers`·`carried_parts`·`should_review`·`_run_worker`는 버리지 않고 룰 폴백·검증·블랙보드·agent 래퍼의 토대로 재배치.
