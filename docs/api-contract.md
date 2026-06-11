# API 계약 (API Contract)

> **기반 문서 (공유).** 클라이언트(FE)↔서버(FastAPI)의 **외부 노출 인터페이스**를 정의한다.
> 데이터 타입은 `docs/data-model.md`, 응답 표현은 `docs/response-templates.md`,
> 라우팅 원칙은 `docs/architecture.md` §8, 오케스트레이션 내부는 `docs/orchestration.md` 를 본다.

## 1. 핵심 경계 — "전부 API가 아니다"

호출을 세 종류로 구분한다. **외부로 노출하는 것만 HTTP/WS API**고, 내부는 함수·DB 접근이다.

| 종류 | 누가 호출 | 형태 | 예 |
|------|-----------|------|-----|
| **외부 노출 API** | 클라이언트(FE) | HTTP/WS 엔드포인트 | `/chat`(WS), `/orders`, `/devices` |
| **내부 도메인 호출** | 오케스트레이터 → 도메인 서비스 | **인프로세스 함수 호출** (HTTP 아님) | `device_service.get_status(...)` |
| **데이터 접근** | 도메인 서비스 → 데이터 | 외부면 **Port(API)**, 내부면 **Repository(DB)** | `STP.fetch(...)` / `conv_repo.get(...)` |

**원칙**
- 단일 FastAPI 프로세스라 **오케스트레이터→도메인은 HTTP가 아니라 함수 호출**이다. (마이크로서비스 아님)
- **내부 데이터는 DB/Repository로 직접** 접근한다. 외부 연동(SmartThings·O2O 등)만 Port로 추상화해 API화한다.
- 즉 "기기 상태 조회"는 외부(SmartThings)라 Port, "대화 이력 조회"는 내부라 **DB 함수**다. 모든 동작을 API로 만들지 않는다.
- LLM **tool**은 이 셋 위의 얇은 어댑터다(구현이 함수/DB/Port 중 무엇이든 무관) — `docs/orchestration.md` §3.

## 2. 클라이언트 API 표면

라우팅 두 갈래(`architecture.md` §8)에 대응한다.

### 2.1 대화 — WebSocket `/chat`
자연어·멀티모달·인터랙션 회신의 단일 양방향 채널(트랜스포트 결정은 `frontend-architecture.md` §5).

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
{ "type": "delta", "text": str }                            # 텍스트 토큰
{ "type": "template", "template": Template }                # 구조화 출력(완성 단위)
{ "type": "flow", "active_flow": str | None }               # 흐름 상태(R6)
{ "type": "done", "message_id": Id, "ctas": [Cta] }         # 메시지 종료
{ "type": "error", "code": str, "fallback": Template }      # 폴백(R13)
```

### 2.2 결정적 HTTP 엔드포인트 (조회·커밋)
FE의 **구조화된 호출**(조회·커밋)은 LLM 미경유로 직행(architecture §8). 응답은 **`Template`/상태**로 정형화.

> **CTA는 두 종류다.** 이 결정적 채널을 쓰는 건 **되돌릴 수 없는 커밋**(결제·주문·예약 확정)과
> 단순 조회뿐이다. **대화형 CTA**(제안 칩, `choices`/`confirmation`/`booking` 회신, 설명 요청)는
> §2.1 `/chat`으로 재진입해 **LLM을 탈 수 있다.** "CTA = 결정적"이 아니라 "**커밋 = 결정적**"이다.

| 엔드포인트 | 메서드 | 용도 | 요구사항 |
|------------|--------|------|----------|
| `/cart` | POST/GET/DELETE | 장바구니 담기·조회 | R4 |
| `/orders` | POST | 주문/결제 확정(ActionGate) | R4·R17 |
| `/orders/{id}` | GET | 주문 상태·이력 | R12 |
| `/bookings` | POST | 방문 예약 슬롯 확정 | R18 |
| `/devices` | GET | 기기 목록·상태 | R2 |
| `/handoff` | POST | 상담원 연결 접수 | R18 |
| `/history` | GET | 대화·주문 이력(페이지네이션) | R12 |

> 도메인 엔드포인트의 요청/응답 스키마 필드는 `docs/data-model.md` 타입을 그대로 쓴다.

## 3. 인증 / 세션

- 인증 토큰은 헤더로 전달(`Authorization`), **도메인 모델에 저장 안 함**(architecture NFR). MVP는 AuthP Mock.
- `session_id` 로 대화 맥락(FlowState)을 식별. 세션은 TTL 휘발성 저장(Redis 후보).
- WebSocket 연결 시 토큰 검증(인증 게이트 = API/표현 계층, architecture §9).

## 4. 에러 / 폴백 (R13)

- 모든 외부 실패는 **클라이언트 계약(폴백 응답)으로 정규화**한다. 대화 전체를 중단시키지 않는다.
- 표준 에러 형태: `{ "code": str, "message": str, "fallback": Template | None }`.
- 되돌릴 수 없는 행동(R17)은 `confirmation` 게이트를 통과해야 커밋한다.

## 5. 비범위

- 실제 결제·인증 프로토콜 세부(SSO 등)는 실 전환 시. MVP는 Mock 경계(architecture §5).
- Rate limit·버저닝 정책은 후속.
