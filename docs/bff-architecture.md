# BFF 아키텍처 — 기여자 오리엔테이션

> `bff/gateway/` 에서 작업을 시작하는 사람의 **첫 문서**다.
> 여기서는 BFF의 책임·구조·핵심 흐름을 잡고, **계약·결정의 세부는 SoT(진실의 출처)로 링크**한다.
> 중복 정의하지 않는다(§8 참조). 코드 기준 경로/함수는 모두 `bff/gateway/` 실제 구현에 근거한다.

BFF(Backend-for-Frontend)는 `FE ↔ BFF ↔ BE` 3계층(`docs/architecture.md` §9)의 **클라이언트 표면**이다.
FE는 이 서비스만 본다. BE 도메인 내부 API(`/internal/*`)를 중계·정형화하고, 신원 포워딩을 더한다.

---

## 1. 책임 경계

**BFF가 하는 것**
- **인증·신원 해석** — Authorization 헤더(또는 WS `?token=`)로 로그인/게스트를 구분한다(`auth.py`).
- **신원 포워딩** — 모든 BE 호출에 신원을 싣는다. HTTP는 헤더(`X-User-Id` | `X-Guest-Token`),
  WS `/chat`은 payload(`user_id`·`guest_token`)로 주입한다.
- **중계(relay)** — BE 응답의 **상태코드·본문을 그대로 패스스루**한다(401/409/403/410 포함).
- **변환(transform)** — 인터랙션 회신을 다음 턴 텍스트로 바꾸고(`interaction_to_text`),
  업스트림 장애를 클라이언트 폴백 계약으로 정규화한다(`fallback_body`).
- **스트림 포워딩** — BE 대화 스트림(NDJSON)을 **버퍼링 없이 도착 즉시** WS로 흘려보낸다.

**BFF가 안 하는 것**
- **도메인 로직 없음** — 주문/예약/견적 판정, 금액 계산, 커밋 게이트(409/401 판정)는 **모두 BE**가 한다.
  BFF는 그 결과를 막지도 바꾸지도 않고 중계만 한다.
- **상태 보유 없음** — 세션/대화/주문 상태를 BFF가 들고 있지 않다. 게스트 토큰조차 저장하지 않고
  매 요청 해석한다(없으면 새로 발급해 응답 흐름에 실음).
- **토큰을 도메인 모델에 저장하지 않는다**(architecture NFR, `auth.py` 모듈 docstring).

---

## 2. 구조 맵

`bff/gateway/` 의 모듈별 역할과 핵심 함수:

| 모듈 | 역할 | 핵심 함수 / 심볼 |
|------|------|------------------|
| `main.py` | FastAPI 앱 팩토리. HTTP 라우트 + WS `/chat` 루프. | `create_app(backend)`, `chat(ws)` (WS), `_backend(request)` |
| `auth.py` | 신원 해석(로그인/게스트), FastAPI 의존성. | `Identity`(dataclass), `resolve_identity`, `identity_dep`, `require_login`, (레거시) `require_auth`·`ws_user` |
| `backend_client.py` | BE `/internal/*` 호출(`httpx.AsyncClient`) + 헤더 스레딩. | `BackendClient`, `turn_stream`(스트림), 엔드포인트별 메서드(`home`·`place_order`·…) |
| `transform.py` | 중계 헬퍼·폴백 정규화·인터랙션 변환. | `relay`, `fallback_body`, `interaction_to_text` |
| `config.py` | 환경설정. | `BE_BASE_URL`(기본 `http://localhost:8001`), `UPSTREAM_TIMEOUT`(기본 10.0s) |

**팩토리 패턴.** `create_app(backend)`는 `BackendClient`를 주입받는다(생략 시 기본 생성).
테스트는 `httpx.ASGITransport`로 BE 앱을 인프로세스 연결한 `BackendClient`를 주입해
**실제 HTTP 계약**을 그대로 검증한다(§6).

**`Identity`의 두 출력 메서드** (신원 포워딩의 중심):
- `headers()` → HTTP용. `user`면 `{"X-User-Id": id}`, `guest`면 `{"X-Guest-Token": id}`.
- `ws_fields()` → WS payload용. `{"user_id": …, "guest_token": …}` (해당 없는 쪽은 `None`).

---

## 3. 핵심 흐름

### (a) WS `/chat` 한 턴 (`main.py` `chat(ws)`)

1. **연결·신원 해석.** `ws.accept()` 후 토큰을 읽는다. 브라우저 WS는 헤더를 못 보내므로
   `Authorization` 헤더 **또는** 쿼리 `?token=` 둘 다 허용한다. 게스트 토큰은 `?guest_token=`.
   `resolve_identity(token, guest_token)` → 토큰 있음=`user`, 없음=`guest`(없으면 신규 발급).
