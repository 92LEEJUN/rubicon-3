"""BE 도메인 **내부 API**(BFF 전용) — api-contract.md §2.4.

- WS  /internal/turn         : 자연어 → 오케스트레이터 섹션 스트림(§2.1 봉투)
- POST /internal/surface     : 카드 탭 → bridge/panel 결정(§2.3)
- GET  /internal/devices…    : 결정적 조회(§2.2)
- POST /internal/orders      : 커밋 게이트(R17) — 미확인 시 409 ConfirmationRequired
- GET/POST /internal/bookings: 방문 슬롯·예약(R18)
- GET  /internal/home        : home_summary aggregation(R9-2)

인증·세션은 BFF가 처리(§2.4) — 내부망 전제. 여기서는 검증된 컨텍스트를 신뢰한다.
"""
from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..container import build_container
from ..domain import Template
from ..errors import ConfirmationRequired
from ..orchestrator import Orchestrator

app = FastAPI(title="MVP 컨시어지 — BE 내부 API")

# MVP: 단일 컨테이너(인메모리 상태). 실 전환 시 세션/사용자별로 분리.
_container = build_container()
_orch = Orchestrator(container=_container)


# ── 요청 모델 ────────────────────────────────────────────────────────────────
class OrderRequest(BaseModel):
    user_id: str = "usr_01"
    part_ids: list[str]
    confirmed: bool = False


class BookingRequest(BaseModel):
    slot_id: str
    context_ref: str | None = None


class SurfaceRequest(BaseModel):
    card_type: str
    ref: str | None = None
    screen_context: dict | None = None


# ── 대화(WS) — 섹션 스트림 ──────────────────────────────────────────────────
@app.websocket("/internal/turn")
async def turn(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            text = msg.get("text", "")
            for chunk in _orch.stream_turn(text, msg.get("screen_context")):
                await ws.send_json(chunk)
    except WebSocketDisconnect:
        return


# ── 결정적 조회(HTTP) ────────────────────────────────────────────────────────
@app.get("/internal/devices")
def list_devices():
    return [d.model_dump(mode="json") for d in _container.device.list_devices()]


@app.get("/internal/devices/{device_id}")
def get_device(device_id: str):
    res = _container.device.get_status(device_id)
    if not res.found:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": res.message})
    return res.model_dump(mode="json")


@app.get("/internal/home")
def home_summary():
    """홈 aggregation — 기기 + 선제 알림(동의/중복 게이트 통과분)."""
    user = _container.user
    alerts = _container.notification.pending_alerts(user)
    return Template(kind="home_summary", data={
        "user": user.display_name,
        "devices": [d.model_dump(mode="json") for d in _container.device.list_devices()],
        "alerts": [a.model_dump(mode="json") for a in alerts],
    }).model_dump(mode="json")


@app.get("/internal/catalog/recommend")
def recommend():
    products = _container.catalog.recommend(_container.user)
    return [p.model_dump(mode="json") for p in products]


# ── 커밋(HTTP) — 주문 게이트(R17) ───────────────────────────────────────────
@app.post("/internal/orders")
def place_order(req: OrderRequest):
    try:
        order = _container.order.checkout(req.user_id, req.part_ids, confirmed=req.confirmed)
    except ConfirmationRequired as gate:
        # 409 + confirmation 템플릿(확인용 DRAFT·금액 분해 동봉)
        return JSONResponse(status_code=409, content={
            "code": "ConfirmationRequired",
            "message": gate.message,
            "template": Template(kind="confirmation", data={
                "order": gate.draft.model_dump(mode="json"),
                "summary": gate.draft.summary.model_dump(mode="json"),
            }).model_dump(mode="json"),
        })
    return order.model_dump(mode="json")


# ── 핸드오프/예약(HTTP) — R18 ────────────────────────────────────────────────
@app.get("/internal/bookings/slots")
def booking_slots(visit_type: str = "REPAIR"):
    return [s.model_dump(mode="json") for s in _container.handoff.list_slots(visit_type)]


@app.post("/internal/bookings")
def create_booking(req: BookingRequest):
    return _container.handoff.book(req.slot_id, req.context_ref).model_dump(mode="json")


# ── 카드 탭 — surface 결정(§2.3) ────────────────────────────────────────────
@app.post("/internal/surface")
def surface(req: SurfaceRequest):
    """간단(상태·소모품 알림)=bridge(S4), 복잡=panel(S3)."""
    simple = req.card_type in ("alert", "consumable", "device_status")
    if simple:
        status = _container.device.get_status(req.ref or "")
        body = status.model_dump(mode="json") if status.found else {"message": "기기 정보를 찾지 못했습니다."}
        return {"surface": "bridge",
                "template": Template(kind="bridge", data={"summary": body}).model_dump(mode="json")}
    return {"surface": "panel", "conversation_id": f"conv_{req.ref or 'new'}"}
