# 프론트엔드 아키텍처 (Frontend Architecture)

> **기반 문서 (공유).** React Native 앱의 내부 구조·결정을 정의한다.
> BE 계약은 `docs/architecture.md`(요청 라우팅) 와 `docs/response-templates.md`(응답 템플릿) 를 따른다.
> FE 구조·라이브러리·트랜스포트 결정이 바뀌면 **이 문서를 갱신**한다.
>
> 각 결정은 **우선안 + 후보안 + 선택/미선택 이유**를 남겨, 추후 교체가 필요할 때 바로 바꿀 수 있게 한다.
> 트랜스포트·상태관리·카드 surface 결정은 `docs/adr/`(ADR-0022·0023·0027)에도 기록.
>
> **BE 계약 연동(최근 작업).** 신원·커밋 라운드트립 계약은 `docs/adr/0050-bff-be-identity-and-commit-contract.md`,
> 응답 표현(템플릿·CTA)은 `docs/response-templates.md`, 타입 단일 출처는 `frontend/src/types/contract.ts`다.
> 아래 §12~§19는 이 연동의 FE 측 구현(렌더·게이트·라우팅·검증)을 상세화한다 — **계약 본문은 위 SoT를 따르며 여기서 중복 정의하지 않는다.**

## 1. 개요 / 범위

- **React Native 앱.** 홈 · CS 페이지 · 어디서든 진입하는 전역 채팅 패널(R9).
- 멀티모달 입출력(R10), 응답 템플릿·CTA 렌더(R11), 스트리밍 응답(R14).
- 디자이너 애셋 미수령 → **토큰/플레이스홀더**로 진행, 애셋 도착 시 값만 교체.
- **FE는 BFF만 호출**한다(WS `/chat`·HTTP 엔드포인트). BE 도메인은 BFF 뒤에 있다(`architecture.md` §9, `api-contract.md` §2).
- 원칙: FE는 **BFF 계약(템플릿 모델)을 렌더**할 뿐, "LLM이냐 API냐" 라우팅은 판단하지 않는다(`architecture.md` §8).

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
- `Message` = `text`(리드) + **`sections[]`**(섹션별 `template`+`ctas`+`label`) + `media` 합성 렌더.
  복합 응답(R7)은 섹션을 **순서대로 세로 스택**, 각 섹션에 의도 라벨·미처리(`handled:false`) 표시.
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
- **조용한 재인증** — 토큰 만료 시 백그라운드로 재발급하고 대화 흐름 유지, 실패 시에만 재로그인 안내(api-contract §3).

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
│  ├─ templates/               # kind → 컴포넌트 레지스트리 (§4·§12, 현재 REGISTRY 13종 + text 폴백)
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
1. **채팅 스트림 환원** — WS 청크(`delta`/`section`/`flow`/`done`/`error`)를 메시지 + **섹션 리스트**(복합 R7) + 스트리밍 상태로 누적(api-contract §2.1).
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

## 12. 응답 계약 표현 — CTA·템플릿 kind (BE 연동)

§4(템플릿 렌더러)를 BE 계약 연동 기준으로 구체화한다. 표현 계약 본문(스키마·선택/CTA 규칙)은
`docs/response-templates.md`, 타입 union 단일 출처는 `frontend/src/types/contract.ts`다.
**여기서는 FE가 렌더/분기하는 위치만 매핑**한다.

### 12.1 CtaKind union (`contract.ts`)
`CtaKind`는 **permissive**(`CtaKind | string`) — BFF가 새 kind를 보내도 깨지지 않게 두되, 코드가
분기하는 알려진 값만 열거한다. `CtaAction`은 `"chat" | "commit" | "navigate"`.

| CTA kind | action | FE 처리(라우팅) | 처리 위치 |
|----------|--------|-----------------|-----------|
| `order`·`booking`(commit) | `commit` | REST 커밋 라운드트립(§13) | `transport/commit.ts`·`state/useCommit.ts` |
| `login` | `navigate` | 로그인 월 오픈 | `useCommit.openLogin()` → `CommitGate.LoginWall` |
| `select_device` | (any) | `payload.device_id`로 **즉시 질의 전송**(입력창 편집 아님) | `onCta`(screens, §14) |
| `booking`(advisory)·`restock_alert`·`compare`·`explain`·`recommend`·`choices` | `chat` | `/chat` 후속(`interaction_reply`) | `useChat.replyInteraction` |

