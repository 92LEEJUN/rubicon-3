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

import json
import os
from pathlib import Path
from typing import AsyncIterator

try:  # backend/.env 자동 로드(있으면) — OPENAI_API_KEY·LLM_BACKED 등.
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ModuleNotFoundError:
    pass

from fastapi import FastAPI, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..container import build_container
from ..domain import Template
from ..errors import (
    ConfirmationRequired,
    OutOfStock,
    PickupTransitionError,
    QuoteExpired,
    QuoteForbidden,
    QuoteNotConvertible,
)
from ..orchestrator.capability import CapabilityOrchestrator
from ..principal import (
    Principal,
    UserDirectory,
    multitenant_enabled,
    resolve_principal,
)

app = FastAPI(title="MVP 컨시어지 — BE 내부 API")

# 공유 컨테이너 — 인메모리 상태 리포는 **이미 user_id 키잉**(멀티테넌트 준비됨, specs/multi-tenant-state).
# 단일 지점이던 `_container.user`(프로필)는 Principal/UserDirectory로 분리한다.
_container = build_container()
_users = UserDirectory()
# 결정적 경로(LLM off) = capability 오케스트레이터(플래너 없음). 옛 core.Orchestrator를
# 여기로 수렴(스트랭글러 §12.3) — 봉투 동일 + ADR-0046 수리 CTA 게이팅 포함.
_orch = CapabilityOrchestrator(container=_container, llm_planner=None)


def _principal(user_id: str | None = None, guest_token: str | None = None) -> Principal:
    """요청 신원 → Principal(토글 off거나 신원 없으면 폴백, specs/multi-tenant-state)."""
    return resolve_principal(user_id, guest_token)


def _resolve_commit_identity(
    x_user_id: str | None,
    x_guest_token: str | None,
    body_user_id: str | None = None,
    body_guest_token: str | None = None,
) -> tuple[str | None, str | None]:
    """커밋 신원 해석 — 헤더 우선, 본문 폴백(gap ②).

    우선순위: 헤더 `X-User-Id` > 헤더 `X-Guest-Token` > 본문 `user_id` > 본문 `guest_token`.
    BFF는 HTTP 호출에 헤더를 싣지만, 본문 `user_id`로 신원을 중계하기도 한다(TurnRequest·OrderRequest).
    어느 쪽이든 일관되게 받는다. `body_user_id`는 **명시적으로 제공된 경우에만** 넘겨야 한다
    (OrderRequest.user_id 기본값 "usr_01"을 로그인으로 오인하지 않도록 — place_order 참조).
    """
    user_id = x_user_id or body_user_id
    guest_token = x_guest_token or body_guest_token
    return user_id or None, guest_token or None


def _guest_commit_gate(x_user_id: str | None, x_guest_token: str | None,
                       body_user_id: str | None = None,
                       body_guest_token: str | None = None):
    """게스트(비로그인) 커밋 차단(요구사항 2-3). 토글 off면 게이트 없음(회귀).

    신원은 헤더 우선·본문 폴백으로 해석한다(gap ② — BFF가 본문 user_id로 중계하는 경우 포함).
    """
    if not multitenant_enabled():
        return None
    user_id, guest_token = _resolve_commit_identity(
        x_user_id, x_guest_token, body_user_id, body_guest_token)
    if _principal(user_id, guest_token).is_guest:
        return JSONResponse(status_code=401, content={
            "code": "LoginRequired",
            "message": "주문·예약은 로그인 후 확정할 수 있어요.",
            "template": Template(kind="text", data={
                "message": "로그인하면 진행할 수 있어요. 지금까지 담은 내용은 로그인 후 이어집니다."}).model_dump(mode="json"),
            "cta": {"label": "로그인", "action": "navigate", "kind": "login"},
        })
    return None


def _llm_backed() -> bool:
    """LLM 자연어 경로 사용 여부 — 매 호출 평가(런타임 env·.env 모두 반영)."""
    return os.getenv("LLM_BACKED", "").strip().lower() in ("1", "true", "yes", "on")


