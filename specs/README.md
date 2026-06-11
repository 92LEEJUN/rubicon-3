# 스펙 (Specs)

스펙은 **큰 기능 단위**의 틀을 잡는 작업 폴더다(작업 규칙: 루트 `CLAUDE.md`).
**전체 제품·시스템 토대는 기반 문서(`docs/`)** 가 갖고, 각 스펙은 그 토대 위의 **한 기능 줄기**를 다룬다.

## 현재 스펙
| 스펙 | 범위 |
|------|------|
| [`mvp-concierge/`](./mvp-concierge/) | **MVP** — 이상 감지 → 해결 → 부속품 주문 (비전 3→4→5 + 진입 1) |

> ⚠️ 이름이 제품명처럼 컸을 뿐, 내용은 **MVP 한 기능 줄기**다. "전부를 포괄"하는 건 `docs/`(토대)다.

## 로드맵 — 미래 큰 기능은 **형제 스펙**으로
제품 비전(`mvp-concierge/requirements.md` 개요)의 확장은 각각 별도 스펙으로 추가한다:
- `specs/o2o-full/` — 매장 픽업·견적 이어보기·오프라인 통합(현재 인터페이스만 선반영)
- `specs/product-recommendation/` — 선제적 제품 판매 추천(비전 2 본격화)
- `specs/enterprise-multi-account/` — SmartThings Enterprise·다계정/조직
- `specs/voice-accessibility/` — 음성·접근성·다국어

각 스펙은 `requirements.md` / `design.md` / `tasks.md` 3종으로 구성하고, 공유 모델·계약은
`docs/` 기반 문서를 **참조**한다(중복 정의 금지).