> `booking`은 **kind 이름이 두 경로에 걸친다**: `action:"commit"`이면 예약 확정(§13), 그 외(advisory)는
> chat 후속. 분기는 `isCommitCta(cta)`(action+kind 동시 검사)가 판정한다 — kind 이름만으로 판단하지 않는다.
> CTA 버튼은 `components/message.tsx`의 `CtaRow`가 렌더하며 `action==="commit"`만 primary 강조.

### 12.2 TemplateKind union (`contract.ts`) — 신규 `booking`
`TemplateKind`도 permissive. 미등록 kind·스키마 불일치는 `text` 폴백(`response-templates.md` §7).
레지스트리는 `frontend/src/templates/index.tsx`의 `REGISTRY`(13종)이며, **신규 `booking` 템플릿**을 포함한다.

- **`booking` 렌더러(`templates/index.tsx`의 `Booking`)** — `data:{ visit_type?, slots:[{id,start,end}…] }`.
  방문 유형 배지(`VISIT_KO`) + 슬롯 라디오 리스트(`RadioRow`, `choices`와 공용) + 빈 슬롯 폴백 문구.
  **슬롯 선택은 표시용**이며, 실제 예약 확정은 섹션의 commit CTA(`kind:"booking", action:"commit"`)가 담당(§13).
- `clarify`·`warranty`·`explain` 섹션은 별도 kind 없이 기존 kind(`text`·`recommendation_list`·`booking`)를
  **재사용**한다(`contract.ts` 주석).
- `TemplateView`는 `REGISTRY[kind] ?? text`로 폴백하고, 폴백 시 `data.message`를 텍스트로 노출(`stringifyFallback`).

## 13. 커밋 게이트 — 409 확인 / 401 로그인 (BE 연동)

§4의 "되돌릴 수 없는 커밋"(ActionGate, R17)을 BE 계약(409/401)으로 구체화한다.
**커밋/신원 계약 본문은 `docs/adr/0050-bff-be-identity-and-commit-contract.md`·`docs/api-contract.md`**를 따른다.

### 13.1 트랜스포트 (`transport/commit.ts`)
commit CTA(`kind ∈ {order, booking}`, `action:"commit"`) → REST 커밋 엔드포인트. 경로 매핑은 `PATH`:

| commit kind | BFF 경로 | 비고 |
|-------------|----------|------|
| `order` | `POST /orders` | → BE `/internal/orders`(ADR-0050) |
| `booking` | `POST /bookings` | → BE `/internal/bookings` |

상태코드별 정규화(`CommitResult`):
- **409 `ConfirmationRequired`** → `{status:"confirm", template, payload}`. 응답의 `template`(kind:`confirmation`)을
  보관, 사용자가 확정하면 **`confirmed:true`로 재-POST**(2-step). BE가 template을 안 주면 `demoConfirmation` 폴백.
- **401 `LoginRequired`** → `{status:"login", cta}`. 게스트는 **commit만 게이트**, advisory(chat)는 통과.
- 그 외 **2xx** → `{status:"ok"}`(확정). 비-OK → `{status:"error", code}`.
- **`cfg.base` 미설정(정적 배포·BE 미연결)** → 네트워크를 타지 않고 데모로 정규화: 첫 호출은 confirm 게이트,
  `confirmed`면 ok. `isCommitCta`/`commitFromCta`가 CTA→kind 추출 헬퍼다.

토큰은 `headers()`가 `Authorization: Bearer`로 주입(게스트면 생략).

### 13.2 상태머신 (`state/useCommit.ts`)
`useCommit(cfg, opts)`가 게이트 상태를 들고 `apply(res, kind)`로 전이한다. 노출 상태:
`confirmTemplate`(409 다이얼로그 템플릿·null이면 미표시), `showLogin`(401 월), `busy`(중복 탭 방지).