def _multiagent() -> bool:
    """멀티에이전트 경로 토글 — LLM_BACKED 위에서 동작(매 호출 평가, 기본 off)."""
    return os.getenv("MULTIAGENT", "").strip().lower() in ("1", "true", "yes", "on")


def _capability_orch() -> bool:
    """capability 오케스트레이터 경로 토글(§9.2) — 매 호출 평가, 기본 off.

    on이면 결정적/멀티에이전트 경로 대신 CapabilityOrchestrator.astream으로 라우팅한다.
    LLM_BACKED on이면 LLM 플래너(apropose)로, off면 규칙 폴백으로 동작한다."""
    return os.getenv("CAPABILITY_ORCH", "").strip().lower() in ("1", "true", "yes", "on")


# 모듈 로드 시 1회 구성(_orch와 동일 패턴). LLM_BACKED 평가는 _stream_turn에서 매 호출.
def _build_cap_orch():
    from ..orchestrator.capability import CapabilityOrchestrator
    from ..orchestrator.planner import LLMPlanner
    planner = LLMPlanner() if _llm_backed() else None
    return CapabilityOrchestrator(container=_container, llm_planner=planner)


_cap_orch = None   # 첫 CAPABILITY_ORCH 요청 시 lazy 구성(LLM_BACKED 토글 반영)


async def _stream_turn(text: str, screen_context: dict | None,
                       principal: Principal | None = None) -> AsyncIterator[dict]:
    """턴 스트림 디스패치(비동기):
    ⓪ CAPABILITY_ORCH on → CapabilityOrchestrator.astream(LLM-planner 라우팅, §9.2)
    ① LLM_BACKED off → 결정적 섹션(CapabilityOrchestrator, 플래너 없음 — core 수렴 §12.3)
    ② LLM_BACKED on, MULTIAGENT off → 단일 tool-loop(legacy, LLM 자연어 prose)
    ③ LLM_BACKED on, MULTIAGENT on → 슈퍼바이저-워커(runtime, LLM 자연어 prose).

    ②③(LLM prose)는 capability에 LLM agent capability(§8~11)가 생기기 전까지 유지한다."""
    principal = principal or _principal()
    user = _users.get(principal)
    if _capability_orch():
        global _cap_orch
        if _cap_orch is None:
            _cap_orch = _build_cap_orch()
        async for chunk in _cap_orch.astream(text, screen_context=screen_context, user=user):
            yield chunk
    elif _llm_backed():
        memory = _container.companion.context(principal.id)  # 이어가기 주입(§0.4·사용자별)
        if _multiagent():
            from ..orchestrator.runtime import astream_multiagent
            async for chunk in astream_multiagent(text, screen_context, memory=memory):
                yield chunk
        else:
            from ..orchestrator.legacy import astream_turn as _llm_astream
            async for chunk in _llm_astream(text, screen_context, memory=memory):
                yield chunk
    else:
        for chunk in _orch.stream_turn(text, screen_context=screen_context, user=user):
            yield chunk


def _collect_assistant(chunk: dict, parts: list[str]) -> None:
    """스트림 청크에서 어시스턴트 텍스트를 모은다(컴팩션 기록용)."""
    t = chunk.get("type")
    if t == "delta":
        parts.append(chunk.get("text", ""))
    elif t == "section":
        label = (chunk.get("section") or {}).get("label")
        if label:
            parts.append(f"[{label}]")  # 상세 추출은 컴패니언 §0.3


async def _stream_and_record(text: str, screen_context: dict | None,
                             principal: Principal | None = None) -> AsyncIterator[dict]:
    """턴 스트림 + 종료 후 컴팩션 기록(turn 루프 배선, tasks §0.4). 기록 실패는 무시(비차단)."""
    principal = principal or _principal()
    parts: list[str] = []
    async for chunk in _stream_turn(text, screen_context, principal):
        _collect_assistant(chunk, parts)
        yield chunk
    try:
        _container.companion.record_turn(principal.id, text, " ".join(p for p in parts if p))
    except Exception:
        pass


