"""BFF FastAPI 앱 — 클라이언트 표면(api-contract §2). FE는 이 서비스만 본다.

WS /chat(섹션 스트림 중계) · 결정적 HTTP(/devices·/home·/orders·/bookings·/surface).
BE 도메인 내부 API를 BackendClient(async)로 호출하고, 인증 게이트·폴백 정형화를 더한다.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect

from .auth import require_auth, ws_user
from .backend_client import BackendClient
from .transform import fallback_body, interaction_to_text, relay


def _backend(request: Request) -> BackendClient:
    return request.app.state.backend


def create_app(backend: Optional[BackendClient] = None) -> FastAPI:
    app = FastAPI(title="MVP 컨시어지 — BFF (클라이언트 표면)")
    app.state.backend = backend or BackendClient()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # ── 결정적 조회(§2.2) — 인증 게이트 ────────────────────────────────────
    @app.get("/devices")
    async def list_devices(user: str = Depends(require_auth), be: BackendClient = Depends(_backend)):
        return await relay(be.list_devices)

    @app.get("/devices/{device_id}")
    async def get_device(device_id: str, user: str = Depends(require_auth),
                         be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.get_device(device_id))

    @app.get("/home")
    async def home(user: str = Depends(require_auth), be: BackendClient = Depends(_backend)):
        return await relay(be.home)

    @app.get("/catalog/recommend")
    async def recommend(user: str = Depends(require_auth), be: BackendClient = Depends(_backend)):
        return await relay(be.recommend)

    # ── 커밋(§2.2) — 주문 게이트(R17) 그대로 중계(409 포함) ─────────────────
    @app.post("/orders")
    async def place_order(request: Request, user: str = Depends(require_auth),
                          be: BackendClient = Depends(_backend)):
        body = await request.json()
        body.setdefault("user_id", user)
        return await relay(lambda: be.place_order(body))

    @app.get("/orders")
    async def list_orders(user: str = Depends(require_auth), be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.list_orders(user))

    @app.get("/bookings")
    async def list_bookings(user: str = Depends(require_auth), be: BackendClient = Depends(_backend)):
        return await relay(be.list_bookings)

    # ── 예약(§2.2, R18) ─────────────────────────────────────────────────────
    @app.get("/bookings/slots")
    async def booking_slots(visit_type: str = "REPAIR", user: str = Depends(require_auth),
                            be: BackendClient = Depends(_backend)):
        return await relay(lambda: be.booking_slots(visit_type))

    @app.post("/bookings")
    async def create_booking(request: Request, user: str = Depends(require_auth),
                             be: BackendClient = Depends(_backend)):
        body = await request.json()
        return await relay(lambda: be.create_booking(body))

    # ── 카드 탭 surface(§2.3) ───────────────────────────────────────────────
    @app.post("/surface")
    async def surface(request: Request, user: str = Depends(require_auth),
                      be: BackendClient = Depends(_backend)):
        body = await request.json()
        return await relay(lambda: be.surface(body))

    # ── 대화 WS(§2.1) — BE 섹션 스트림 중계 ────────────────────────────────
    @app.websocket("/chat")
    async def chat(ws: WebSocket):
        await ws.accept()
        # 브라우저 WebSocket은 헤더를 못 보내므로 쿼리 토큰(?token=)도 허용(api-contract §3).
        token = ws.headers.get("authorization") or ws.query_params.get("token")
        if ws_user(token) is None:
            await ws.send_json({"type": "error", "code": "unauthorized",
                                "fallback": {"kind": "text", "data": {"message": "인증이 필요합니다."}}})
            await ws.close()
            return
        be: BackendClient = ws.app.state.backend
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") not in ("user_message", "interaction_reply"):
                    await ws.send_json({"type": "error", "code": "bad_request"})
                    continue
                text = msg.get("text") if msg.get("type") == "user_message" else interaction_to_text(msg)
                payload = {"session_id": msg.get("session_id", "s1"),
                           "text": text or "", "screen_context": msg.get("screen_context")}
                # 증분 포워딩 — 청크를 모으지 않고 도착 즉시 중계(operations §9).
                sent_any = False
                try:
                    async for chunk in be.turn_stream(payload):
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
