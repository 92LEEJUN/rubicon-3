# ADR-0038: 분석 이벤트 스키마 견고성 (네이밍·event_id·schema_version·단일 소유자)

- **상태**: 채택
- **관련**: `docs/analytics.md` §2·§4, `docs/data-model.md`(`AnalyticsEvent`)

## 배경
택소노미에 네 가지 구멍이 있었다: ① 네이밍 혼재(`order_confirmed` vs `add_to_cart`) ② 배치 재전송 시 **중복 집계**(멱등 키 부재) ③ props 진화 추적 불가 ④ `flow_*` owner "BE/FE" 모호 → **이중 카운트** 위험.

## 후보안
각 항목: **보강 채택** vs **현행 유지**.

## 결정 (4종 모두 채택)
1. **네이밍 = `object_action`(과거형)** 통일 — `add_to_cart`(분석) → `cart_item_added`, `cta_click` → `cta_clicked`, `flow_start/step/complete/abandon` → `flow_started/advanced/completed/abandoned` 등. (CTA 액션 `add_to_cart`와 분석 이벤트를 이름으로 구분하는 부수 효과.)
2. **`event_id`(UUID)** — ingestion에서 멱등 dedup(배치 재시도 중복 제거).
3. **`schema_version`** — props 변경 추적(additive-only와 병행).
4. **이벤트별 단일 소유자** — `flow_*` owner=**BE**(FlowState 진실의 출처). FE는 추적하되 emit 안 함.

## 기각 이유
- 현행 유지: 데이터가 쌓이기 시작하면 중복·이중카운트·네이밍 드리프트가 분석을 오염시킨다. **런칭 전이라 rename 비용이 0**(라이브 후엔 additive-only로 금지).

## 결과/영향
`AnalyticsEvent` 타입에 `event_id`·`schema_version` 추가(data-model). 네이밍 규칙은 analytics §2에 명문화.
