# 작업 (Tasks) — MVP 컨시어지 구현 (FE / BFF / BE + E2E)

> `requirements.md`(R1~R29)·`design.md`·`journeys.md`(J1~J5)를 실제 구현으로 나눈 체크리스트.
> **3계층 분리**(FE · BFF · BE 도메인, `docs/architecture.md` §9)를 **독립 브랜치·TDD**로 개발하고,
> 전부 완성 후 **E2E 풀테스트**한다. 각 항목 끝에 관련 요구사항/저니를 표기한다.

## 0. 전제 / 결정 (이번 빌드)

- **서비스 경계** — FE(Expo RN) → BFF(FastAPI, 클라이언트 표면) → BE(FastAPI, 오케스트레이터+도메인+Port). `docs/architecture.md` §8·§9.
- **저니 범위** — J1~J5 전부(`journeys.md`).
- **FE 스택/스크린샷** — Expo + react-native-web, **PR마다 Playwright 헤드리스 스크린샷** 첨부.
- **FE 비주얼** — Samsung One UI 스타일 디자인 토큰(애셋 도착 시 값만 교체).
- **TDD** — 각 트랙은 테스트를 먼저/동반 작성한다. BE/BFF=pytest, FE=Jest+RNTL, E2E=Playwright.
- **데이터** — `specs/mvp-concierge/fixtures/`를 Mock 어댑터·계약 Stub이 그대로 반환(`api-contract.md` §5).

### 브랜치 맵
| 트랙 | 브랜치 | 산출물 |
|------|--------|--------|
| 문서 | `doc/architecture-bff-split` | 아키텍처 분리 반영 + 본 tasks |
| BE 도메인 | `feat/be-domain` | FastAPI 승격·도메인·Port·오케스트레이터·내부 API + pytest |
| BFF | `feat/bff-gateway` | WS `/chat`·HTTP·aggregation·Template·인증·중계 + pytest/계약테스트 |
| FE | `feat/fe-app` | Expo RN·One UI 토큰·렌더러·트랜스포트·화면 + Jest/RNTL + 스크린샷 |
| E2E | `test/e2e-full` | FE↔BFF↔BE 통합 Playwright E2E (J1~J5) |

---

## 1. 공통 기반 (먼저)

- [x] 1.1 모노레포 레이아웃 확정: `backend/`·`bff/`·`frontend/`·`e2e/` _(architecture §9)_
- [x] 1.2 공유 계약 타입 단일 출처 — `data-model.md` DTO ↔ BE Pydantic ↔ FE `types/contract`. 드리프트 방지 _(api-contract §1)_
- [x] 1.3 fixtures 커버: `part_hepa.in_stock=false`·보증 `coverage`·`BookingSlot`(Mock 어댑터 생성) _(J2·J3·J4)_
- [~] 1.4 워크플로: **GitHub Pages 배포** 추가(`.github/workflows/deploy-pages.yml`)+`vercel.json`. 테스트 CI(BE/BFF/FE/E2E)는 후속 _(cicd)_

---

## 2. BE 도메인 트랙 — `feat/be-domain` (pytest TDD)

> 기존 `backend/app/` 프로토타입(Mock 어댑터·오케스트레이터·OpenAI)을 **FastAPI 도메인 서비스로 승격**한다.

- [x] 2.1 **Port/Repository 인터페이스** 정의(Protocol) + Mock 구현 _(data-model §6, R2·R3·R4)_
  - [x] 2.1.1 `DevicePort`(get_status) + Mock + 테스트 _(R2·R5)_
  - [x] 2.1.2 `CSKnowledgePort`(find_solutions, 하이브리드) + Mock + 테스트 _(R3·R16)_
  - [x] 2.1.3 `CatalogPort`(match_parts·recommend) + Mock + 테스트 _(R4)_
  - [x] 2.1.4 `OrderPort`(order, 성공/실패/취소) + Mock + 테스트 _(R4·R21)_
  - [x] 2.1.5 `HandoffPort`(list_slots·book_slot) + `WarrantyPort`(coverage) + Mock + 테스트 _(R18·R22)_
  - [x] 2.1.6 `EngagementRepository`(viewed/dismissed/interested) + 테스트 _(R29)_
