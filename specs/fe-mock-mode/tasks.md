# 작업 (Tasks) — FE 단독 동작 Mock 모드

> [design.md](./design.md) 구현 체크리스트. **클라이언트 전용·회귀 불변**(apiBase 설정 시 미발동).
> 검증: `cd frontend && npx jest` + `npx vite build`. 각 항목 끝에 요구사항 번호.

- [x] 1. mock 모드 감지 _(요구사항 2)_
  - [x] 1.1 `src/mock/mode.ts` — `isMock(apiBase)`·`readQueryFlags`(`?mock=1`·`?reset=1`).
  - [x] 1.2 `main.tsx` — `?mock=1`이면 apiBase·wsUrl 비움, `?reset=1` 초기화. `components/DemoBadge.tsx` + `App`에서 mock 시 렌더.

- [x] 2. mock 스토어 _(요구사항 4·5)_
  - [x] 2.1 `src/mock/store.ts` — localStorage(`rubicon.mock.v1`): orders·bookings·candidates·conversation, add/get/reset, 영속 실패 시 메모리 폴백.
  - [x] 2.2 테스트 `tests/mock-store.test.tsx`(4) — add→get·reset·candidates.

- [x] 3. 데이터셋 _(요구사항 6)_
  - [x] 3.1 `src/fixtures/mockData.ts` — DEVICES·PARTS·PRODUCTS·SOLUTIONS·SLOTS·HOME·SEED_ORDERS/BOOKINGS. contract/response-templates 정합.

- [x] 4. mock 채팅 라우터 _(요구사항 3)_
  - [x] 4.1 `src/mock/sections.ts` — capability별 빌더(diagnose 안전·보증 게이팅·order 품절·warranty·booking·explain·clarify·recommend).
  - [x] 4.2 `src/mock/respond.ts` — 시나리오 스크립트 + 키워드 라우터 → §2.1 봉투(우선순위 정렬).
  - [x] 4.3 테스트 `tests/mock-respond.test.tsx`(7) — 봉투 순서·진단·안전 게이팅·품절·F2·explain carry·clarify.

- [x] 5. 통합 _(요구사항 1·4·7)_
  - [x] 5.1 `transport/api.ts` — `!base` 시 orders/bookings = 시드+store 병합.
  - [x] 5.2 `transport/commit.ts` — 정적 폴백이 `recordDemoCommit`로 store.addOrder/addBooking 기록.
  - [x] 5.3 `screens/LiveChat.tsx`(자유입력 respond)·`ChatPanel.tsx`(첫 턴 큐레이트→이후 respond).
  - [x] 5.4 회귀 확인 — apiBase 설정 시 미발동, 기존 jest 통과(81 green).

- [x] 6. 검증 _(요구사항 7)_
  - [x] 6.1 `npx jest` 81 통과 · `DEPLOY_BASE=/rubicon-3/ npx vite build` OK.
  - [ ] 6.2 수동 — 배포(merge) 후 mock에서 홈·채팅(자유입력)·커밋→이력 반영 확인.

## 메모
- 순서 1→2→3→4→5→6. mock/*는 신규 파일이라 충돌 적음.
- 게이팅·라우팅·템플릿은 문서를 미러(ADR-0051). BE 계약·엔드포인트·봉투는 불변.
