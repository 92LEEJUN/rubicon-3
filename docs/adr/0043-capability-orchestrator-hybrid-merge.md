# ADR-0043: 멀티에이전트 구조 재확정 — capability 기반 통합 오케스트레이터 + 하이브리드 병합

- **상태**: 채택
- **관련**: ADR-0009(슈퍼바이저-워커)·0010(그래뉼래리티 중간)·0011(조건부 리뷰)·0012(단일 패스), `docs/agents.md`, `backend/app/orchestrator/{core,runtime}.py`

## 배경
구현이 진행되며 두 가지가 드러났다:
1. **오케스트레이터가 둘** — `core.Orchestrator`(결정적 섹션 병합)와 `runtime`(멀티에이전트 delta)이 분리돼 같은 "분해→실행→조립"을 중복한다.
2. **도메인 능력 대부분이 결정적(tool)** — 추천(`RecommendationService`)·O2O(`StoreService`/`QuoteService`)·핸드오프·이력은 결정적 서비스다. LLM 추론이 실제로 필요한 건 **진단(상태+RAG 해석)** 과 경계의 **커머스** 정도.

→ "오케스트레이터가 필요한 에이전트·툴을 호출하고 **병합·정리**한다"는 단일 구조로 재정리할 시점.

## 후보안
**갈래 ① 무엇을 agent로 두나(그래뉼래리티)**
| 안 | agent | tool |
|---|---|---|
| 1a 미니멀 | 진단 | 커머스·추천·O2O·핸드오프·이력 |
| **1b (선택)** | **진단·커머스** | 추천·O2O·핸드오프·이력 |
| 1c 도메인 | 진단·커머스·추천·O2O | 핸드오프·이력 |

**갈래 ② 병합·정리(Merge)**
| 안 | 방식 |
|---|---|
| 2a 결정적 | 섹션 우선순위 스택(현 core) — 빠름·근거보존·무환각, 자연어 연결 약 |
| **2c (선택)** | **하이브리드** — 결정적 섹션 + 얇은 LLM 연결문구(인트로/전환) |
| 2b LLM 신서사이저 | 부분결과를 자연어로 매끄럽게 병합 — 흐름 좋으나 홉·지연·환각 위험 |

## 결정
**1b + 2c + 단일 capability 오케스트레이터.**

```
사용자 입력
 → Orchestrator(planner): 의도 분해 + 우선순위(§6.6)
 → capability 선택·실행  [균일 인터페이스 call(input) → result]
      agent: Diagnosis(상태+RAG), Commerce(매칭+주문초안)
      tool : Recommend(RecommendationService)·O2O(Store/Quote)·Handoff(booking)·History
      의존(진단 required_parts → 커머스)은 순차, 독립은 병렬 후보(ADR-0017 보류)
 → Merge(하이브리드 2c): 결정적 섹션 우선순위 스택 + 얇은 LLM 연결문구
 → 조건부 Review(안전 R23·커밋 R17·불확실 R16)
 → done (다단계 스트리밍: 빠른 결정적 섹션 먼저)
```

- **통합** — `core`(결정적 섹션 백본) = capability+merge의 골격, `runtime`의 LLM 워커(진단·커머스)는 그 위의 **agent capability**. `LLM_BACKED`/`MULTIAGENT` 토글은 "어떤 capability가 LLM-backed인가"로 수렴.

## 기각 이유
- **1a**: 커머스(매칭+초안+게이트 판단)는 다단계 추론이라 순수 tool로는 약하다.
- **1c**: 추천·O2O는 내부가 **결정적 서비스**라 agent로 감싸면 LLM 홉·비용만 늘고 전문성 이득이 작다("추천 에이전트" 내부도 결국 결정적 호출).
- **2a**: 복합 응답의 자연어 연결이 약해 컴패니언 톤이 끊긴다.
- **2b**: 부분결과를 통째로 LLM에 재투입 → 지연·환각 위험. 근거(섹션 데이터)는 결정적으로 보존하고 연결문구만 LLM(2c)이 안전.

## 결과/영향
- ADR-0009(슈퍼바이저=planner)·0010(1b)·0011·0012 유지·정합. 본 ADR은 **병합 전략(2c)·오케스트레이터 통합**을 추가.
- 구현: `runtime`/`core`를 capability 레지스트리(agent|tool 균일 인터페이스) + 하이브리드 merge로 수렴(후속 리팩터). 프리페치(첫 섹션 ≤2s)는 결정적 섹션을 먼저 흘리는 2c와 자연 정합.