- [x] 2.2 **도메인 서비스**(Port 위 비즈니스 로직) — 각 서비스 단위 테스트 _(architecture §4)_
  - [x] 2.2.1 DeviceService(이상·임계치 판정, design §6.3) _(R2·R5)_
  - [x] 2.2.2 Knowledge·Catalog·Order·Handoff·Notification 서비스 _(R3·R4·R5·R8)_
- [x] 2.3 **오케스트레이터** — 의도 분류(주입형)·복합 분해·우선순위·세션/FlowState _(R1·R6·R7, design §6.1·6.6)_
  - [x] 2.3.1 의도 분류 + 복합(`is_compound`) 분해 테스트 — J5 → `[troubleshoot,order]` _(R7·J5)_
  - [x] 2.3.2 핸들러(device_status·troubleshoot·order·recommend) + LLM tool-loop(legacy CLI) _(R2·R3·R4)_
  - [x] 2.3.3 섹션 생성(`MessageSection`, handled/unhandled) — J5 부분 처리 테스트 _(R7-3·J5)_
- [x] 2.4 **응답 → Template 모델** 매핑(BE에서 kind 구조화) _(R11)_
- [x] 2.5 **내부 API**(BFF용, api-contract §2.4): `/internal/turn`(WS+NDJSON)·`/internal/surface`·조회/커밋 _(api-contract §2.4)_
  - [x] 2.5.1 스트림 청크(`section`·`flow`·`done`·`error`) WS/HTTP 테스트 _(R14)_
  - [x] 2.5.2 커밋 게이트(`/orders` confirmed→`409`) 테스트 _(R17)_
