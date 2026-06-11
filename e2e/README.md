# E2E 풀테스트 — FE ↔ BFF ↔ BE

세 서비스를 **실제로 띄워** J1~J5를 검증하는 Playwright E2E(`specs/mvp-concierge/tasks.md` §5).
`playwright.config.ts`의 `webServer`가 기동을 오케스트레이션한다.

```
BE  (FastAPI, :8001)  ← 도메인·오케스트레이터(규칙기반 분류기 — 네트워크/키 불필요)
BFF (FastAPI, :8000)  ← 클라이언트 표면, BE_BASE_URL=http://127.0.0.1:8001
FE  (vite preview, :4173) ← react-native-web 빌드, BFF에 WS/HTTP
```

## 실행
```bash
# 의존성: backend·bff(파이썬), frontend(노드) 설치 + Playwright 크로미움
pip install -r ../backend/requirements.txt -r ../bff/requirements.txt
npm install && npm --prefix ../frontend install
npx playwright install chromium

npm test          # BE·BFF·FE 자동 기동 후 E2E (webServer)
```

## 커버리지 (8 케이스)
| 저니 | 경로 | 검증 |
|------|------|------|
| **J1** | 브라우저(WS) + API | 라이브 채팅 해결 가이드+부품 카드 / 주문 커밋 게이트 409→확정 |
| **J2** | API | 선제 알림(home_summary) + 카드 탭 브릿지(S4) |
| **J3** | 브라우저(WS) + API | HEPA 품절 미처리 + 대체 추천 / 개인화 추천 |
| **J4** | API | 방문 예약 슬롯 조회 → 확정(R18) |
| **J5** | 브라우저(WS) | 복합 — 정수필터 처리 + HEPA 품절 미처리(R7) |
| 인증 | API | 토큰 없으면 401 |

- **브라우저 E2E**(`chat.e2e.ts`) — 라이브 채팅(FE 웹 → BFF WS → BE 오케스트레이터)으로 섹션 스트림 렌더 확인.
- **서비스 E2E**(`journeys-api.e2e.ts`) — 클라이언트 입장에서 BFF HTTP 저니(실 BFF→BE).
- 증빙: `__screenshots__/e2e-j1-live.png`(라이브 스트림 렌더).

> 브라우저 WebSocket은 헤더를 못 보내므로 BFF가 `?token=` 쿼리 토큰도 허용(api-contract §3).