2. **메시지 수신·검증.** `type`이 `user_message` | `interaction_reply`가 아니면 `{"type":"error","code":"bad_request"}` 후 다음 메시지로.
3. **입력 텍스트 결정.** `user_message`면 `text` 그대로, `interaction_reply`면 `interaction_to_text(msg)`로
   다음 턴 입력 텍스트로 변환(§5 커밋 스코핑 주석 참고: WS 경로는 커밋 채널을 새로 만들지 않는다).
4. **payload 구성·신원 주입.** `{session_id, text, screen_context, **idy.ws_fields()}` — `user_id`/`guest_token` 주입.
5. **증분 포워딩.** `be.turn_stream(payload, headers=idy.headers())`의 청크를 **모으지 않고** 도착 즉시
   `ws.send_json(chunk)`로 중계한다(operations §9). 이 청크가 §2.1 섹션 스트림 봉투다.
6. **스트림 실패 처리.** 예외 시 — 이미 일부 전송했으면(`sent_any`) `stream_interrupted` 에러로 마감,
   아무것도 못 보냈으면 일반 폴백 에러. `WebSocketDisconnect`면 조용히 종료.

### (b) HTTP 커밋/조회 (예: `POST /orders`)

1. **신원 해석.** `identity_dep`(의존성)이 헤더+쿼리/쿠키에서 신원을 해석한다.
2. **BE 호출.** `be.place_order(body, headers=idy.headers())` — `X-User-Id` | `X-Guest-Token` 헤더로 전달.
   (`/orders`·`/quotes/convert`는 로그인 시 body에 `user_id`를 `setdefault`로도 채운다.)
3. **그대로 중계.** `relay(...)`가 BE 응답의 **상태코드·본문을 패스스루**한다.
   미확인 커밋 → BE **409** `ConfirmationRequired`, 게스트 커밋(MULTITENANT on) → BE **401** `LoginRequired` —
   **BFF는 막지 않고 둘 다 그대로 중계**한다. 업스트림 장애만 503 폴백으로 정규화한다.

> 신원 토큰 누수 방지: `/stores`는 쿼리에서 `guest_token`을 제거하고 BE로 보낸다(`main.py`).

---

## 4. 계약 경계

BFF는 **두 계약의 경계**에 있다. 세부 스키마는 SoT로 링크한다(중복 금지).

**FE ↔ BFF** (BFF가 소유 — `docs/api-contract.md` §2)

| 표면 | 내용 | SoT |
|------|------|-----|
| WS `/chat` | msg 타입 `user_message`·`interaction_reply` 입력 / 섹션 스트림 봉투 출력 | api-contract §2.1, response-templates |
| 결정적 HTTP | `/devices`·`/home`·`/catalog/recommend`·`/orders`·`/bookings`·`/stores`·`/quotes`·`/surface`·`/resume`·`/reengagement` 등 | api-contract §2.2·§2.3 |

**BFF ↔ BE** (`/internal/*`, 응답 패스스루 — `docs/api-contract.md` §2.4)

| 항목 | BFF→BE | BE→BFF(그대로 중계) | SoT |
|------|--------|---------------------|-----|
| 신원 (HTTP) | `X-User-Id` \| `X-Guest-Token` 헤더 | — | ADR-0050 §1 |
| 신원 (WS) | payload `user_id`·`guest_token` (+헤더 동봉) | — | ADR-0050 §1 |
| 게스트 커밋 | 막지 않음 | **401** `LoginRequired` (+`cta.kind:"login"`) | ADR-0050 §2·§3 |
| 미확인 커밋 | 막지 않음 | **409** `ConfirmationRequired` (주문·예약·견적전환) | api-contract §2.2 |
| O2O 상태 | — | 403/410/409 (견적 권한·만료·역전이) | api-contract §2.2 |
| 업스트림 장애 | — | (BFF가 **503/502 폴백**으로 정규화) | api-contract §4, R13 |

세부 계약: `docs/api-contract.md` §2·§3, 신원·커밋 결정의 *이유·기각안*은 `docs/adr/0050-bff-be-identity-and-commit-contract.md`,
응답 봉투/템플릿 모양은 `docs/response-templates.md`.

---

## 5. 신원·게스트 (핵심)

신원 해석은 BFF의 **유일한 판정 로직**이다(나머지는 BE). 규칙은 단순하다(`auth.py`):

- **토큰 있음 → `user`** (`MOCK_USER_ID = "usr_01"`). MVP는 Mock 검증 — 통과 시 고정 사용자.
- **토큰 없음 → `guest`** — 전달된 `guest_token`(쿼리 `?guest_token=` / 쿠키)을 재사용, 없으면
  `_new_guest_token()`(`"g-"+uuid`)으로 **새로 발급**.

