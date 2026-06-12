# API 계약 (API Contract)

> **기반 문서 (공유).** 클라이언트(FE)↔BFF, BFF↔BE의 **노출 인터페이스**를 정의한다.
> 데이터 타입은 `docs/data-model.md`, 응답 표현은 `docs/response-templates.md`,
> 라우팅 원칙은 `docs/architecture.md` §8, 서비스 분리는 §9, 오케스트레이션 내부는 `docs/orchestration.md` 를 본다.

## 1. 핵심 경계 — "전부 API가 아니다"

호출을 네 종류로 구분한다. **계층을 넘는 것만 HTTP/WS API**고, 한 서비스 안은 함수·DB 접근이다.

| 종류 | 누가 호출 | 형태 | 예 |
|------|-----------|------|-----|
| **클라이언트 API** | 클라이언트(FE) → **BFF** | HTTP/WS 엔드포인트 | `/chat`(WS), `/orders`, `/devices` (§2) |
| **내부 BFF↔BE API** | BFF → **BE 도메인** | HTTP/WS (네트워크) | `POST /internal/turn`, BE 스트림 중계 (§2.4) |
| **BE 인프로세스 호출** | 오케스트레이터 → 도메인 서비스 | **함수 호출** (HTTP 아님) | `device_service.get_status(...)` |
| **데이터 접근** | 도메인 서비스 → 데이터 | 외부면 **Port(API)**, 내부면 **Repository(DB)** | `STP.fetch(...)` / `conv_repo.get(...)` |

**원칙**
- **FE는 BFF만 본다.** 클라이언트 계약(§2)은 BFF가 소유하고, BFF는 BE 도메인을 **내부 API**(§2.4)로 호출한다(architecture §9).
- BE 도메인 안에서 **오케스트레이터→도메인은 HTTP가 아니라 함수 호출**이다(한 프로세스). BFF↔BE만 네트워크 경계.
- **내부 데이터는 DB/Repository로 직접** 접근한다. 외부 연동(SmartThings·O2O 등)만 Port로 추상화해 API화한다.
- 즉 "기기 상태 조회"는 외부(SmartThings)라 Port, "대화 이력 조회"는 내부라 **DB 함수**다. 모든 동작을 API로 만들지 않는다.
- LLM **tool**은 이 셋 위의 얇은 어댑터다(구현이 함수/DB/Port 중 무엇이든 무관) — `docs/orchestration.md` §3.
- **계약 드리프트 방지** — 클라이언트↔BFF와 BFF↔BE는 같은 data-model DTO를 쓴다. BFF는 변환·중계만 하고 새 타입을 만들지 않는다.

## 2. 클라이언트 API 표면

라우팅 두 갈래(`architecture.md` §8)에 대응한다.

### 2.1 대화 — WebSocket `/chat`
자연어·멀티모달·인터랙션 회신의 단일 양방향 채널(트랜스포트 결정은 `frontend-architecture.md` §5).
아래는 WS 봉투(`type` 판별자)이며, 본문은 data-model DTO에 대응한다:
`user_message`≈`ChatRequest`, `interaction_reply`≈`InteractionReply`, 청크≈`ChatResponseChunk`(data-model §4).

**클라이언트 → 서버 메시지**
```python
# user_message — 자유 입력(R1·R10)
{ "type": "user_message", "session_id": Id, "text": str,
  "media": [Media], "screen_context": dict | None }        # 화면 맥락(R9-4)

# interaction_reply — 인터랙션 템플릿 회신(response-templates §8)
{ "type": "interaction_reply", "session_id": Id,
  "ref": Id,                                                # 원본 메시지/템플릿
  "kind": "choices|confirmation|booking",
  "payload": dict }                                         # 선택/확정 값
```

**서버 → 클라이언트 스트림 청크** (점진적 전달, R14)
```python
{ "type": "delta", "text": str }                            # 리드/섹션 텍스트 토큰
{ "type": "section", "section": MessageSection }            # 섹션 1개(복합이면 의도 순서대로 여러 번)
{ "type": "flow", "active_flow": str | None }               # 흐름 상태(R6)
{ "type": "done", "message_id": Id }                        # 메시지 종료(누적 sections로 확정)
{ "type": "error", "code": str, "fallback": Template }      # 폴백(R13)
```
> **복합 질문(R7)** — 의도별 `section` 청크를 **우선순위 순서대로** 보낸다. 각 `section`은 `label·intent·
> template·ctas·handled`(미처리=`handled:false`). FE는 섹션을 순서대로 누적·렌더(`response-templates.md` §5).