# ── 요청 모델 ────────────────────────────────────────────────────────────────
class TurnRequest(BaseModel):
    session_id: str = "s1"
    text: str
    media: list = []
    screen_context: dict | None = None
    user_id: str | None = None       # 신원(멀티테넌트) — 없으면 게스트/기본 폴백
    guest_token: str | None = None


class OrderRequest(BaseModel):
    user_id: str = "usr_01"
    part_ids: list[str]
    confirmed: bool = False
    # O2O — 픽업(BOPIS) 이행 방식·픽업 매장(O3). delivery면 store_id 무시.
    fulfillment: str = "delivery"
    store_id: str | None = None
    guest_token: str | None = None   # 본문 신원 폴백(gap ②) — 헤더 없을 때 게스트 식별


class BookingRequest(BaseModel):
    slot_id: str
    context_ref: str | None = None
    # O2O — 센터/매장 방문(O7). visit_type=center·store_id로 거점 동반.
    visit_type: str = "REPAIR"
    store_id: str | None = None
    confirmed: bool = False   # R17 커밋 게이트 — 미확인이면 409(주문과 동일)
    user_id: str | None = None     # 본문 신원 폴백(gap ②) — 헤더 없을 때 로그인 식별
    guest_token: str | None = None


class PickupActionRequest(BaseModel):
    action: str  # "ready" | "picked_up" | "expired"


class ConvertRequest(BaseModel):
    user_id: str = "usr_01"
    confirmed: bool = False
    fulfillment: str = "delivery"
    store_id: str | None = None


class SurfaceRequest(BaseModel):
    card_type: str
    ref: str | None = None
    screen_context: dict | None = None


# ── 대화(WS) — 섹션 스트림 ──────────────────────────────────────────────────
@app.websocket("/internal/turn")
async def turn_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()   # 핸드셰이크/메시지가 신원 운반(user_id·guest_token)
            text = msg.get("text", "")
            principal = _principal(msg.get("user_id"), msg.get("guest_token"))
            async for chunk in _stream_and_record(text, msg.get("screen_context"), principal):
                await ws.send_json(chunk)
    except WebSocketDisconnect:
        return


@app.post("/internal/turn")
def turn_http(req: TurnRequest, x_user_id: str | None = Header(None),
              x_guest_token: str | None = Header(None)) -> StreamingResponse:
    """BFF 중계용 HTTP 스트림(NDJSON) — 한 줄당 청크 1개(§2.1 봉투). 비동기 제너레이터로
    스트리밍(이벤트 루프 비차단 — 스레드-당-턴 점유 제거).

    신원은 헤더 우선·본문 폴백(gap ②) — BFF가 헤더(X-User-Id/X-Guest-Token)를 싣는 경우 지원."""
    user_id, guest_token = _resolve_commit_identity(
        x_user_id, x_guest_token, req.user_id, req.guest_token)
    principal = _principal(user_id, guest_token)
    async def gen():
        async for chunk in _stream_and_record(req.text, req.screen_context, principal):
            yield json.dumps(chunk, ensure_ascii=False) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.get("/internal/resume")
def resume(fresh: bool = False, x_user_id: str | None = Header(None),
           x_guest_token: str | None = Header(None)):
    """이어가기(컴패니언 §1) — 영속 메모리·상대 시간 복원. fresh면 '새로 시작'."""
    principal = _principal(x_user_id, x_guest_token)
    return _container.companion.resume(principal.id, fresh=fresh).model_dump(mode="json")


@app.get("/internal/reengagement")
def reengagement(x_user_id: str | None = Header(None),
                 x_guest_token: str | None = Header(None)):
    """선제 재관여(컴패니언 §3) — 엄격 게이트 통과분 1건(peek). 없으면 {}."""
    user = _users.get(_principal(x_user_id, x_guest_token))
    cand = _container.reengagement.candidate(user)
    return cand.model_dump(mode="json") if cand else {}


