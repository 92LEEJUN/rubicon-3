# ADR-0013: 에이전트 프롬프트 단일 출처 = prompts.py

- **상태**: 구현됨
- **관련**: `backend/app/orchestrator/prompts.py`, `docs/agents.md` §10, `docs/llm-policy.md`

## 배경
에이전트별 시스템 프롬프트(Supervisor·Diagnosis·Commerce·Review)를 어디에 두고, 정책 문서(llm-policy)와 어떻게 정합시킬지. 두 곳에 두면 단일 출처 원칙이 깨진다.

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| **A (선택)** | **코드(`prompts.py`)가 프롬프트 문구 단일 출처**, 정책 상위 출처는 `llm-policy.md`, `agents.md`는 매핑만 | 사용 가능(applied)·중복 없음 | 문서에서 전문은 안 보임 |
| B | **문서(`agents.md`)에 프롬프트 전문** | 문서로 일람 | 코드와 동기화 부담·실행 불가 |
| C | **양쪽에 전문** | 어디서든 보임 | **중복 = 단일 출처 위반**·드리프트 |

## 결정
**A.** 공통 `BASE_POLICY`(llm-policy 가드레일·어투, 캐싱 친화 안정 프리픽스) + 역할별 프롬프트. `agents.md §10`은 임무·금지·출력 매핑만 두고 `prompts.py`를 가리킨다.

## 기각 이유
- B: 코드에서 import 불가 → 실제 적용 불가.
- C: 중복은 단일 출처 위반·드리프트.

## 결과/영향
멀티에이전트 런타임 미배선이지만, 구현 시 그대로 사용할 캐논. 정책이 바뀌면 llm-policy → prompts 순으로 갱신.