### 2.2 결정적 HTTP 엔드포인트 (조회·커밋)
FE의 **구조화된 호출**(조회·커밋)은 LLM 미경유로 직행(architecture §8). 응답은 **`Template`/상태**로 정형화.

> **CTA는 두 종류다.** 이 결정적 채널을 쓰는 건 **되돌릴 수 없는 커밋**(결제·주문·예약 확정)과
> 단순 조회뿐이다. **대화형 CTA**(제안 칩, `choices`/`confirmation`/`booking` 회신, 설명 요청)는
> §2.1 `/chat`으로 재진입해 **LLM을 탈 수 있다.** "CTA = 결정적"이 아니라 "**커밋 = 결정적**"이다.

요청/응답 본문은 **`docs/data-model.md`의 DTO/엔티티 타입을 그대로** 쓴다(중복 정의 금지). 엔드포인트별 계약:

| 엔드포인트 | 메서드 | 요청 | 응답 | 요구사항 |
|------------|--------|------|------|----------|
| `/devices` | GET | – | `list[Device]` | R2 |
| `/devices/{id}` | GET | – | `Device` (+ `[Anomaly]`) | R2·R5 |
| `/cart` | GET | – | `Order`(DRAFT) | R4 |
| `/cart` | POST | `CartRequest` | `Order`(DRAFT) | R4 |
| `/cart/items/{part_id}` | DELETE | – | `Order`(DRAFT) | R4 |
| `/orders` | POST | `OrderRequest`(`confirmed=true`) | `Order` / `409 ConfirmationRequired` | R4·R17 |
| `/orders/{id}` | GET | – | `Order` (상태·이력) | R12 |
| `/bookings/slots` | GET | – | `list[BookingSlot]` | R18 |
| `/bookings` | POST | `BookingRequest` | `Booking` | R18 |
| `/handoff` | POST | `{type, context_ref}` | `ServiceRequest` | R18 |
| `/history` | GET | `?limit&cursor` | `Page[Conversation \| Order]` | R12 |
| `/resume` | GET | `?fresh` | `ResumePayload`(`has_context`·`summary`·`facts`·`open_loops[]`·`elapsed_label`·`suspended_flow`) | 컴패니언 §1·§2 |
| `/reengagement` | GET | – | `ReEngagement`(`primary_ref`·`primary_label`·`kind`·`also_count`·`message`) \| `{}` | 컴패니언 §3(ADR-0042) |
| `/reengagement/deliver` | POST | – | `ReEngagement` \| `{}` (전달 확정 + 재노출 억제) | 컴패니언 §3.3 |
| `/open-loops/{ref}/{action}` | POST | `action`=`resolve`\|`dismiss` | `OpenLoop` / `404` | 컴패니언 §2.3 |

- `/orders` POST는 `confirmed=false`거나 게이트 미통과면 **`409`(`ConfirmationRequired`)** 반환(R17). 클라이언트는 `confirmation` 템플릿으로 확인 후 재요청.
- 목록은 모두 **커서 페이지네이션**(`Page`, data-model §5).

### 2.3 카드 탭 — surface 결정 (브릿지 vs 패널)
카드 탭은 **BE가 surface를 동적 판단**한다(response-templates §9). bridge는 단발이라 `/chat`이 아닌 전용 호출.

```python
POST /surface   요청 { "card_type": str, "ref": Id, "screen_context": dict | None }
  → { "surface": "bridge", "template": <bridge> }            # 간단 → 모달(S4)
  → { "surface": "panel",  "conversation_id": Id }            # 복잡 → 대화 패널(S3) 진입
```
- `bridge.summary`는 LLM 생성 가능(가벼운 단발). 무거운 추론은 `surface: panel`로 넘긴다.
- 에스컬레이션(`bridge.escalate`)·복잡 분기는 §2.1 `/chat`으로 이어진다.

## 2.4 내부 계약 — BFF ↔ BE 도메인

BFF는 클라이언트 표면을 받고, **추론·도메인 처리는 BE 도메인에 위임**한다(architecture §9). BFF는 변환·중계만 한다.

