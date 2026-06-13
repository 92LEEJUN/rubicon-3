# 보류 항목 (Deferred)

> **사용자 지정 보류** 항목의 단일 인덱스. "지금은 안 한다"를 명시적으로 기록해 누락·재논의를
> 줄인다. 각 항목은 *무엇을·왜 보류·해제 조건·관련 위치*를 담는다. 진실의 출처는 각 항목이 가리키는
> 문서/스펙이며, 본 문서는 **링크 중심 인덱스**다(중복 정의 금지).
>
> 상태 범례: **보류(사용자 지정)** = 결정·구현을 의도적으로 미룸.

## 목록

| # | 항목 | 상태 | 관련 위치 |
|---|---|---|---|
| 1 | part_ids 매핑(explain 제품 주문 `product_ids`↔`part_ids`) | 보류(사용자 지정) | [backend-architecture.md](backend-architecture.md)(`handlers.py: resolve_part_ids`·`handle_explain`)·[operations.md](operations.md)(부품 매칭 `match_parts`) |
| 2 | 실 SSO(외부 IdP 연동 신원) | 보류(사용자 지정) | [`specs/multi-tenant-state/tasks.md`](../specs/multi-tenant-state/tasks.md) §5·ADR-0050 |
| 3 | 레이턴시 pre-paint(선제 렌더/프리페인트) | 보류(사용자 지정) | [frontend-architecture.md](frontend-architecture.md)·[operations.md](operations.md)(스트리밍·지연) |

## 상세

### 1. part_ids 매핑 (explain 제품 주문)
- **무엇** — explain 경로에서 제품 주문 시 `product_ids` ↔ `part_ids` 매핑(주문 대상 식별자 정합).
  현재 `resolve_part_ids`(backend-architecture.md, `handlers.py`)가 부품 식별을 다루나, explain→주문
  교차 매핑은 미완.
- **왜 보류** — 사용자 지정. 본 라운드 범위 외(별도 증분).
- **해제 조건** — explain 기반 주문 플로우를 정식 스펙으로 승격할 때(`specs/<작업>/`로).

### 2. 실 SSO
- **무엇** — 외부 IdP(SSO) 연동 실 신원. 현재는 fixture 사용자 + 게스트 토큰 합성(ADR-0050·0049).
- **왜 보류** — 사용자 지정. 풀 멀티테넌시/실 IdP는 후속(ADR-0049 "풀 멀티테넌시는 후속"과 정합).
- **해제 조건** — 실 인증 연동 착수 시. tasks 위치: `specs/multi-tenant-state/tasks.md`(아래 §5 머지와
  별개로, 실 SSO 신원 발급은 본 항목으로 추적).

### 3. 레이턴시 pre-paint
- **무엇** — 응답 전 선제 렌더/프리페인트로 체감 지연 단축.
- **왜 보류** — 사용자 지정. 현행 스트리밍·점진 렌더(ADR-0004·0015)로 충분, 최적화는 후속.
- **해제 조건** — 지연 관측 결과 필요성이 확인될 때(operations.md 관측 기반).
