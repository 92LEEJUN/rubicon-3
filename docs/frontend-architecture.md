# 프론트엔드 아키텍처 (Frontend Architecture)

> **기반 문서 (공유).** React Native 앱의 내부 구조·결정을 정의한다.
> BE 계약은 `docs/architecture.md`(요청 라우팅) 와 `docs/response-templates.md`(응답 템플릿) 를 따른다.
> FE 구조·라이브러리·트랜스포트 결정이 바뀌면 **이 문서를 갱신**한다.
>
> 각 결정은 **우선안 + 후보안 + 선택/미선택 이유**를 남겨, 추후 교체가 필요할 때 바로 바꿀 수 있게 한다.

## 1. 개요 / 범위

- **React Native 앱.** 홈 · CS 페이지 · 어디서든 진입하는 전역 채팅 패널(R9).
- 멀티모달 입출력(R10), 응답 템플릿·CTA 렌더(R11), 스트리밍 응답(R14).
- 디자이너 애셋 미수령 → **토큰/플레이스홀더**로 진행, 애셋 도착 시 값만 교체.
- 원칙: FE는 **BE 계약(템플릿 모델)을 렌더**할 뿐, "LLM이냐 API냐" 라우팅은 판단하지 않는다(`architecture.md` §8).

## 2. 상태 관리

**요구:** 전역 채팅 패널 상태가 **화면 이동에도 유지**(R9), 스트리밍 부분 메시지 누적, 이력(R12).

- **서버 상태**(대화·기기·주문 등) 와 **클라이언트 UI 상태**(패널 열림·입력·임시 선택)를 분리한다.
- **우선안** — 서버 상태: 데이터 패칭/캐싱 라이브러리(React Query 계열) · 전역 UI/세션 상태: 경량 store(Zustand 계열).
- **후보안** — Redux Toolkit(대규모·미들웨어 풍부하나 보일러플레이트↑), Context만 사용(소규모엔 충분하나 리렌더·확장 약함).
- **선택 이유** — 스트리밍·캐싱·무효화는 서버상태 라이브러리가 잘 풀고, 전역 UI는 가벼운 store가 적합. 보일러플레이트 최소.
- 채팅 세션은 **단일 소스**로 두고 스트리밍 청크를 누적, `FlowState`(진행 흐름)를 FE에도 반영.

## 3. 네비게이션

- **React Navigation** 기반.
- **전역 채팅 패널** — 바텀시트/모달 오버레이로 **어느 화면에서나** 호출(R9-1). 화면 스택과 독립.
- **화면 맥락 전달**(R9-4) — 패널을 연 화면 정보를 주입 → `ChatRequest.screen_context`.
- **딥링크** — 푸시 알림(R20) → 특정 화면/대화, CTA → 제품·장바구니·예약 화면 이동.
- **카드 탭 → 브릿지 vs 패널 (S4 vs S3)** — 카드 탭은 BE에 요청을 보내고, 응답의 **surface**에 따라
  렌더한다: `bridge`(경량 모달 S4) 또는 대화 패널(S3). **분기 판단은 BE(동적)**, FE는 surface만 보고 띄운다
  (`response-templates.md` §9 · `wireframes.md` S4). 브릿지의 에스컬레이션은 S3를 화면 맥락과 함께 연다.

## 4. 템플릿 렌더러

- **kind → 컴포넌트 레지스트리(맵)** 로 렌더. 모르는 kind·스키마 불일치 → `text` 폴백(`response-templates.md` §7).
- `Message` = `text` + `template` + `ctas` + `media` 합성 렌더.
- **CTA 핸들러 — 두 경로**(`architecture.md` §8): **대화형 CTA**(제안 칩·`choices` 등 회신·설명 요청)는
  `/chat`으로 전송, **되돌릴 수 없는 커밋**(결제·주문·예약 확정)은 결정적 엔드포인트 + ActionGate(R17).
- **인터랙션 회신**(`choices`·`confirmation`·`booking`)은 선택값을 `/chat` 후속 요청으로 전송(`response-templates.md` §8).
- 템플릿 추가 시: 레지스트리에 컴포넌트 등록 + 폴백 유지.

## 5. 스트리밍 트랜스포트 (상세 결정)

**요구:** `/chat` 점진적 응답(R14), 인터랙션 회신(R6·R7), 향후 실시간(상담원 연결 R18·라이브 알림 R20).

> **우선안: WebSocket** / 후보안: SSE, chunked fetch(HTTP 스트리밍).
> 단, 아래 **트랜스포트 추상화**로 감싸 언제든 교체 가능하게 둔다.

