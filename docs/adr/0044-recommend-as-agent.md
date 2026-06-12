# ADR-0044: Recommend를 agent로 승격 (자연어 추천 reasoning)

- **상태**: 구현됨
- **관련**: ADR-0010(그래뉼래리티)·0043(capability 통합)·0011(조건부 리뷰), `backend/app/orchestrator/runtime.py`·`prompts.py`·`tools.py`

## 배경
ADR-0043은 그래뉼래리티 1b(Recommend=tool)로 뒀다. 그러나 **자연어 제품 추천**은 결정적 랭킹만으론 부족하다:
- *"겨울에 건조한데 50만원으로 뭐 사면 좋아?"* → **need 추론**(건조→가습/공기청정)·**예산/제약 해석**·**후보 비교**·**"왜 추천?" 설명**이 필요.
- 이 부분은 본질적으로 **비결정적(LLM 추론)** 이다.

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| A | **tool 파라미터화** — LLM이 slot(need·category·budget) 추출 → 결정적 `recommend(params)` 호출 | 1b 유지·결정성↑ | 단발 tool이라 **비교·설명 reasoning 약함** |
| **B (선택)** | **Recommend를 agent로 승격** — LLM 추론 루프가 recommend tool을 호출·비교·설명 | 자연어 need·비교·설명 강함, grounding 유지 | LLM 홉·비용↑ |

## 결정
**B.** Recommend = 3번째 agent(진단·커머스·**추천**). 내부 grounding은 **tool**:
- `recommend(category, budget)`(카탈로그 후보·가격·사양) + `match_parts`.
- 에이전트(LLM)는 자연어 need 이해 → tool로 후보 조회 → **후보 데이터로만** 비교·근거 설명(가격/사양 날조 금지, llm-policy §4).

## 기각 이유
- A: slot 추출은 되지만, "이 둘 중 뭐가 나아?"·"왜?" 같은 **다단계 비교·설명**을 단발 tool로는 못 한다. 추천은 진단처럼 **추론 루프**가 어울린다.

## 결과/영향
- **그래뉼래리티 수정**: ADR-0010/0043의 1b → **"1b + Recommend"**(≈1c 일부). 진단·커머스·추천 = agent.
- **비결정성의 위치** = 이해(오케스트레이터)·추론(Recommend agent)·설명(하이브리드 병합). **선택의 grounding은 결정적 tool**(환각 방지).
- 결정적 경로(`handle_recommend`, LLM_BACKED off)는 `RecommendationService` 그대로 유지(회귀 0).
- 구현: `tools.py` `recommend` tool, `prompts.RECOMMEND_PROMPT`, `runtime` recommend 스테이지(`_RECO_TOOLS`). 백엔드 144 통과.
