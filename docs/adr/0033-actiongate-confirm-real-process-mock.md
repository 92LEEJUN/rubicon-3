# ADR-0033: ActionGate = 확인 UX 실제 / 처리 Mock

- **상태**: 채택
- **관련**: `docs/architecture.md` §5·§8, `docs/data-model.md` §6, `docs/response-templates.md` §4, R17

## 배경
되돌릴 수 없는 커밋(결제·주문·예약 확정)은 **확인**을 거쳐야 한다(R17). 그러나 MVP에서 실제 결제/주문을 커밋할 수는 없다.

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| A | **확인·처리 모두 Mock** | 가장 쌈 | 확인 UX(흐름)를 실제로 검증 못 함 |
| **B (선택)** | **확인 UX는 실제, 처리만 Mock** | 게이트 흐름을 진짜로 검증 + 비용 0 | 처리 결과는 시뮬레이션 |
| C | **모두 실제** | 완전 | 비용·리스크(실 결제) |

## 결정
**B.** 사용자는 실제 `confirmation` 템플릿/ActionGate를 보고 확인하지만, 백엔드 커밋은 Mock(`ActionGatePort`/`OrderPort` 시뮬레이션: 성공/실패·취소/환불 R21). 라우팅상 커밋은 LLM 미경유(ADR-0024).

## 기각 이유
- A: 확인 UX(미확인 시 409 ConfirmationRequired 등) 흐름을 실제로 검증하지 못한다.
- C: 실 결제는 비용·리스크가 크다(MVP 부적합).

## 결과/영향
멱등성 키로 중복 커밋 방지(architecture §7). ADR-0020(Port 전략)의 구체 사례.
