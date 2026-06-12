# 결정 기록 (ADR — Architecture Decision Records)

> 이 폴더는 레포의 **설계 결정**을 **최소 단위로 번호를 매겨** 기록한다.
> 각 ADR은 **배경 → 후보안 → 선택 → 근거 → 기각 이유 → 상태**를 담아, *무엇을 고려했고 왜 그걸 골랐는지*를 남긴다.
>
> - **기반 문서(`docs/*.md`)** = 결정의 *결과*(현재 진실). **ADR** = 결정의 *이유와 대안*.
> - **스펙(`specs/<작업명>/`)** = 기능별 requirements/design/tasks. ADR을 참조한다.
> - 번호는 **추가 순서**다(엄밀한 시간순 아님). 0001~0018은 최근 운영/멀티에이전트/Phase A 작업,
>   0019~0036은 그 **이전 기반 설계**(아키텍처·FE·도메인)를 소급 기록한 것 — 실제 결정 시점은 0019~0036이 더 이르다.

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
| [0043](0043-capability-orchestrator-hybrid-merge.md) | **capability 통합 오케스트레이터 + 하이브리드 병합**(1b·2c) | 채택 |
| [0044](0044-recommend-as-agent.md) | **Recommend를 agent로 승격**(자연어 추천 reasoning) | 구현됨 |
| [0045](0045-capability-structure-detail.md) | capability 상세 — **2채널 출력·LLM플래너(검증)·블랙보드** | 채택 |
| [0046](0046-advisory-action-cta-bridge.md) | **조언형/행동형 분리 + CTA 브릿지** — 판매·기사 자동라우팅 금지·수리CTA게이팅·추천위임·복합쿼리 | 채택 |

### Phase A — 스트리밍 / 동시성 실행 (operations.md §6·§9·§14)
| # | 결정 | 상태 |
|---|---|---|
| [0014](0014-phase-a-streaming-first.md) | Phase A 우선순위 = **스트리밍 먼저** | 채택 |
| [0015](0015-streaming-scope-2a.md) | 증분 스트리밍 범위 = **2a만**(2b 후속) | 구현됨 |
| [0016](0016-async-execution-model.md) | 실행 모델 = **async 전환**(순차 유지) | 구현됨 |
| [0017](0017-intra-turn-parallelism-deferred.md) | 후보1 **턴 내 병렬화** | 보류 |
| [0018](0018-stage-timeout-abort-deferred.md) | 후보3 **단계 타임아웃·fine abort** | 보류 |

### 이전 기반 설계 — 아키텍처 / 경계 (architecture.md)
| # | 결정 | 상태 |
|---|---|---|
| [0019](0019-three-tier-bff-split.md) | **3계층 + BFF 독립 서비스** 분리 | 채택 |
| [0020](0020-port-mock-real-boundary.md) | Mock↔실 = **Port/Repository + DI** | 채택 |
| [0021](0021-tokenprovider-three-tier.md) | SmartThings 인증 = **TokenProvider 3계층** | 채택 |
| [0024](0024-routing-be-owned.md) | 요청 라우팅 **BE 소유**, LLM미경유=커밋 한정 | 채택 |
| [0033](0033-actiongate-confirm-real-process-mock.md) | ActionGate = **확인 실제 / 처리 Mock** | 채택 |
| [0034](0034-provider-agnostic-llm.md) | LLM = **provider-agnostic** + 모델 라우팅 | 채택 |
| [0036](0036-proactive-polling-to-events.md) | 선제 = **폴링→이벤트**(동일 정규화) | 채택 |

### 이전 기반 설계 — 프론트엔드 (frontend-architecture.md)
| # | 결정 | 상태 |
|---|---|---|
| [0022](0022-streaming-transport-websocket.md) | 스트리밍 트랜스포트 = **WebSocket**(vs SSE/fetch) | 채택 |
| [0023](0023-fe-state-management.md) | FE 상태관리 = **React Query + Zustand** | 채택 |
| [0027](0027-card-tap-surface.md) | 카드 탭 = **BE 동적 bridge/panel** | 채택 |

### 이전 기반 설계 — 응답 표현 / 도메인 / 데이터 (response-templates·data-model·orchestration)
| # | 결정 | 상태 |
|---|---|---|
| [0025](0025-structured-template-model.md) | 응답 표현 = **구조화 Template**(vs 자유텍스트) | 채택 |
| [0026](0026-message-sections.md) | 복합 응답 = **sections[] + handled** | 채택 |
| [0028](0028-flowstate-active-suspended.md) | FlowState = **active + suspended** | 채택 |
| [0029](0029-engagement-vs-analytics.md) | **Engagement vs Analytics** 도메인 분리 | 채택 |
| [0030](0030-consent-scoped.md) | 동의 = **기능별 scope 세분화** | 채택 |
| [0031](0031-intent-hybrid-classification.md) | 의도 분류 = **LLM 구조화 + 규칙** | 채택 |
| [0032](0032-rag-hybrid-retrieval.md) | RAG = **오류코드 매칭 + 벡터** 하이브리드 | 채택 |
| [0035](0035-data-model-layering.md) | 데이터 모델 = **4계층 분리** | 채택 |

### 분석 / 택소노미 (analytics.md)
| # | 결정 | 상태 |
|---|---|---|
| [0037](0037-attribution-turn-based.md) | 전환 기여 = **turn 기반 + CTA last-touch** | 채택 |
| [0038](0038-analytics-schema-hardening.md) | 분석 스키마 견고성(**네이밍·event_id·version·소유자**) | 채택 |
| [0039](0039-analytics-error-events.md) | **에러/폴백 이벤트** 추가(지연=운영 분리) | 채택 |
| [0041](0041-analytics-session-consistent-sampling.md) | 분석 = **세션 일관 샘플링**(중요이벤트 100%) | 채택 |

### 세션 / 대화 연속성 (operations.md)
| # | 결정 | 상태 |
|---|---|---|
| [0040](0040-conversation-continuity-compaction.md) | 대화 연속성 = **하이브리드 컴팩션 + 영속 메모리** | 채택 |
| [0042](0042-companion-proactive-gated.md) | 컴패니언 선제 재관여 = **엄격 게이트** | 채택 |
