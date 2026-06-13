# 설계 (Design) — FE 단독 동작 Mock 모드

> [requirements.md](./requirements.md)를 어떻게 만족시킬지 설계한다. mock은 **클라이언트 전용**이며
> 아키텍처 문서(`docs/backend-architecture.md`·`docs/frontend-architecture.md`)와 `docs/response-templates.md`·
> `frontend/src/types/contract.ts`를 진실의 출처로 미러한다. 결정 기록은 [ADR-0051](../../docs/adr/0051-fe-mock-mode.md).

## 1. 개요
기존 graceful degradation(apiBase 없으면 fixtures 폴백, WS 실패 시 MockTransport 재생)을 **풍부한
데이터 + 결정적 mock 응답 + localStorage 스토어**로 확장한다. 실연동(apiBase/wsUrl 설정) 경로는 불변.

## 2. Mock 모드 감지 (요구사항 2)
- **`isMock = !apiBase`** 를 기준으로 한다(기존 `api.ts`/`commit.ts` 규칙 재사용).
- `main.tsx`에서 `?mock=1`이면 apiBase·wsUrl을 **비우고** 넘겨 mock으로 강제(하위 계층은 `!base`만 보면 됨).
- `App`은 `!apiBase`일 때 **"데모 모드" 배지**(작은 비차단 표시)를 렌더.
- WS는 기존대로 ResilientTransport가 무응답/실패 시 폴백 — 단 폴백 스크립트를 mock 라우터로 교체(§4).

## 3. 데이터 — 풍부한 fixtures (요구사항 6)
- `src/fixtures/mockData.ts`(신규) — 단일 출처 데이터셋:
  - `DEVICES`(세탁기·냉장고·공기청정기·인덕션 등 다중, consumables 포함)
  - `CATALOG`(제품/부품: 정수필터·배수필터·HEPA·큐브 등, 재고/가격)
  - `SOLUTIONS`(증상/에러코드→guide_steps·required_parts·coverage·safety)
  - `ORDERS`·`BOOKINGS` 시드 이력, `RECOMMENDATIONS`, `REENGAGEMENT`, `OPEN_LOOPS`, `CONVERSATION`
- 기존 `journeys.ts`/`scenarios.ts`는 유지하고 mockData가 이를 보강·재사용. 모든 객체는 `contract.ts`/
  `response-templates.md` 스키마와 정합.

## 4. Mock 채팅 라우터 (요구사항 3)
`src/mock/respond.ts` — `respond(text: string, store): Chunk[]` (§2.1 봉투 생성).
- **① 시나리오 매처**: 트리거(정규식/키워드 맵, `scenarios.ts` 기반)에 맞으면 해당 **스크립트 저니** 재생.
- **② 키워드 라우터(폴백)**: BE capability 미러 — 입력에서 의도 키워드 추출 후 section 빌더 호출:
  - `diagnose` → `guide_steps`(+ **안전 게이팅**: 위험 키워드→cta_notice·부품 CTA 숨김; coverage=free→무상 안내)
  - `recommend` → `recommendation_list`(candidates 기록)
  - `order` → `product_card`(재고) / `text`+unhandled(품절)
  - `warranty`→`text`(무상/유상), `booking`→`booking`(슬롯), `explain`→`recommendation_list`(detail), `clarify`→`text`+기기 칩
- section 빌더는 `mockData`를 읽어 일관된 템플릿 생성. 우선순위·복합(fan-out)·게이팅은 문서 규칙을 따른다.
- 봉투: `delta`(짧은 인트로, 선택) → `section*` → `flow` → `done`.

## 5. Mock 스토어 (요구사항 4·5)
`src/mock/store.ts` — localStorage 백엔드 클라이언트 상태.
- 키 네임스페이스 `rubicon.mock.v1`. 스키마: `{ orders[], bookings[], candidates[], conversation[] }`.
- API: `getOrders()/addOrder()`, `getBookings()/addBooking()`, `getHomeExtras()`, `reset()`.
- 영속 실패(프라이빗 모드)면 메모리 폴백(throw 금지).
- **리셋 수단**: 데모 배지에 "초기화" 또는 `?reset=1`.

## 5. 컴포넌트/인터페이스
```
src/mock/mode.ts     isMock(apiBase) · readQueryFlags()
src/mock/store.ts    localStorage 상태(주문·예약·candidates·대화) + reset
src/mock/respond.ts  respond(text, store) → Chunk[]  (시나리오 매처 + 키워드 라우터)
src/mock/sections.ts capability별 section/template 빌더(mockData 사용)
src/fixtures/mockData.ts  데이터셋
components/DemoBadge.tsx   데모 모드 표시 + 초기화
```

## 6. 통합 (요구사항 1·4·7)
- `transport/api.ts`: `!base`일 때 `getOrders`/`getBookings`는 **시드 + store** 병합, `getHome`는 store 반영.
- `transport/commit.ts`: 정적 폴백 분기에서 `store.addOrder/addBooking` 기록 후 ok 반환(409 왕복은 그대로).
- `screens/LiveChat.tsx`·`screens/ChatPanel.tsx`: `ResilientTransport(ws, (m)=>respond(m.text, store))`로 교체(기존 `()=>fallbackChunks()` 대체).
- `App.tsx`: mock일 때 `DemoBadge` 렌더.
- 실연동(apiBase 있음)이면 위 분기 모두 미발동 → 회귀 불변.

## 7. 에러 처리
- mock 계층은 절대 throw하지 않음(빈 화면 금지, R7). localStorage 예외→메모리, 알 수 없는 입력→clarify.

## 8. 테스트 전략 (요구사항 7)
- jest: `respond()` 라우팅(시나리오 매칭·키워드 분기·게이팅·품절 unhandled), `store` 왕복(add→get·reset·영속 mock), `commit` 정적 폴백이 store 기록.
- 회귀: apiBase 설정 경로 기존 테스트 그대로(mock 미발동). `npx jest` + `npx vite build`.
- 수동: GH Pages(mock 기본)에서 화면/채팅/커밋 클릭.

## 9. 이행 순서
1. `mock/store.ts`(+테스트) · 2. `fixtures/mockData.ts` · 3. `mock/sections.ts`+`respond.ts`(+테스트) ·
4. 통합(api·commit·LiveChat·ChatPanel·App 배지) · 5. jest+build 검증.
