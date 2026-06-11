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

- [ ] 1.1 모노레포 레이아웃 확정: `backend/`(BE 승격)·`bff/`·`frontend/`·`tests/e2e/` _(architecture §9)_
- [ ] 1.2 공유 계약 타입 단일 출처 — `data-model.md` DTO ↔ BE Pydantic ↔ BFF ↔ FE `types/`. 드리프트 방지 규칙 명시 _(api-contract §1)_
- [ ] 1.3 fixtures 보강(저니 커버): `part_hepa.in_stock=false`, 보증 `coverage`, `BookingSlot` 샘플, escalation 플래그 _(J2·J3·J4)_
- [ ] 1.4 CI 골격(워크플로): BE pytest · BFF pytest · FE Jest+스크린샷 · (통합 후) E2E. SessionStart 훅으로 web 세션에서도 테스트/린트 가능 _(cicd)_

---

## 2. BE 도메인 트랙 — `feat/be-domain` (pytest TDD)

> 기존 `backend/app/` 프로토타입(Mock 어댑터·오케스트레이터·OpenAI)을 **FastAPI 도메인 서비스로 승격**한다.

- [ ] 2.1 **Port/Repository 인터페이스** 정의(추상) + Mock 구현 이관 _(data-model §6, R2·R3·R4)_
  - [ ] 2.1.1 `DevicePort`(get_status·detect_anomalies) + Mock + 테스트 _(R2·R5)_
  - [ ] 2.1.2 `CSKnowledgePort`(find_solutions, 하이브리드) + Mock + 테스트 _(R3·R16)_
  - [ ] 2.1.3 `CatalogPort`(match_parts·by-id) + Mock + 테스트 _(R4)_
  - [ ] 2.1.4 `OrderPort`(cart·order, 성공/실패/취소) + Mock + 테스트 _(R4·R21)_
  - [ ] 2.1.5 `HandoffPort`(list_slots·book_slot) + `WarrantyPort`(coverage) + Mock + 테스트 _(R18·R22)_
  - [ ] 2.1.6 `EngagementRepository`(viewed/dismissed/interested) + 테스트 _(R29)_
- [ ] 2.2 **도메인 서비스**(Port 위 비즈니스 로직) — 각 서비스 단위 테스트 _(architecture §4)_
  - [ ] 2.2.1 DeviceService(이상·임계치 판정, design §6.3) _(R2·R5)_
  - [ ] 2.2.2 KnowledgeService·CatalogService·OrderService·NotificationService·PersonalizationService _(R3·R4·R5·R8)_
- [ ] 2.3 **오케스트레이터** — 의도 분류(구조화)·복합 분해·우선순위·tool 조합·세션/FlowState _(R1·R6·R7, design §6.1·6.6)_
  - [ ] 2.3.1 의도 분류 + 복합(`is_compound`) 분해 테스트 — J5 입력 → `[TROUBLESHOOT,ORDER,ORDER]` _(R7·J5)_
  - [ ] 2.3.2 tool 호출 루프(get_device_status·search_solutions·match_parts·order·booking) 테스트 _(R2·R3·R4)_
  - [ ] 2.3.3 섹션 생성(`MessageSection`, handled/unhandled) — J5 부분 처리 테스트 _(R7-3·J5)_
- [ ] 2.4 **응답 → Template 모델** 매핑(`response-templates.md` 14종)을 BE에서 구조화 _(R11)_
- [ ] 2.5 **내부 API** 노출(BFF용, api-contract §2.4): `/internal/turn`(WS 스트림)·`/internal/interaction`·`/internal/surface`·조회/커밋 _(api-contract §2.4)_
  - [ ] 2.5.1 스트림 청크(`delta`·`section`·`flow`·`done`·`error`) WS 테스트 _(R14)_
  - [ ] 2.5.2 커밋 게이트(`/orders` confirmed→`409`) 테스트 _(R17)_
- [ ] 2.6 폴백/부분 degradation — 외부 실패 시 의도별 폴백(전체 중단 금지) 테스트 _(R13)_
- [ ] 2.7 BE PR(draft) + pytest 그린

---

## 3. BFF 트랙 — `feat/bff-gateway` (pytest + 계약 테스트)

> 클라이언트 표면을 소유하고 BE 내부 API로 위임. **비즈니스 로직 없음**(조합·변환·중계·인증).

- [ ] 3.1 BFF 스캐폴드(FastAPI 별도 서비스) + BE 내부 API 클라이언트 _(architecture §9)_
- [ ] 3.2 **WS `/chat`** — 클라이언트 청크 봉투(§2.1) ↔ BE `/internal/turn` 중계 _(R1·R14)_
  - [ ] 3.2.1 `user_message`·`interaction_reply` 수신 → BE 위임 → 청크 중계 테스트 _(R6·R7)_
  - [ ] 3.2.2 스트리밍 중계(섹션 순서 보존) 테스트 _(R7·R14)_
