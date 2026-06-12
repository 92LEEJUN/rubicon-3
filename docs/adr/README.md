# 결정 기록 (ADR — Architecture Decision Records)

> 이 폴더는 레포의 **설계 결정**을 **최소 단위로 번호를 매겨** 기록한다.
> 각 ADR은 **배경 → 후보안 → 선택 → 근거 → 기각 이유 → 상태**를 담아, *무엇을 고려했고 왜 그걸 골랐는지*를 남긴다.
>
> - **기반 문서(`docs/*.md`)** = 결정의 *결과*(현재 진실). **ADR** = 결정의 *이유와 대안*.
> - **스펙(`specs/<작업명>/`)** = 기능별 requirements/design/tasks. ADR을 참조한다.
> - 번호는 대략 **시간/계층 순서**(기반 → 멀티에이전트 → Phase A).

## 상태 범례
`채택`(반영됨) · `구현됨`(코드 반영) · `보류`(결정 미룸/안 함) · `대체됨`

## 목록

### 기반 — 동시성 / 운영 (operations.md)
| # | 결정 | 상태 |
|---|---|---|
| [0001](0001-two-plane-interactive-async.md) | 인터랙티브/비동기 **2-플레인 분리** | 채택 |
| [0002](0002-concurrency-path-a-to-b.md) | 동시성 채택 경로 **A(인프로세스)→B(Redis)**, C·D 보류 | 채택 |
| [0003](0003-session-serialization.md) | 세션 직렬화 = **FE 입력차단 + 서버 세션락** | 채택 |
| [0004](0004-backpressure-hidden.md) | **백프레셔 무노출 + 점진 렌더**(적응형 강등 제외) | 채택 |
| [0005](0005-sla-shape.md) | SLA = **목표+관측+오토스케일**(능동 강등 안 함) | 채택 |
| [0006](0006-phase-b-redis-topology.md) | Phase B **무상태 워커 + Redis** 토폴로지 | 채택(설계) |
| [0007](0007-streaming-relay-deferred.md) | 스트리밍 릴레이 **Streams vs Pub/Sub** | 보류 |

### 멀티에이전트 (agents.md)
| # | 결정 | 상태 |
|---|---|---|
| [0008](0008-multiagent-latency.md) | 멀티에이전트 **지연 고려 반영**(SLA 재정의·N배) | 채택 |
| [0009](0009-supervisor-worker.md) | 제어 패턴 = **슈퍼바이저-워커** | 채택 |
| [0010](0010-agent-granularity.md) | 그래뉼래리티 = **중간**(진단·커머스만 에이전트) | 채택 |
| [0011](0011-conditional-review.md) | 리뷰/크리틱 = **조건부** | 채택 |
| [0012](0012-single-pass.md) | 계획 = **단일 패스**(재계획 루프 없음) | 채택 |
| [0013](0013-prompt-single-source.md) | 에이전트 프롬프트 **단일 출처 = prompts.py** | 구현됨 |

### Phase A — 스트리밍 / 동시성 실행 (operations.md §6·§9·§14)
| # | 결정 | 상태 |
|---|---|---|
| [0014](0014-phase-a-streaming-first.md) | Phase A 우선순위 = **스트리밍 먼저** | 채택 |
| [0015](0015-streaming-scope-2a.md) | 증분 스트리밍 범위 = **2a만**(2b 후속) | 구현됨 |
| [0016](0016-async-execution-model.md) | 실행 모델 = **async 전환**(순차 유지) | 구현됨 |
| [0017](0017-intra-turn-parallelism-deferred.md) | 후보1 **턴 내 병렬화** | 보류 |
| [0018](0018-stage-timeout-abort-deferred.md) | 후보3 **단계 타임아웃·fine abort** | 보류 |
