# ADR-0028: FlowState = active + suspended 이원 모델 (흐름 전환·복원)

- **상태**: 채택
- **관련**: `docs/data-model.md` §3, `specs/mvp-concierge/design.md` §2.3, R6

## 배경
가이드 흐름(해결 단계 등) 진행 중 사용자가 자유 채팅으로 이탈했다가 **다시 돌아올** 수 있어야 한다(R6).

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| A | **단일 능동 흐름만** | 단순 | 이탈하면 흐름 소실 |
| B | **흐름 스택**(중첩 push/pop) | 다중 중첩 지원 | MVP엔 과함, UX 모호 |
| **C (선택)** | **active + suspended 이원** | explicit·UX 친화(한 흐름 보류·복원) | 깊은 중첩은 미지원 |

## 결정
**C.** 진행 중 자유 입력 → 현재 흐름을 `suspended_flow`로 보관, 채팅 응답 후 "원래대로 돌아가기" → `active_flow`로 복원. FE reducer도 start/step/suspend/restore로 환원.

## 기각 이유
- A: 이탈 시 흐름이 사라져 복귀 불가.
- B: 다단 스택은 MVP에 불필요하게 복잡하고 UX가 모호.

## 결과/영향
퍼널 분석(`flow_*` 이벤트)·복합 질문 흐름과 정합. 깊은 중첩이 필요해지면 스택으로 확장 검토.