@app.post("/internal/reengagement/deliver")
def reengagement_deliver(x_user_id: str | None = Header(None),
                         x_guest_token: str | None = Header(None)):
    """전달 액션(§3.3) — 게이트 통과분을 전달 처리하고 mark_sent(빈도·중복 갱신). 없으면 {}.

    실 채널은 AlertPort(§10); 여기서는 전달 확정 + 재노출 억제를 담당한다.
    """
    user = _users.get(_principal(x_user_id, x_guest_token))
    cand = _container.reengagement.candidate(user)
    if not cand:
        return {}
    _container.reengagement.mark_sent(user)
    return cand.model_dump(mode="json")


@app.get("/internal/recommendations")
def recommendations(x_user_id: str | None = Header(None),
                    x_guest_token: str | None = Header(None)):
    """반응형 추천(컴패니언·비전 2) — 추천 코어 산출(개인화·동의 차등). recommendation_list 매핑용."""
    user = _users.get(_principal(x_user_id, x_guest_token))
    items = _container.recommendation.recommend(user)
    return {"items": [it.model_dump(mode="json") for it in items]}


@app.post("/internal/recommendations/preemptive")
def recommendations_preemptive(x_user_id: str | None = Header(None),
                               x_guest_token: str | None = Header(None)):
    """선제 추천 등록 — 트리거를 open-loop로 적재(전달은 컴패니언 게이트가 규율, ADR-0042)."""
    user = _users.get(_principal(x_user_id, x_guest_token))
    n = _container.recommendation.enqueue_preemptive(user, _container.companion)
    return {"enqueued": n}


@app.post("/internal/open-loops/{ref}/resolve")
def resolve_open_loop(ref: str, x_user_id: str | None = Header(None),
                      x_guest_token: str | None = Header(None)):
    """미해결 스레드 해소(§2.3) — R25 해결확인·주문 배송완료 등."""
    principal = _principal(x_user_id, x_guest_token)
    loop = _container.companion.resolve_loop(principal.id, ref)
    if loop is None:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "open-loop 없음"})
    return loop.model_dump(mode="json")


@app.post("/internal/open-loops/{ref}/dismiss")
def dismiss_open_loop(ref: str, x_user_id: str | None = Header(None),
                      x_guest_token: str | None = Header(None)):
    """미해결 스레드 닫기(§2.3) — 사용자 dismiss."""
    principal = _principal(x_user_id, x_guest_token)
    loop = _container.companion.dismiss_loop(principal.id, ref)
    if loop is None:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "open-loop 없음"})
    return loop.model_dump(mode="json")


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
def home_summary(x_user_id: str | None = Header(None),
                 x_guest_token: str | None = Header(None)):
    """홈 aggregation — 기기 + 선제 알림 + 개인화 추천(동의/중복 게이트 통과분)."""
    user = _users.get(_principal(x_user_id, x_guest_token))
    alerts = _container.notification.pending_alerts(user)
    recs = _container.catalog.recommend(user)
    return Template(kind="home_summary", data={
        "user": user.display_name,
        "devices": [d.model_dump(mode="json") for d in _container.device.list_devices()],
        "alerts": [a.model_dump(mode="json") for a in alerts],
        "recommendations": [p.model_dump(mode="json") for p in recs],
    }).model_dump(mode="json")


@app.get("/internal/catalog/recommend")
def recommend(x_user_id: str | None = Header(None),
              x_guest_token: str | None = Header(None)):
    user = _users.get(_principal(x_user_id, x_guest_token))
    products = _container.catalog.recommend(user)
    return [p.model_dump(mode="json") for p in products]


# ── 이력 조회(HTTP) — 주문/예약 진행(R12·R18) ───────────────────────────────
@app.get("/internal/orders")
def list_orders(user_id: str | None = None):
    """주문 이력(최신순) — 진행 추적/홈·CS 노출용."""
    return [o.model_dump(mode="json") for o in _container.order.history(user_id)]