전이(액션):
- `start(cta)` — kind/payload 추출 후 1차 호출. `pending`(ref)에 보관.
- `confirm()` — `pending`을 `confirmed:true`로 재제출(2-step). `cancelConfirm()`은 다이얼로그·pending 클리어.
- `openLogin()` — 보류 커밋 없이 순수 로그인 월(login CTA용). `login()` — 토큰 확보 후(데모 placeholder
  또는 `opts.onLogin()`) **보류 커밋이 있으면 토큰 동반 1차 재호출**. `dismissLogin()` — 게스트로 계속(닫기).
- 토큰은 게스트→로그인으로 바뀔 수 있어 `tokenRef`로 동적 주입(`cfgNow()`가 최신 토큰으로 ApiConfig 합성).
- 분석 emit: confirm→`checkout_shown`, ok→`order_confirmed`, error→`error_shown`(§17).

### 13.3 게이트 UI (`components/CommitGate.tsx`)
self-contained 오버레이 2종 — 화면이 `useCommit` 상태로 토글한다.
- **`ConfirmDialog`** — 409. `TemplateView`로 confirmation 템플릿 렌더 + 확정/취소. `busy`면 "확정 중…".
- **`LoginWall`** — 401 placeholder. "로그인"(`onLogin`)·"게스트로 계속"(`onDismiss`). 실 로그인 연동은 후속.

### 13.4 흐름 시퀀스 (order commit, 게스트)
```text
사용자 commit CTA 탭
  → onCta: isCommitCta → useCommit.start(cta)
  → commit() POST /orders                         [busy]
  → 401 LoginRequired → showLogin=true            → LoginWall
      → login(): token 확보 → POST /orders(토큰)
  → 409 ConfirmationRequired → confirmTemplate    → ConfirmDialog
      → confirm(): POST /orders {…, confirmed:true}
  → 2xx ok → onCommitted 콜백(+order_confirmed 분석) → 확정 메시지
```

## 14. onCta 라우팅 (screens)

모든 섹션 CTA는 화면의 단일 `onCta(cta)` 라우터로 모인다(`screens/ChatPanel.tsx`·`screens/LiveChat.tsx`,
두 화면 동일 분기). 라우팅 우선순위:

1. **commit** — `isCommitCta(cta)` → `commitCtl.start(cta)`(§13). 409/401 게이트로 진입.
2. **login** — `cta.kind==="login"` → `commitCtl.openLogin()`(로그인 월).
3. **select_device** — `cta.kind==="select_device"` → `payload.device_id`로 **즉시 질의 전송**(`sendQuery`/`submit`). 입력창에 채워 편집하는 방식이 아니라 탭 즉시 해당 기기 질의를 보낸다.
4. **그 외(chat 후속)** — `replyInteraction(cta)` → `/chat`으로 `interaction_reply` 전송(explain·restock_alert·
   compare·booking(advisory)·recommend·choices…).

모든 경로 진입 시 `cta_clicked` 분석 emit(§17).

## 15. 미처리(unhandled) 섹션 — R7

복합 응답(R7)의 섹션 중 `handled=false`는 **정상 답변과 시각적으로 구분**해 렌더한다
(`components/message.tsx`의 `UnhandledSection`).
- `SectionView`가 `!section.handled`면 `UnhandledSection`으로 분기(정상은 `Card`).
- 톤다운 스타일: 점선 테두리·뮤트 배경·"처리 보류" 배지·"이건 아직 도와드리기 어려워요" 리드.
- `template.data.message`/`detail`을 보조 노출하고, **CTA(입고 알림·대체 추천 등)는 남겨** 대안 행동을 유지.

## 16. 레이턴시 UX — 타이핑/스트리밍 인디케이터 (R14)

§8(스트리밍 타이핑 인디케이터)의 구현. 진행 중 어시스턴트 턴은 `components/StreamingMessage.tsx`가 렌더.
- delta 누적 텍스트 + section 세로 스택(§4 `SectionView` 재사용) 합성.
- **아직 아무것도 도착 안 한 수신 중**(`streaming && !text && sections.length===0`) → 순수 타이핑 인디케이터
  (`TypingDots`, 점 3개 페이드 루프). 내용 도착 시 텍스트/섹션으로 전환, `done`이면 인디케이터 제거.
