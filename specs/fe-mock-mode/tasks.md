# 작업 (Tasks) — FE 단독 동작 Mock 모드

> [design.md](./design.md) 구현 체크리스트. **클라이언트 전용·회귀 불변**(apiBase 설정 시 미발동).
> 검증: `cd frontend && npx jest` + `npx vite build`. 각 항목 끝에 요구사항 번호.

- [ ] 1. mock 모드 감지 _(요구사항 2)_
  - [ ] 1.1 `src/mock/mode.ts` — `isMock(apiBase)`·쿼리 플래그(`?mock=1`·`?reset=1`).
  - [ ] 1.2 `main.tsx` — `?mock=1`이면 apiBase·wsUrl 비움. `components/DemoBadge.tsx` + `App`에서 mock 시 렌더.

- [ ] 2. mock 스토어 _(요구사항 4·5)_
  - [ ] 2.1 `src/mock/store.ts` — localStorage(`rubicon.mock.v1`): orders·bookings·candidates·conversation, add/get/reset, 영속 실패 시 메모리 폴백.
  - [ ] 2.2 테스트 `tests/mock-store.test.tsx` — add→get·reset·영속 mock.

- [ ] 3. 데이터셋 _(요구사항 6)_
  - [ ] 3.1 `src/fixtures/mockData.ts` — DEVICES·CATALOG·SOLUTIONS·ORDERS·BOOKINGS·RECOMMENDATIONS·REENGAGEMENT·OPEN_LOOPS·CONVERSATION. contract/response-templates 정합.

- [ ] 4. mock 채팅 라우터 _(요구사항 3)_
  - [ ] 4.1 `src/mock/sections.ts` — capability별 section/template 빌더(diagnose 게이팅·order 품절·warranty·booking·explain·clarify·recommend).
  - [ ] 4.2 `src/mock/respond.ts` — 시나리오 매처 + 키워드 라우터 → §2.1 봉투 청크.
  - [ ] 4.3 테스트 `tests/mock-respond.test.tsx` — 시나리오 매칭·키워드 분기·안전 게이팅·품절 unhandled·봉투 순서.

- [ ] 5. 통합 _(요구사항 1·4·7)_
  - [ ] 5.1 `transport/api.ts` — `!base` 시 orders/bookings = 시드+store, home 반영.
  - [ ] 5.2 `transport/commit.ts` — 정적 폴백이 store.addOrder/addBooking 기록.
  - [ ] 5.3 `screens/LiveChat.tsx`·`screens/ChatPanel.tsx` — 폴백 스크립트를 `respond(m.text, store)`로 교체.
  - [ ] 5.4 회귀 확인 — apiBase 설정 시 미발동, 기존 jest 통과.

- [ ] 6. 검증 _(요구사항 7)_
  - [ ] 6.1 `npx jest`(신규+기존) · `npx vite build`(GH Pages base).
  - [ ] 6.2 수동 — mock 배포에서 홈·채팅(자유입력)·주문/예약 커밋→이력 반영 확인.

## 메모
- 순서 1→2→3→4→5→6. mock/*는 신규 파일이라 충돌 적음.
- 게이팅·라우팅·템플릿은 문서를 미러(ADR-0051). BE 계약·엔드포인트·봉투는 불변.
