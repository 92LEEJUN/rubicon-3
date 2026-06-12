# ADR-0037: 전환 기여 = turn 기반 correlation_id + CTA last-touch

- **상태**: 채택
- **관련**: `docs/analytics.md` §5, `docs/architecture.md` §11, R28

## 배경
이 제품은 **버튼 없이 대화로 주문**하는 경로가 핵심이다(자유 텍스트 진단 → "주문해줘"). 그런데 기존 택소노미는 `correlation_id`를 **`cta_click`에서만** 발급해 last-touch 기여를 했다 → CTA 없는 대화형 전환은 **기여가 0**으로 샜다.

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| **A (선택)** | **turn/flow 시작 시 `correlation_id` 발급** + CTA last-touch | 대화 자체를 1급 기여 채널로, 대화형 전환 측정 | 발급 시점 관리 |
| B | **현행 CTA last-touch만** | 단순 | 대화형(organic) 전환 누락 |
| C | **multi-touch** | 정밀 | MVP 과함·분석 복잡 |

## 결정
**A.** `correlation_id`를 turn 시작 시 발급해 `message_sent` → `order_confirmed`까지 전파. CTA가 있으면 마지막 `cta_clicked`로, 없으면 **대화(organic chat)** 채널로 기여(last-touch).

## 기각 이유
- B: 컨시어지의 핵심인 대화형 전환이 측정 불가(기여 0).
- C: 다중 접점 가중은 MVP에 과하고 분석 복잡도↑.

## 결과/영향
대화 채널 분모는 `chat_opened`/`message_sent`, CTA 분모는 `cta_shown`. 스키마 보강은 ADR-0038.