- [x] 2.6 폴백/부분 degradation — 오케스트레이터 예외 → `error` 청크 정규화 테스트 _(R13)_
- [x] 2.7 BE PR(#29) + pytest 52 그린

---

## 3. BFF 트랙 — `feat/bff-gateway` (pytest + 계약 테스트)

> 클라이언트 표면을 소유하고 BE 내부 API로 위임. **비즈니스 로직 없음**(조합·변환·중계·인증).

- [x] 3.1 BFF 스캐폴드(FastAPI 별도 서비스) + BE 내부 API 클라이언트(httpx.AsyncClient) _(architecture §9)_
- [x] 3.2 **WS `/chat`** — 클라이언트 청크 봉투(§2.1) ↔ BE `/internal/turn` 중계 _(R1·R14)_
  - [x] 3.2.1 `user_message`·`interaction_reply` 수신 → BE 위임 → 청크 중계 테스트 _(R6·R7)_
  - [x] 3.2.2 스트리밍 중계(섹션 순서 보존) 테스트 _(R7·R14)_
- [x] 3.3 **결정적 HTTP 엔드포인트**(§2.2): `/devices`·`/home`·`/orders`·`/bookings`·`/catalog/recommend` _(R2·R4·R18)_
  - [x] 3.3.1 `/orders` 커밋 게이트(`confirmed`·`409`) 테스트 _(R17)_
- [x] 3.4 **`POST /surface`** — 카드 탭 surface(bridge/panel) 중계 _(api-contract §2.3·R9)_
- [x] 3.5 **aggregation** — `home_summary` 중계 _(R9-2)_
- [x] 3.6 **인증/세션 게이트** — 토큰 검증(헤더+WS 쿼리), 없으면 401 _(api-contract §3)_
- [x] 3.7 **폴백 정규화** — BE/외부 실패 → 클라이언트 폴백 응답(§4) 테스트 _(R13)_
- [x] 3.8 **계약 테스트** — 클라이언트↔BFF↔BE(ASGITransport 인프로세스) 합치 검증 _(api-contract §5)_
- [x] 3.9 BFF PR(#30) + pytest 16 그린

---

## 4. FE 트랙 — `feat/fe-app` (Jest+RNTL TDD, **PR마다 스크린샷**)

> Expo RN. One UI 토큰. BFF만 호출. 디자이너 애셋 전 토큰 플레이스홀더.

- [x] 4.1 스캐폴드(Vite + react-native-web) + Jest+Testing Library + **Playwright 스크린샷 파이프라인** _(frontend-arch §10)_
- [x] 4.2 **디자인 토큰** — Samsung One UI 스타일(색·타이포·radius·간격) _(frontend-arch §6)_
- [x] 4.3 **트랜스포트 추상화** `ChatTransport` + `WebSocketTransport`(→ BFF `/chat`)·`MockTransport` _(frontend-arch §5)_
- [x] 4.4 **상태** — 채팅 reducer(청크/섹션 누적·폴백) + `useChat` 훅 _(frontend-arch §2·§11)_
- [x] 4.5 **템플릿 렌더러** — kind→컴포넌트 레지스트리(12종) + `text` 폴백 + 섹션 스택(복합 R7) _(R11·R7)_
  - [x] 4.5.1 `device_status`·`guide_steps`·`product_card`·`order_summary`·`confirmation`·`status_tracker` + 테스트 _(J1)_
  - [x] 4.5.2 `home_summary`·`bridge`·`recommendation_list`·`handoff_card`·`booking` + 테스트 _(J2·J3·J4)_
- [~] 4.6 **화면**: 홈(S1)·전역 채팅(S3)·라이브(WS)·템플릿 갤러리·브릿지 템플릿(S4). CS 페이지(S2)는 후속 _(R9, wireframes)_
- [x] 4.7 **CTA 처리** — 대화형(action=chat)·커밋(action=commit) 두 경로 모델링 _(architecture §8·R17)_
- [ ] 4.8 멀티모달 입력(R10)·로딩/에러/재시도 — 후속 _(R10·R14)_
- [x] 4.9 **스크린샷** — home·chat-j1·gallery·e2e-live 캡처해 PR 첨부 _(이번 빌드 요구)_
- [x] 4.10 FE PR(#31) + Jest 20 그린 + 스크린샷

---

## 5. E2E 풀테스트 트랙 — `test/e2e-full` (전부 완성 후)

> FE(RN Web) ↔ BFF ↔ BE(실 오케스트레이터·Mock 어댑터)를 함께 띄워 저니별 통과 검증.

- [x] 5.1 통합 구동 하네스 — Playwright `webServer`로 BE·BFF·FE(web) 동시 기동 _(architecture §9)_
- [x] 5.2 **J1** 세탁기 5C → 해결 가이드 → 배수필터 주문(브라우저 WS + 커밋 게이트 API) _(J1)_
- [x] 5.3 **J2** 선제 알림(home_summary) → 브릿지(surface) _(J2)_
- [x] 5.4 **J3** HEPA 품절 미처리 → 대체 추천 _(J3·R13·R8)_
- [x] 5.5 **J4** 방문 예약(슬롯 조회·확정) _(J4·R18)_
- [x] 5.6 **J5** 복합 질문 → 분해·부분 처리(섹션 묶음, handled/unhandled) _(J5·R7)_
- [x] 5.7 인증 게이트(401)·BE 장애 폴백 _(R13)_
- [x] 5.8 E2E PR(#32) + 8 케이스 그린 + 라이브 스크린샷

## 진행 메모
<!-- 구현 중 설계와 달라진 점·결정을 기록. 변경 시 design.md/기반 문서도 갱신. -->
- 2026-06-11: BFF를 **별도 서비스로 분리** 결정(이전 "통합 유지" 반전). `docs/architecture.md` §8·§9, `api-contract.md` §1·§2.4 갱신.
- 2026-06-11: FE 테스트는 **Testing Library + react-native-web**로 적응(웹 우선, 스크린샷/E2E 타깃 일관) — tasks의 "RNTL" 대체.
- 2026-06-11: BFF↔BE turn 채널은 **HTTP NDJSON 스트림**(+WS 병행)으로 구현 — 브라우저/인프로세스 테스트 용이.
- 2026-06-11: 배포 = **GitHub Pages**(Actions) + `vercel.json`. 정적 데모(홈·갤러리·Mock 채팅)는 백엔드 없이 동작, 라이브는 `?screen=live&ws=<BFF>`.
- 후속: 멀티모달(4.8)·CS 페이지 S2(4.6)·테스트 CI(1.4)·스택 PR→main 정리.
