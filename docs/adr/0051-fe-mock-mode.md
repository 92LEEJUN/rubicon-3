# ADR-0051: FE 단독 동작 Mock 모드

- **상태**: 채택
- **관련**: `specs/fe-mock-mode/`, ADR-0050(신원·커밋 계약), `docs/frontend-architecture.md`, `docs/response-templates.md`

## 배경
FE는 GitHub Pages에 정적 배포되어 BE/BFF 없이도 데모돼야 한다. 기존엔 graceful degradation(apiBase
없으면 fixtures 폴백, WS 실패 시 MockTransport)이 있었으나 **mock이 얇아** 채팅이 입력을 무시하고
고정 응답을 냈고, 커밋이 이력에 반영되지 않았다. "BE 없이 fully 동작"을 위해 mock을 강화한다.

## 결정
- **클라이언트 전용 mock 계층** — 별도 mock 서버(MSW 등) 없이 FE 안에서 처리. 정적 배포에 가장 단순.
- **문서를 명세로 미러** — mock의 라우팅·게이팅·템플릿은 `docs/backend-architecture.md`·
  `docs/frontend-architecture.md`·`docs/response-templates.md`를 따른다(드리프트 시 문서가 기준).
- **채팅 = 시나리오 재생 + 키워드 라우터 폴백** — 정의된 저니는 스크립트로 완성도 있게, 자유 입력은
  capability 미러로 그럴듯하게(둘 다).
- **상태 = localStorage 영속** — 주문·예약·대화가 새로고침·재방문에도 유지. 리셋 수단 제공.
- **신원 = 로그인 사용자 기준** — 게스트/로그인 월 mock은 범위 외(실연동 시 BE가 처리). 단순화.
- **회귀 불변** — `isMock = !apiBase`. apiBase/wsUrl 설정 시 mock 전부 미발동, 기존 실연동·jest 그대로.

## 대안 / 기각
- **MSW(서비스워커 mock 서버)** — 네트워크 레이어를 더 충실히 흉내내나, 정적 배포·번들 복잡도 증가. 클라이언트 fixtures로 충분 → 기각.
- **시나리오 전용(키워드 라우터 없음)** — 자유 입력 대응 불가 → 데모 체감 저하. 폴백 라우터 추가.
- **게스트/로그인 월 mock 포함** — 데모 복잡도 대비 효용 낮음(로그인 상태로 충분) → 범위 외.

## 영향
- 신규 `src/mock/{mode,store,respond,sections}.ts`·`src/fixtures/mockData.ts`·`components/DemoBadge.tsx`.
- `transport/api.ts`·`commit.ts`·`screens/{LiveChat,ChatPanel}.tsx`·`App.tsx`·`main.tsx` 통합(mock 분기).
- BE/BFF 계약·엔드포인트·봉투·CTA kind는 **불변**.

## 후속
- 게스트/로그인 월 mock(원하면) · mock 데이터 추가 시나리오 · analytics 싱크와 무관(emit는 console).