**게스트 정책 (advisory 허용, 커밋만 BE가 게이트).**
게스트도 **자문·대화 턴은 허용**한다 — 조회(`/devices`·`/stores`·`/resume`…)와 WS `/chat`이 401로 막히지 않는다.
**커밋(주문/예약/견적전환)도 BFF는 막지 않는다.** 게스트가 커밋하면 BE가 **401 `LoginRequired`**
(`cta.kind:"login"`)를 돌려주고, BFF는 그대로 중계한다(공유 계약). 즉 로그인 강제 판정은 BE 단일 지점.

의존성 선택:
- `identity_dep` — 사용자/게스트 공용. 자문·조회·커밋 중계 경로가 모두 쓴다(현재 모든 HTTP 라우트).
- `require_login` — 로그인만 허용(게스트/무토큰 → 401). **진짜 로그인 필수** 엔드포인트용(현재 미사용, 향후 대비).
- (레거시) `require_auth`·`ws_user` — 하위호환 이름. 신규 코드는 `identity_dep`/`resolve_identity`를 쓴다.

> MVP는 **Mock 인증**이다. 실 삼성 계정 SSO·세션 TTL·조용한 재인증은 후속(§7).

---

## 6. 테스트 / 검증

```bash
cd bff && python -m pytest        # 현재 45 케이스 통과
```

계약 테스트는 `BackendClient`를 `httpx.ASGITransport`로 **BE 앱에 인프로세스 연결**해
FE↔BFF↔BE를 **실제 HTTP 계약**으로 묶어 검증한다(별도 서버 불필요, `conftest.py`).
BE를 import하므로 `../backend/requirements.txt`도 설치해야 한다(`bff/README.md`).

커버 영역:

| 파일 | 커버 |
|------|------|
| `tests/test_endpoints.py` | 헤더 전달(`X-User-Id`/`X-Guest-Token` 캡처), 게스트 조회 허용, 커밋 게이트 409 중계, 게스트 커밋 401(`MULTITENANT=1`) 중계, 예약 409, 폴백 503 |
| `tests/test_chat_ws.py` | 섹션 스트림 중계, 인터랙션 회신, 게스트 advisory 허용, WS 신원 포워딩(payload+헤더), 부분 전송 후 `stream_interrupted` |
| `tests/test_o2o_endpoints.py` | O2O 패스스루(거점·재고·픽업 전이·견적 403/410/409·전환), 게스트 거점 조회, 폴백 |
| `tests/conftest.py` | 인프로세스 BE fixture(`be_backend`/`client`), 장애 시뮬레이션(`broken_client`) |

> 결정성 고정: `conftest.py`가 BE import 전에 `LLM_BACKED=""`로 꺼 실 LLM 경로를 차단한다.

---

## 7. 현재 상태 & 후속

**된 것**
- 신원 전달(HTTP 헤더 / WS payload), 게스트(비로그인) advisory 허용 + 토큰 발급.
- 모든 BE 응답 패스스루 중계(401/409/403/410/404), 업스트림 장애 폴백 정규화(R13).
- 증분 스트림 포워딩(버퍼링 없음, 부분 실패 시 `stream_interrupted`).
- 계약 확정: `docs/adr/0050-bff-be-identity-and-commit-contract.md`.

**후속**
- **인-챗 구조적 커밋 채널** — 현재 WS 경로는 커밋 채널을 만들지 않고, FE가 commit-kind 인터랙션을
  REST(`/orders`·`/bookings`)로 직접 호출한다(`main.py` ⑥ 주석). WS 내 구조적 커밋은 향후 과제.
- **실 SSO** — Mock 토큰 → 삼성 계정 SSO·세션 TTL·조용한 재인증(`auth.py`).
- **analytics 싱크** — 사용 분석 이벤트 전달(`docs/analytics.md` 택소노미와 정합).

---

## 8. SoT 링크 / 중복 금지

이 문서는 **오리엔테이션**이다. 아래가 진실의 출처(SoT)이며, 변경은 거기서 한다:

| 주제 | SoT |
|------|-----|
| 엔드포인트·경계 스펙(FE↔BFF, BFF↔BE) | `docs/api-contract.md` §2·§3·§2.4 |
| 신원·게스트·커밋 왕복 **결정(이유·기각안)** | `docs/adr/0050-bff-be-identity-and-commit-contract.md` |
| 응답 봉투/템플릿 모양 | `docs/response-templates.md` |
| 전체 시스템 아키텍처·3계층 | `docs/architecture.md` |
| 스트리밍·증분 포워딩·폴백 운영 | `docs/operations.md`, `docs/orchestration.md` |

**규칙(CLAUDE.md 문서 계층):** 데이터 모델·공개 인터페이스·계약이 바뀌면 이 문서가 아니라
**위 기반 문서를 갱신**하고, 여기서는 링크만 한다. 계약 변경은 3계층 동기화
(BE 계약 ↔ `bff/gateway/` ↔ `frontend/src/types/contract.ts`)를 함께 검증한다.
