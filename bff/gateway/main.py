"""BFF FastAPI 앱 — 클라이언트 표면(api-contract §2). FE는 이 서비스만 본다.

WS /chat(섹션 스트림 중계) · 결정적 HTTP(/devices·/home·/orders·/bookings·/surface).
BE 도메인 내부 API를 BackendClient(async)로 호출하고, 신원 포워딩·폴백 정형화를 더한다.

신원 포워딩(멀티테넌트, 공유 계약):
- 로그인/게스트 신원을 `identity_dep`로 해석하고, 모든 BE HTTP 호출에 신원 헤더
  (X-User-Id | X-Guest-Token)를 싣는다. WS /chat은 payload에 user_id·guest_token을 주입한다.
- 게스트(비로그인)도 자문·대화 턴은 허용한다. 커밋(주문/예약)은 BFF에서 막지 않는다 —
  게스트 커밋이면 BE가 401 {code:"LoginRequired", cta:{kind:"login"}}을 돌려주고 그대로 중계.
- BE가 미확인 커밋에 409 {code:"ConfirmationRequired"}를 돌려주면(주문·예약 모두) 그대로 중계.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect

from .auth import Identity, identity_dep, resolve_identity
from .backend_client import BackendClient
from .observability import install_observability
from .transform import fallback_body, interaction_to_text, relay


def _backend(request: Request) -> BackendClient:
    return request.app.state.backend


def create_app(backend: Optional[BackendClient] = None) -> FastAPI:
    app = FastAPI(title="MVP 컨시어지 — BFF (클라이언트 표면)")
    app.state.backend = backend or BackendClient()

    # 관측성(gap 8) — /metrics + 요청/에러 카운트 미들웨어(stdlib only, 중계/스트림 불변).
    # /health 는 아래에 이미 있으므로 add_health=False.
    install_observability(app, service="bff", add_health=False)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # ── 결정적 조회(§2.2) — 신원 해석(로그인/게스트) 후 헤더 포워딩 ──────────
    @app.get("/devices")
    async def list_devices(idy: Identity = Depends(identity_dep),
                           be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.list_devices(headers=idy.headers()))

    @app.get("/devices/{device_id}")
    async def get_device(device_id: str, idy: Identity = Depends(identity_dep),
                         be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.get_device(device_id, headers=idy.headers()))

    @app.get("/home")
    async def home(idy: Identity = Depends(identity_dep), be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.home(headers=idy.headers()))

    @app.get("/catalog/recommend")
    async def recommend(idy: Identity = Depends(identity_dep),
                        be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.recommend(headers=idy.headers()))

    # ── 커밋(§2.2) — BFF는 막지 않음. BE의 401(LoginRequired)/409(ConfirmationRequired)
    #    를 상태코드·본문 그대로 중계(relay가 status+body 패스스루) ───────────
    @app.post("/orders")
    async def place_order(request: Request, idy: Identity = Depends(identity_dep),
                          be: BackendClient = Depends(_backend)):
        body = await request.json()
        if idy.user_id:
            body.setdefault("user_id", idy.user_id)
        return await relay(lambda: be.place_order(body, headers=idy.headers()))

    @app.get("/orders")
    async def list_orders(idy: Identity = Depends(identity_dep),
                          be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.list_orders(idy.user_id, headers=idy.headers()))

    @app.get("/orders/{order_id}")
    async def get_order(order_id: str, idy: Identity = Depends(identity_dep),
                        be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.get_order(order_id, headers=idy.headers()))

    # ── O2O 픽업 상태 전이(§2.2, O3·O4) — 역전이 409 그대로 중계 ────────────
    @app.post("/orders/{order_id}/pickup")
    async def advance_pickup(order_id: str, request: Request,
                             idy: Identity = Depends(identity_dep),
                             be: BackendClient = Depends(_backend)):
        body = await request.json()
        return await relay(lambda: be.advance_pickup(order_id, body, headers=idy.headers()))

    # ── O2O 거점·재고(§2.2, O1·O2) ──────────────────────────────────────────
    @app.get("/stores")
    async def list_stores(request: Request, idy: Identity = Depends(identity_dep),
                          be: BackendClient = Depends(_backend)):
        params = dict(request.query_params)
        params.pop("guest_token", None)  # 신원 토큰은 BE 쿼리로 새지 않게 제거
        return await relay(lambda: be.list_stores(params or None, headers=idy.headers()))

    @app.get("/stores/{store_id}/stock/{part_id}")
    async def check_stock(store_id: str, part_id: str, idy: Identity = Depends(identity_dep),
                          be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.check_stock(store_id, part_id, headers=idy.headers()))

    # ── O2O 견적 이어보기/전환(§2.2, O5·O6) — 403/410/409 그대로 중계 ───────
    @app.get("/quotes/{quote_ref}")
    async def get_quote(quote_ref: str, idy: Identity = Depends(identity_dep),
                        be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.get_quote(quote_ref, idy.user_id, headers=idy.headers()))

    @app.post("/quotes/{quote_ref}/convert")
    async def convert_quote(quote_ref: str, request: Request,
                            idy: Identity = Depends(identity_dep),
                            be: BackendClient = Depends(_backend)):
        body = await request.json()
        if idy.user_id:
            body.setdefault("user_id", idy.user_id)
        return await relay(lambda: be.convert_quote(quote_ref, body, headers=idy.headers()))

    @app.get("/bookings")
    async def list_bookings(idy: Identity = Depends(identity_dep),
                            be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.list_bookings(headers=idy.headers()))

    # ── 예약(§2.2, R18) — 미확인 시 BE 409(ConfirmationRequired) 그대로 중계 ─
    @app.get("/bookings/slots")
    async def booking_slots(visit_type: str = "REPAIR",
                            idy: Identity = Depends(identity_dep),
                            be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.booking_slots(visit_type, headers=idy.headers()))

    @app.post("/bookings")
    async def create_booking(request: Request, idy: Identity = Depends(identity_dep),
                             be: BackendClient = Depends(_backend)):
        body = await request.json()
        return await relay(lambda: be.create_booking(body, headers=idy.headers()))

    # ── 이어가기(컴패니언 §1) — 패널 열기 시 복원 맥락 ──────────────────────
    @app.get("/resume")
    async def resume(fresh: bool = False, idy: Identity = Depends(identity_dep),
                     be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.resume(fresh, headers=idy.headers()))

    @app.get("/reengagement")
    async def reengagement(idy: Identity = Depends(identity_dep),
                           be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.reengagement(headers=idy.headers()))

    @app.get("/recommendations")
    async def recommendations(idy: Identity = Depends(identity_dep),
                              be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.recommendations(headers=idy.headers()))

    @app.post("/reengagement/deliver")
    async def reengagement_deliver(idy: Identity = Depends(identity_dep),
                                   be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.reengagement_deliver(headers=idy.headers()))

    @app.post("/open-loops/{ref}/{action}")
    async def resolve_open_loop(ref: str, action: str, idy: Identity = Depends(identity_dep),
                                be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.resolve_open_loop(ref, action, headers=idy.headers()))

    # ── 카드 탭 surface(§2.3) ───────────────────────────────────────────────
    @app.post("/surface")
    async def surface(request: Request, idy: Identity = Depends(identity_dep),
                      be: BackendClient = Depends(_backend)):
        body = await request.json()
        return await relay(lambda: be.surface(body, headers=idy.headers()))

    # ── 대화 WS(§2.1) — BE 섹션 스트림 중계 ────────────────────────────────
    @app.websocket("/chat")
    async def chat(ws: WebSocket):
        await ws.accept()
        # 브라우저 WebSocket은 헤더를 못 보내므로 쿼리 토큰(?token=)도 허용(api-contract §3).
        # 토큰 없음 → 게스트(비로그인). 게스트 토큰은 ?guest_token= 로 받거나 새로 발급한다.
        token = ws.headers.get("authorization") or ws.query_params.get("token")
        guest_token = ws.query_params.get("guest_token")
        idy = resolve_identity(token, guest_token)
        be: BackendClient = ws.app.state.backend
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") not in ("user_message", "interaction_reply"):
                    await ws.send_json({"type": "error", "code": "bad_request"})
                    continue
                # ⑥ 커밋 CTA 스코핑: interaction_reply 중 commit-kind(order|booking)는
                # FE가 REST 커밋 엔드포인트(/orders·/bookings)를 직접 호출한다(FE 에이전트 담당).
                # WS 경로에서는 새 커밋 채널을 만들지 않고, 비커밋 회신은 기존 텍스트-폴백으로
                # 다음 턴 입력으로 변환해 흘려보낸다. 신원은 아래 payload로 포워딩된다.
                text = msg.get("text") if msg.get("type") == "user_message" else interaction_to_text(msg)
                # 신원 주입(user_id·guest_token) — BE /internal/turn WS 계약(msg.get(...)).
                payload = {"session_id": msg.get("session_id", "s1"),
                           "text": text or "", "screen_context": msg.get("screen_context"),
                           **idy.ws_fields()}
                # 증분 포워딩 — 청크를 모으지 않고 도착 즉시 중계(operations §9).
                # BE HTTP turn은 body로 신원을 읽고, 헤더도 함께 실어 일관성을 유지한다.
                sent_any = False
                try:
                    async for chunk in be.turn_stream(payload, headers=idy.headers()):
                        await ws.send_json(chunk)
                        sent_any = True
                except Exception:
                    if sent_any:
                        # 부분 전송 후 실패는 되돌릴 수 없으니 에러로 마감(operations §8).
                        await ws.send_json({"type": "error", **fallback_body(
                            "응답 생성 중 문제가 발생했어요. 다시 시도해 주세요.", "stream_interrupted")})
                    else:
                        await ws.send_json({"type": "error", **fallback_body()})
                    continue
        except WebSocketDisconnect:
            return

    return app


app = create_app()
