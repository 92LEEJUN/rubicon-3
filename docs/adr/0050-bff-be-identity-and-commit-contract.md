# ADR-0050: BFF↔BE 신원 계약 + 게스트(비로그인) + 커밋 왕복

- **상태**: 채택
- **관련**: ADR-0049(멀티테넌트·커밋 계약), `specs/multi-tenant-state/`, `docs/api-contract.md` §2·§3, `bff/gateway/`, `frontend/src/`

## 배경
BE에 멀티테넌트(Principal·게스트)·예약 게이트가 들어갔으나, FE/BFF가 옛 단일 사용자 가정에 머물러 **통합이 끊겼다**: ① BFF가 토큰을 인증해놓고 신원을 BE로 안 넘김(WS payload·HTTP 헤더 누락), ② BE 커밋 게이트는 `X-User-Id` 헤더를 보는데 BFF는 body로 `user_id`를 보냄(불일치 → 인증 사용자가 게스트로 401), ③ BFF가 무토큰을 전면 401로 막아 비로그인 흐름이 도달 불가. 본 ADR이 세 계층의 **신원·게스트·커밋 왕복 계약**을 고정한다.

## 결정 (계약)

### 1. 신원 전달
- **HTTP**: BFF는 모든 BE 호출에 헤더 `X-User-Id`(로그인) 또는 `X-Guest-Token`(게스트)를 싣는다. BE는 이 헤더로 Principal을 해석한다. 턴 엔드포인트는 body `user_id`/`guest_token`(TurnRequest)도 폴백으로 인정.
- **WS**: 브라우저 WS는 헤더를 못 보내므로, BFF가 BE `/internal/turn`으로 포워딩하는 JSON에 `user_id`/`guest_token` 필드를 **주입**한다(BE는 `msg.get(...)`로 읽음).
- **커밋 게이트 해석 우선순위**(BE): `X-User-Id` > `X-Guest-Token` > body `user_id`. 셋 다 로그인 사용자를 가리키지 않고 `MULTITENANT` on이면 게스트.

### 2. 게스트(비로그인)
- BFF는 무토큰 요청을 **차단하지 않는다**. 게스트 토큰(쿼리 `?guest_token=`·쿠키, 없으면 발급)을 써서 조언형 턴을 허용하고 `X-Guest-Token`/payload로 전달.
- **커밋(주문·예약)** 은 BE가 게스트에게 `401 {code:"LoginRequired", cta:{kind:"login"}}` → BFF가 그대로 중계 → FE가 로그인 월.

### 3. 커밋 왕복(CTA→ActionGate)
- 주문·예약 commit CTA(`action:"commit"`, `kind`∈{order,booking})는 **REST 커밋 엔드포인트**로 간다(WS 텍스트 변환 아님).
- 미확인 → `409 {code:"ConfirmationRequired", template:{kind:"confirmation"}}`(주문·예약 동형) → 클라이언트가 `confirmed:true`로 재요청.

### 4. 응답 표현(FE 신규 지원)
- CTA kind: `login`·`select_device`·`booking`(commit)·`restock_alert`·`compare`·`explain`.
- 템플릿 kind: `booking`(방문 슬롯 리스트).
- `handled=false` 섹션은 FE가 **구분 렌더**(R7 — "못 도와드림"을 침묵시키지 않음).

### 5. 토글 호환
- BE `MULTITENANT` off → 기본 사용자(회귀). BFF/FE는 BE 토글 on·off 양쪽에서 동작해야 한다.

## 영향
- BFF: `auth.py`(게스트 해석)·`main.py`/`backend_client.py`(헤더·WS payload 신원 주입·401/409 중계).
- BE: `internal.py` 커밋 게이트 헤더+body 정합, 턴 헤더 수용.
- FE: `contract.ts`(신규 kind)·`message.tsx`(booking·unhandled 렌더)·커밋 409/401 왕복·로그인 월·레이턴시 인디케이터·analytics emit(최소).

## 후속
- analytics 싱크(BFF/BE 수신) · 게스트→로그인 머지(ADR-0049 §3) · 실 SSO 인증(현재 Mock 토큰).