@app.get("/internal/bookings")
def list_bookings():
    """예약 이력 — 홈/CS '진행 중' 노출용."""
    return [b.model_dump(mode="json") for b in _container.handoff.list_bookings()]


def _confirmation_409(gate: ConfirmationRequired) -> JSONResponse:
    """409 + confirmation 템플릿(확인용 DRAFT·금액 분해 동봉, R17)."""
    return JSONResponse(status_code=409, content={
        "code": "ConfirmationRequired",
        "message": gate.message,
        "template": Template(kind="confirmation", data={
            "order": gate.draft.model_dump(mode="json"),
            "summary": gate.draft.summary.model_dump(mode="json"),
        }).model_dump(mode="json"),
    })


def _out_of_stock_409(err: OutOfStock) -> JSONResponse:
    """409 — 재고 없음. 대체 매장/배송 제안(O2-2·O2-3·O4-3)."""
    alts = _container.store.stores_with_stock(err.part_id)
    return JSONResponse(status_code=409, content={
        "code": "OutOfStock",
        "message": err.message,
        "store_id": err.store_id,
        "part_id": err.part_id,
        "alternatives": [s.model_dump(mode="json") for s in alts],  # 재고 있는 대체 매장
        "delivery_available": True,                                  # 배송 전환 가능
    })


# ── 커밋(HTTP) — 주문 게이트(R17) ───────────────────────────────────────────
@app.post("/internal/orders")
def place_order(req: OrderRequest, x_user_id: str | None = Header(None),
                x_guest_token: str | None = Header(None)):
    # 본문 user_id는 **명시적으로 보낸 경우만** 신원으로 인정한다(기본값 "usr_01"을 로그인으로 오인 방지).
    body_user_id = req.user_id if "user_id" in req.model_fields_set else None
    gate = _guest_commit_gate(x_user_id, x_guest_token,   # 게스트 커밋 차단(요구사항 2-3, gap ②)
                              body_user_id, req.guest_token)
    if gate is not None:
        return gate
    try:
        if req.fulfillment == "pickup":
            order = _container.order.checkout_pickup(
                req.user_id, req.part_ids, req.store_id or "", confirmed=req.confirmed)
        else:
            order = _container.order.checkout(req.user_id, req.part_ids, confirmed=req.confirmed)
    except ConfirmationRequired as gate:
        return _confirmation_409(gate)
    except OutOfStock as err:
        return _out_of_stock_409(err)
    return order.model_dump(mode="json")


@app.get("/internal/orders/{order_id}")
def get_order(order_id: str):
    """주문 상세 — 픽업 상태·픽업 매장 포함(O3-5·R12)."""
    order = _container.order.get(order_id)
    if order is None:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "주문 없음"})
    return order.model_dump(mode="json")


@app.post("/internal/orders/{order_id}/pickup")
def advance_pickup(order_id: str, req: PickupActionRequest):
    """픽업 상태 전이 — ready/picked_up/expired. 역전이/잘못된 전이는 409(O3-6·O4)."""
    try:
        order = _container.order.advance_pickup(order_id, req.action)
    except KeyError:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "주문 없음"})
    except PickupTransitionError as err:
        return JSONResponse(status_code=409, content={
            "code": "PickupTransitionError", "message": err.message,
            "current": err.current, "requested": err.requested,
        })
    return order.model_dump(mode="json")


# ── O2O 거점·재고(HTTP) — O1·O2 ────────────────────────────────────────────
@app.get("/internal/stores")
def list_stores(lat: float | None = None, lng: float | None = None, type: str | None = None):
    geo = (lat, lng) if lat is not None and lng is not None else None
    stores = _container.store.find_stores(geo, type)
    return [s.model_dump(mode="json") for s in stores]


@app.get("/internal/stores/{store_id}/stock/{part_id}")
def check_stock(store_id: str, part_id: str):
    return {"in_stock": _container.store.check_stock(store_id, part_id)}