### 후보 비교
| 안 | 장점 | 단점 |
|----|------|------|
| **WebSocket (우선)** | 양방향(회신·중단·타이핑에 자연스러움), RN **내장 지원** 성숙, 연결 상태 관리 명확, 실시간 확장(R18·R20) 용이 | 재연결·하트비트·백그라운드 전환 관리 필요, 서버 WS 핸들링(FastAPI 지원), 스케일 시 sticky 세션 고려 |
| SSE | 단방향 스트리밍 단순, HTTP 기반(프록시 친화), 자동 재연결 | **RN에서 `EventSource` 기본 미지원**(폴리필 필요), 단방향 → 회신은 별도 POST(채널 이원화), 헤더 인증 번거로움 |
| chunked fetch | 추가 프로토콜 불필요 | **RN `fetch`의 ReadableStream 스트리밍이 불안정**(엔진/버전 의존), 구현·디버깅 까다로움 |

### 선택 / 미선택 이유
- **선택(WebSocket):** ① 인터랙션 **양방향성**이 우리 모델(회신·흐름 전환)과 맞고, ② RN **내장 WebSocket**으로 의존성 적고, ③ 상담원 실시간 연결(R18)·라이브 알림(R20)으로 **자연 확장**된다.
- **SSE 미선택:** RN 기본 미지원 + 단방향이라 회신 채널을 따로 둬야 해 **구조가 이원화**된다. (단방향 스트리밍만 필요해지면 재고 가능)
- **chunked fetch 미선택:** RN의 스트리밍 `fetch` 지원이 **불안정**해 리스크가 크다.

### 트랜스포트 추상화 (교체 가능하게)
```text
ChatTransport (interface)
  connect()             # 세션 시작
  send(message)         # 사용자 입력/인터랙션 회신 전송
  onChunk(handler)      # 스트리밍 청크 수신 (ChatResponseChunk)
  onState(handler)      # 연결/재연결/오류 상태
  close()

WebSocketTransport   # 우선 구현
SseTransport         # 후보 (필요 시)
HttpStreamTransport  # 후보 (필요 시)
```
- UI·상태관리는 `ChatTransport` 인터페이스에만 의존한다. 트랜스포트 교체 시 **이 구현만 바꾸면** 된다.
- **검증 스파이크(우선)** — WS로 `/chat` 스트리밍 + 회신 왕복 PoC, **재연결·백그라운드 전환·네트워크 단절** 동작 확인. 결과로 본 절을 보정.

## 6. 디자인 시스템 / 토큰

- **토큰**(색·간격·타이포·radius) 과 **테마**(라이트/다크)를 정의하고, 컴포넌트는 토큰만 참조(하드코딩 금지).
- 디자이너 애셋 도착 시 **토큰 값 교체**로 반영. 그 전까지는 중립 플레이스홀더 스타일.

## 7. 멀티모달 입력 (R10)

- 카메라/갤러리/영상 피커, **권한 요청·거부 처리**, 업로드 진행·압축, 크기/형식 제한(`data-model.md` `Media`).
- 입력 실패 시 폴백(R13).

## 8. UX 상태 / 성능

- 모든 화면·템플릿에 **로딩(스켈레톤)·빈 상태·에러·재시도** 4종. 스트리밍 **타이핑 인디케이터**(R14).
- 긴 대화 **리스트 가상화**(FlatList), 스트리밍 중 **리렌더 최소화**, 이미지 메모리/캐싱.

## 9. 네트워크 / 오프라인 / 보안

- 재시도·타임아웃·오프라인 안내(FE 측 R13 대응).
- 인증 토큰은 **보안 저장소(Keychain/Keystore)** 에. 앱 번들에 시크릿 금지(R15 실 전환 시).

## 10. 프로젝트 / 모듈 레이아웃 (제안)

(BE 레이아웃은 `data-model.md` §8.)

```
frontend/
├─ src/
│  ├─ app/                     # 진입점·루트 네비게이션
│  ├─ screens/                 # 화면 (wireframes 대응)
│  │  ├─ Home/                 # S1
│  │  ├─ Support/              # S2 (CS)
│  │  └─ ChatPanel/            # S3 (전역 오버레이)
│  ├─ templates/               # kind → 컴포넌트 레지스트리 (§4, 13종)
│  ├─ hooks/                   # 커스텀 훅 (§11)
│  ├─ transport/               # ChatTransport 추상화 + WebSocket 구현 (§5)
│  ├─ state/                   # 서버상태(쿼리)·UI/세션 store + reducer (§2·§11)
│  ├─ api/                     # 결정적 엔드포인트 클라이언트 (api-contract §2.2)
│  ├─ navigation/              # React Navigation·딥링크 (§3)
│  ├─ design/                  # 토큰·테마 (§6)
│  ├─ media/                   # 멀티모달 입력·렌더 (§7)
│  └─ types/                   # data-model DTO 대응 타입(공유 계약)
└─ __tests__/                  # 컴포넌트·계약(stub) 테스트
```