| 호출 | 메서드 | 요청 | 응답 | 대응 클라이언트 표면 |
|------|--------|------|------|----------------------|
| `/internal/turn` | WS | `{ session_id, text, media, screen_context }` | **청크 스트림**(`delta`·`section`·`flow`·`done`·`error`, §2.1과 동일 봉투) | WS `/chat` |
| `/internal/interaction` | WS | `{ session_id, ref, kind, payload }` | 청크 스트림 | `interaction_reply` |
| `/internal/surface` | POST | `{ card_type, ref, screen_context }` | `{ surface, template \| conversation_id }` | `POST /surface` |
| `/internal/devices` 등 | GET/POST | §2.2 요청과 동일 | §2.2 응답(`Device`·`Order` 등) DTO | 결정적 엔드포인트 |

**원칙**
- **같은 봉투·DTO 재사용** — BE→BFF 청크는 §2.1 클라이언트 청크와 **동일 봉투**다. BFF는 그대로 중계(필요 시 인증·세션 주입만).
- **라우팅은 BE 소유** — "LLM vs 도메인" 판단은 BE 오케스트레이터(§8). BFF는 `/internal/turn`에 그대로 넘긴다.
- **커밋은 BFF에서 게이트** — 되돌릴 수 없는 커밋(`/orders` 등 R17)은 BFF가 `confirmed`·인증을 검증한 뒤 BE 도메인 호출.
- **인증 경계** — 토큰 검증·세션 식별은 **BFF가 수행**, BE 도메인은 검증된 `session_id`·사용자 컨텍스트를 신뢰한다(내부망 전제).
- **폴백** — BE 실패 시 BFF가 §4 폴백 응답으로 정규화해 클라이언트 계약을 지킨다(R13).

## 3. 인증 / 세션

- 인증 토큰은 헤더로 전달(`Authorization`), **도메인 모델에 저장 안 함**(architecture NFR). MVP는 AuthP Mock.
- `session_id` 로 대화 맥락(FlowState)을 식별. 세션은 TTL 휘발성 저장(Redis 후보).
- WebSocket 연결 시 토큰 검증(인증 게이트 = API/표현 계층, architecture §9).
- **세션 토큰 만료(조용한 재인증, L)** — 대화 중 만료되면 **백그라운드로 토큰을 재발급**하고 진행 흐름을
  유지한다. 재발급 실패 시에만 재로그인을 안내(R13). 사용자 흐름을 끊지 않는다.

## 4. 에러 / 폴백 (R13)

- 모든 외부 실패는 **클라이언트 계약(폴백 응답)으로 정규화**한다. 대화 전체를 중단시키지 않는다.
- 표준 에러 형태: `{ "code": str, "message": str, "fallback": Template | None }`.
- 되돌릴 수 없는 행동(R17)은 `confirmation` 게이트를 통과해야 커밋한다.

## 5. Mock / 스텁 — 병렬 개발

세 워크스트림(**FE · BFF · BE 도메인**, 독립 브랜치)이 **서로 막히지 않고** 병렬 개발하도록, Mock을 **두 레벨**로 둔다.

| 레벨 | 무엇 | 누가 쓰나 | 출처 |
|------|------|-----------|------|
| **Port 레벨 Mock** | 외부 어댑터(SmartThings·O2O 등) 가짜 구현 | BE 도메인 | data-model §6, architecture §5 |
| **계약 레벨 Stub 서버** | API 경계를 고정 응답으로 흉내 — 클라이언트↔BFF(§2)와 BFF↔BE(§2.4) **두 경계** | FE는 BFF stub에, BFF는 BE stub에 | **이 문서 + response-templates + data-model DTO** |

**계약 Stub 서버 규칙**
- **이 계약을 단일 출처로** 따른다 → FE가 stub에, 실 BE가 같은 계약에 수렴해 **계약 드리프트를 방지**한다.
- `/chat` WS stub: 스크립트된 청크 시퀀스(`delta`→`template`→`done`)를 재생하고, `interaction_reply`는 다음 시나리오로 진행/에코.
- 엔드포인트 stub: data-model **불변식을 만족하는 fixture**(`Device`·`Order`·`Booking` 샘플) 반환. `/orders`는 `confirmed` 분기·`409`도 흉내.
- 구현은 별도 경량 서비스 또는 FE 개발용 mock(MSW 류)·BE의 `Mock*` 어댑터 재사용 중 택1.

**계약 테스트** — FE↔stub와 실 BE↔동일 계약을 같은 fixture/스키마로 검증해, 통합 시 합치를 보장한다(테스트 디렉터리는 data-model §8 `tests/`).

## 6. 비범위

- 실제 결제·인증 프로토콜 세부(SSO 등)는 실 전환 시. MVP는 Mock 경계(architecture §5).
- Rate limit·버저닝 정책은 후속.