- 진행 문구는 **답변 중심**만 — 내부 시스템·대기 상태는 노출하지 않는다.
- `ChatPanel`은 자체 `TypingDots`·`AssistantMessage`로 동일 패턴, `LiveChat`은 "답변을 작성하고 있어요…" 캡션 폴백.
- 생성 중에는 입력창·전송·추천 칩을 비활성(`editable={!streaming}`)해 중복 전송을 막는다.

## 17. 분석 (analytics) — `analytics/track.ts`

택소노미 본문은 `docs/analytics.md` §4(이벤트명 `object_action` 과거형)를 따른다. FE는 **가벼운 emit 유틸**만 둔다.
- `track(name, props?)` — 이벤트 1건 발행, **비차단**(try/catch — 분석은 절대 UX를 막지 않음).
- 기본 싱크는 **console**(`consoleSink`, 개발 가시성), `setAnalyticsSink`로 교체 가능. **BFF/BE 싱크는 후속(deferred)**.
- `AnalyticsEventName`은 FE-소유 이벤트명 열거(permissive). 배선 지점: 턴 전송 `message_sent`(screens),
  CTA 탭 `cta_clicked`(onCta), 커밋 게이트 `checkout_shown`·확정 `order_confirmed`·실패 `error_shown`(`useCommit`).
- `order_confirmed`의 owner는 BE이나, **FE 데모/오프라인(BE 미연결) 커밋 확정도 가시화**하려고 같은 이름으로 발행
  (실 연동 시 BE가 진실의 출처).

## 18. 검증 (서브시스템 게이트)

`frontend/` 변경 시 게이트는 **jest + vite build**다. CLAUDE.md §레포 구조와 동일하게 `tsc --noEmit`은 게이트가 아니다
(react-native 타입 부재로 기존 noise 다수).

- `cd frontend && npx jest` — **현재 67 통과**(13 suites). 컴포넌트·계약(stub)·게이트·라우팅 테스트.
- `cd frontend && npx vite build` — 웹 빌드 성립 확인.
- BE 계약(409/401·CTA·template kind)을 바꾸면 **3계층 동기화**(CLAUDE.md): `contract.ts`·`bff/gateway/`·
  `docs/api-contract.md`·`docs/response-templates.md`·ADR-0050를 함께 갱신·검증.

## 19. 계약 경계 / SoT 링크

FE는 **BFF 계약을 렌더·게이트**할 뿐, 라우팅(LLM/API)·신원 해석은 BE/BFF가 판단한다. 중복 정의 금지 — 본문은 SoT를 따른다.

| 주제 | 단일 출처(SoT) | FE 대응 |
|------|----------------|---------|
| 신원·커밋(409/401·헤더·경로) | `docs/adr/0050-bff-be-identity-and-commit-contract.md`·`docs/api-contract.md` | `transport/commit.ts`·`useCommit.ts` |
| 응답 표현(템플릿·CTA·섹션) | `docs/response-templates.md` | `templates/index.tsx`·`components/message.tsx` |
| 공유 타입(union·DTO) | `frontend/src/types/contract.ts` | 전 컴포넌트가 import |
| 분석 택소노미 | `docs/analytics.md` | `analytics/track.ts` |

## 20. 후속 / 비범위 (MVP 이후)

- 접근성(VoiceOver·TalkBack·동적 폰트), 국제화(i18n), 실 푸시(FCM/APNs),
  OTA 업데이트(EAS/CodePush), 크래시 리포팅(Sentry), e2e 테스트(Detox), iOS/Android 차이 대응.
- **실 로그인 연동**(LoginWall placeholder 대체·토큰 발급·조용한 재인증 §9), **분석 BFF/BE 싱크**(§17 deferred).

## 21. 미해결 / 검증

- **WebSocket 스파이크** 결과로 §5 보정.
- 상태관리·네비게이션 라이브러리 최종 선택(현재 우선안 수준) — 스파이크/프로토타입 후 확정.