- `templates/`·`api/`·`types/`는 **계약(response-templates·api-contract·data-model)** 에 1:1 대응 — 변경 시 함께 갱신.
- `transport/`는 §5 추상화 뒤에 구현을 둬 트랜스포트 교체 가능.

## 11. 상태 환원(reducer) · 커스텀 훅

§2(서버/UI 상태 분리)를 구현 단위로 구체화. **상태를 어디에 둘지** + **이벤트→상태 환원 후보** + **훅 카탈로그**.

### 상태 분류 — 무엇을 어디에
| 상태 도메인 | 관리 방식 | 이유 |
|------------|-----------|------|
| 서버 데이터(기기·주문·이력·`home_summary`) | **Query 캐시**(React Query 계열) | 패칭·캐시·무효화·재시도 |
| 채팅 메시지·스트리밍·`FlowState` | **reducer**(이벤트→상태) | WS 청크 누적은 이벤트 환원에 적합 |
| WS 연결 상태 | **reducer(상태머신)** | 연결/재연결/오프라인 전이 |
| 장바구니(주문 draft) | **reducer** | add/remove/clear 전이 |
| 전역 UI/세션(패널·브릿지·화면맥락) | **경량 store**(Zustand 계열) | 화면 간 공유·단순 |
| 동의·분석 opt-in | store + 보안 저장 | 수집 게이트(R19) |

### 환원(reducer) 후보 — 이벤트 → 상태
1. **채팅 스트림 환원** — WS 청크(`delta`/`template`/`flow`/`done`/`error`)를 메시지 리스트 + 스트리밍 상태로 누적(api-contract §2.1).
2. **연결 상태머신** — connect/open/chunk/drop/background/offline → status(diagrams.md WebSocket 상태).
3. **FlowState** — start/step/suspend/restore → `active_flow`/`suspended_flow`(R6).
4. **장바구니** — add/remove/clear → `Order(DRAFT)`.
5. **브릿지 surface** — open/escalate/dismiss → 모달/패널 상태(작게).

> 위 5종은 **이벤트 시퀀스를 상태로 접는(reduce)** 성격이라 reducer가 자연스럽다. 나머지(서버 데이터)는 Query 캐시.

### 커스텀 훅 카탈로그
| 훅 | 책임 | 의존 계약 |
|----|------|-----------|
| `useChatTransport` | WS 연결·송수신·재연결 | `ChatTransport`(§5), api-contract §2.1 |
| `useChat` | 메시지 전송·스트림 누적·흐름 | 위 + 채팅 reducer |
| `useTemplateRenderer` | kind→컴포넌트 레지스트리·`text` 폴백 | response-templates |
| `useCta` | CTA 처리(대화형→`/chat`, 커밋→엔드포인트+게이트) | architecture §8, R17 |
| `useCardTap` / `useBridge` | 카드 탭→surface(브릿지/패널)·에스컬레이션 | response-templates §9 |
| `useMultimodalInput` | 카메라/갤러리·권한·업로드 | R10 |
| `useDevices`·`useOrders`·`useHistory`·`useHomeSummary` | 서버 데이터 조회 | api-contract §2.2 |
| `useCart` | 장바구니 ops | 장바구니 reducer |
| `useScreenContext` | 화면 맥락 주입(R9-4) | api-contract |
| `useAnalytics` | 이벤트 트래킹(**동의 게이트**·비차단) | analytics.md, R19 |
| `useConsent` | 동의 범위·opt-out | R19 |
| `useNotifications` | 인앱 알림 표시 | R20 |

> 훅은 **계약(api-contract·response-templates·analytics)** 에만 의존 → 트랜스포트/백엔드 교체에 안전.
> `useAnalytics`는 모든 화면/CTA/흐름 훅에서 호출되지만, 동의 없으면 no-op(R19).

## 12. 후속 / 비범위 (MVP 이후)

- 접근성(VoiceOver·TalkBack·동적 폰트), 국제화(i18n), 실 푸시(FCM/APNs),
  OTA 업데이트(EAS/CodePush), 크래시 리포팅(Sentry), e2e 테스트(Detox), iOS/Android 차이 대응.

## 13. 미해결 / 검증

- **WebSocket 스파이크** 결과로 §5 보정.
- 상태관리·네비게이션 라이브러리 최종 선택(현재 우선안 수준) — 스파이크/프로토타입 후 확정.