- [ ] 3.3 **결정적 HTTP 엔드포인트**(§2.2): `/devices`·`/cart`·`/orders`·`/bookings`·`/handoff`·`/history` _(R2·R4·R12·R18)_
  - [ ] 3.3.1 `/orders` 커밋 게이트(`confirmed`·`409`) 테스트 _(R17)_
- [ ] 3.4 **`POST /surface`** — 카드 탭 surface(bridge/panel) 중계 _(api-contract §2.3·R9)_
- [ ] 3.5 **aggregation** — `home_summary`(여러 BE 결과 조합) _(R9-2)_
- [ ] 3.6 **인증/세션 게이트** — 토큰 검증·`session_id`·조용한 재인증 _(api-contract §3)_
- [ ] 3.7 **폴백 정규화** — BE/외부 실패 → 클라이언트 폴백 응답(§4) 테스트 _(R13)_
- [ ] 3.8 **계약 테스트** — 클라이언트↔BFF·BFF↔BE 같은 fixture/스키마로 합치 검증 _(api-contract §5)_
- [ ] 3.9 BFF PR(draft) + pytest 그린

---

## 4. FE 트랙 — `feat/fe-app` (Jest+RNTL TDD, **PR마다 스크린샷**)

> Expo RN. One UI 토큰. BFF만 호출. 디자이너 애셋 전 토큰 플레이스홀더.

- [ ] 4.1 Expo 스캐폴드(react-native-web 빌드 가능) + Jest+RNTL + **Playwright 스크린샷 파이프라인** _(frontend-arch §10)_
- [ ] 4.2 **디자인 토큰/테마** — Samsung One UI 스타일(색·타이포·radius·간격), 라이트/다크 _(frontend-arch §6)_
- [ ] 4.3 **트랜스포트 추상화** `ChatTransport` + `WebSocketTransport`(→ BFF `/chat`) + 재연결 _(frontend-arch §5)_
- [ ] 4.4 **상태** — 서버상태(Query)·채팅 reducer(청크/섹션 누적)·UI store _(frontend-arch §2·§11)_
- [ ] 4.5 **템플릿 렌더러** — kind→컴포넌트 레지스트리(14종) + `text` 폴백 + 섹션 스택(복합 R7) _(R11·R7)_
  - [ ] 4.5.1 `device_status`·`guide_steps`·`product_card`·`order_summary`·`confirmation`·`status_tracker` 컴포넌트 + 테스트 _(J1)_
  - [ ] 4.5.2 `home_summary`·`bridge`·`recommendation_list`·`handoff_card`·`booking` 컴포넌트 + 테스트 _(J2·J3·J4)_
- [ ] 4.6 **화면**(wireframes S1~S4): 홈(S1)·CS(S2)·전역 채팅 패널(S3)·브릿지 모달(S4) _(R9, wireframes)_
- [ ] 4.7 **CTA 처리** — 대화형(→`/chat`)·커밋(→엔드포인트+ActionGate) 두 경로 _(architecture §8·R17)_
- [ ] 4.8 멀티모달 입력(R10)·로딩/빈/에러/재시도 4종·타이핑 인디케이터 _(R10·R14)_
- [ ] 4.9 **스크린샷 세트** — J1~J5 핵심 화면 캡처해 각 FE PR 본문에 첨부 _(이번 빌드 요구)_
- [ ] 4.10 FE PR(draft) + Jest 그린 + 스크린샷

---

## 5. E2E 풀테스트 트랙 — `test/e2e-full` (전부 완성 후)

> FE(RN Web) ↔ BFF ↔ BE(실 오케스트레이터·Mock 어댑터)를 함께 띄워 저니별 통과 검증.

- [ ] 5.1 통합 구동 하네스 — BE·BFF·FE(web) 동시 기동(스크립트/compose) _(architecture §9)_
- [ ] 5.2 **J1** 세탁기 5C → 해결 가이드 → 배수필터 주문 → 추적 _(J1)_
- [ ] 5.3 **J2** 정수필터 선제 알림 → 브릿지(S4) → 재주문 → 확인기록 _(J2·R29)_
- [ ] 5.4 **J3** HEPA 품절 → 대체/입고 안내 → 신제품 추천 _(J3·R13·R8)_
- [ ] 5.5 **J4** 셀프 실패 → 트리아지 → 방문 예약(슬롯·확정) _(J4·R18)_
- [ ] 5.6 **J5** 복합 질문 → 분해·우선순위·부분 처리(섹션 묶음, handled/unhandled) _(J5·R7)_
- [ ] 5.7 폴백/단절 경로(외부 실패·재연결) E2E _(R13)_
- [ ] 5.8 E2E PR(draft) + 전 저니 그린 + 최종 스크린샷/리포트

## 진행 메모
<!-- 구현 중 설계와 달라진 점·결정을 기록. 변경 시 design.md/기반 문서도 갱신. -->
- 2026-06-11: BFF를 **별도 서비스로 분리** 결정(이전 "통합 유지" 반전). `docs/architecture.md` §8·§9, `api-contract.md` §1·§2.4 갱신.