# ── O2O 견적 이어보기/전환(HTTP) — O5·O6 ───────────────────────────────────
@app.get("/internal/quotes/{quote_ref}")
def get_quote(quote_ref: str, user_id: str = "usr_01"):
    """견적 조회 — 본인 403·만료 410·미발견 404. 현재가 변동은 price_changes로 고지(O5)."""
    try:
        quote = _container.store.get_quote(quote_ref, user_id)
    except KeyError:
        return JSONResponse(status_code=404, content={
            "code": "not_found", "message": "견적을 찾지 못했습니다. 매장에 문의하거나 재견적을 받아 주세요."})
    except QuoteForbidden as err:
        return JSONResponse(status_code=403, content={"code": "Forbidden", "message": err.message})
    except QuoteExpired as err:
        return JSONResponse(status_code=410, content={"code": "QuoteExpired", "message": err.message})
    body = quote.model_dump(mode="json")
    body["price_changes"] = _container.store.price_changes(quote)  # 차이 고지(O5-4)
    return body


@app.post("/internal/quotes/{quote_ref}/convert")
def convert_quote(quote_ref: str, req: ConvertRequest):
    """견적 → 주문 전환 — ACTIVE만(409), 확인(409), 전환 시 CONVERTED(O6·R17)."""
    try:
        quote = _container.store.get_quote(quote_ref, req.user_id)
    except KeyError:
        return JSONResponse(status_code=404, content={
            "code": "not_found", "message": "견적을 찾지 못했습니다."})
    except QuoteForbidden as err:
        return JSONResponse(status_code=403, content={"code": "Forbidden", "message": err.message})
    except QuoteExpired as err:
        return JSONResponse(status_code=410, content={"code": "QuoteExpired", "message": err.message})
    try:
        order = _container.order.convert_quote(
            quote, confirmed=req.confirmed, fulfillment=req.fulfillment, store_id=req.store_id)
    except ConfirmationRequired as gate:
        body = _confirmation_409(gate)
        return body
    except OutOfStock as err:
        return _out_of_stock_409(err)
    except QuoteNotConvertible as err:
        return JSONResponse(status_code=409, content={
            "code": "QuoteNotConvertible", "message": err.message, "status": err.status})
    return {"order": order.model_dump(mode="json"), "quote_status": quote.status}


# ── 핸드오프/예약(HTTP) — R18 ────────────────────────────────────────────────
@app.get("/internal/bookings/slots")
def booking_slots(visit_type: str = "REPAIR"):
    return [s.model_dump(mode="json") for s in _container.handoff.list_slots(visit_type)]


def _booking_confirmation_409(req: BookingRequest) -> JSONResponse:
    """409 + confirmation 템플릿 — 예약 커밋 전 확인(R17, 주문 게이트와 동형)."""
    slot = next((s for s in _container.handoff.list_slots(req.visit_type)
                 if s.id == req.slot_id), None)
    return JSONResponse(status_code=409, content={
        "code": "ConfirmationRequired",
        "message": "방문 예약 확인이 필요합니다.",
        "template": Template(kind="confirmation", data={
            "booking": {
                "slot_id": req.slot_id, "visit_type": req.visit_type, "store_id": req.store_id,
                "slot": slot.model_dump(mode="json") if slot else None,
            },
        }).model_dump(mode="json"),
    })


@app.post("/internal/bookings")
def create_booking(req: BookingRequest, x_user_id: str | None = Header(None),
                   x_guest_token: str | None = Header(None)):
    """방문 예약 — 게스트 차단(요구사항 2-3) → 미확인이면 409 ConfirmationRequired(R17).
    확인 시 센터 방문(O7-4)은 visit_type/store_id 동반, 맥락 전달(context_ref, O7-5)."""
    gate = _guest_commit_gate(x_user_id, x_guest_token,   # gap ② — 헤더 우선·본문 폴백
                              req.user_id, req.guest_token)
    if gate is not None:
        return gate
    if not req.confirmed:
        return _booking_confirmation_409(req)
    return _container.handoff.book(
        req.slot_id, req.context_ref, visit_type=req.visit_type, store_id=req.store_id
    ).model_dump(mode="json")


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
