# ADR-0029: Engagement vs Analytics 도메인 분리

- **상태**: 채택
- **관련**: `docs/architecture.md` §11·§12, `docs/analytics.md`, R28·R29

## 배경
"열람·무시·관심 상태"(R29)와 "사용 측정"(R28)은 둘 다 사용자 행동 기록이지만 용도·데이터 구조가 다르다.

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| A | **통합 이벤트 시스템** 하나로 | 단순·일원화 | 측정용과 동작-변경용이 섞여 책임 모호 |
| **B (선택)** | **Engagement(도메인) vs Analytics(분석) 분리** | 책임 명확, 각자 저장/소비 다름 | 모델 2종 |

## 결정
**B.**
- **Analytics(R28)** — 측정용 **fire-and-forget**(앱 동작 불변), `AnalyticsPort`로 sink. 동의·가명화·비차단.
- **Engagement(R29)** — **앱 동작을 바꾸는 조회 가능한 도메인 상태**(중복 추천 방지·관심 반영), `EngagementRepository`(내부 DB).

## 기각 이유
- A: 측정(부수효과 없음)과 동작 변경(상태 조회 필요)을 한 시스템에 두면 책임·정합성이 흐려진다.

## 결과/영향
Personalization은 Engagement·이력을 **조합**하는 내부 도메인. 분석 emit 실패가 흐름을 막지 않는다(비차단).
