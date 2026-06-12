"""O2O 내부 API — 거점·재고·픽업·견적·전환 결정적 엔드포인트(O1~O6·O8-4).

모듈 컨테이너 공유 상태 주의 → 격리가 필요한 흐름은 새 TestClient를 쓴다.
"""
from fastapi.testclient import TestClient

from app.api.internal import app

client = TestClient(app)


# ── 거점·재고(O1·O2) ────────────────────────────────────────────────────────
def test_list_stores():
    r = client.get("/internal/stores")
    assert r.status_code == 200
    assert any(s["id"] == "store_gangnam" for s in r.json())


def test_list_stores_filter_type():
    r = client.get("/internal/stores", params={"type": "service_center"})
    assert all(s["type"] == "service_center" for s in r.json())


def test_list_stores_with_geo_sorted():
    r = client.get("/internal/stores", params={"lat": 37.4979, "lng": 127.0276})
    assert r.json()[0]["id"] == "store_gangnam"


def test_check_stock_endpoint():
    assert client.get("/internal/stores/store_gangnam/stock/part_drain_filter").json()["in_stock"] is True
    assert client.get("/internal/stores/store_hongdae/stock/part_drain_filter").json()["in_stock"] is False


# ── 픽업 주문(O3) ────────────────────────────────────────────────────────────
def test_pickup_order_without_confirmation_409():
    r = client.post("/internal/orders", json={
        "part_ids": ["part_drain_filter"], "fulfillment": "pickup",
        "store_id": "store_gangnam", "confirmed": False})
    assert r.status_code == 409
    assert r.json()["code"] == "ConfirmationRequired"
    assert r.json()["template"]["data"]["order"]["fulfillment"] == "pickup"


def test_pickup_order_out_of_stock_409_with_alternatives():
    r = client.post("/internal/orders", json={
        "part_ids": ["part_drain_filter"], "fulfillment": "pickup",
        "store_id": "store_hongdae", "confirmed": True})
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "OutOfStock"
    assert any(s["id"] == "store_gangnam" for s in body["alternatives"])  # 대체 매장
    assert body["delivery_available"] is True


def test_pickup_order_confirmed_and_lifecycle():
    c = TestClient(app)
    r = c.post("/internal/orders", json={
        "part_ids": ["part_drain_filter"], "fulfillment": "pickup",
        "store_id": "store_gangnam", "confirmed": True})
    assert r.status_code == 200
    oid = r.json()["id"]
    assert r.json()["pickup_status"] == "RESERVED"
    # GET /orders/{id} 픽업 상태 노출(O3-5)
    got = c.get(f"/internal/orders/{oid}").json()
    assert got["pickup_status"] == "RESERVED" and got["store_id"] == "store_gangnam"
    # ready → picked_up 전이
    assert c.post(f"/internal/orders/{oid}/pickup", json={"action": "ready"}).json()["pickup_status"] == "READY"
    assert c.post(f"/internal/orders/{oid}/pickup", json={"action": "picked_up"}).json()["pickup_status"] == "PICKED_UP"


def test_pickup_reverse_transition_409():
    c = TestClient(app)
    oid = c.post("/internal/orders", json={
        "part_ids": ["part_drain_filter"], "fulfillment": "pickup",
        "store_id": "store_gangnam", "confirmed": True}).json()["id"]
    # RESERVED → picked_up (건너뜀) 거부
    r = c.post(f"/internal/orders/{oid}/pickup", json={"action": "picked_up"})
    assert r.status_code == 409 and r.json()["code"] == "PickupTransitionError"


def test_pickup_expired_links_refund():
    c = TestClient(app)
    oid = c.post("/internal/orders", json={
        "part_ids": ["part_drain_filter"], "fulfillment": "pickup",
        "store_id": "store_gangnam", "confirmed": True}).json()["id"]
    r = c.post(f"/internal/orders/{oid}/pickup", json={"action": "expired"})
    assert r.json()["pickup_status"] == "EXPIRED" and r.json()["status"] == "REFUNDED"


def test_get_order_not_found():
    assert client.get("/internal/orders/nope_xyz").status_code == 404


# ── 견적 이어보기(O5) ────────────────────────────────────────────────────────
def test_get_quote_own_active():
    r = client.get("/internal/quotes/quote_active", params={"user_id": "usr_01"})
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"


def test_get_quote_forbidden_403():
    r = client.get("/internal/quotes/quote_other", params={"user_id": "usr_01"})
    assert r.status_code == 403


def test_get_quote_expired_410():
    r = client.get("/internal/quotes/quote_expired", params={"user_id": "usr_01"})
    assert r.status_code == 410


def test_get_quote_missing_404():
    assert client.get("/internal/quotes/quote_none").status_code == 404


def test_get_quote_reports_price_changes():
    r = client.get("/internal/quotes/quote_pricedrift", params={"user_id": "usr_01"})
    assert r.json()["price_changes"][0]["current"] == 38000


# ── 견적 전환(O6) ────────────────────────────────────────────────────────────
def test_convert_without_confirmation_409():
    r = client.post("/internal/quotes/quote_active/convert",
                    json={"user_id": "usr_01", "confirmed": False})
    assert r.status_code == 409 and r.json()["code"] == "ConfirmationRequired"


def test_convert_confirmed_creates_order_and_converts():
    c = TestClient(app)
    r = c.post("/internal/quotes/quote_active/convert",
               json={"user_id": "usr_01", "confirmed": True})
    assert r.status_code == 200
    assert r.json()["order"]["status"] == "CONFIRMED"
    assert r.json()["quote_status"] == "CONVERTED"


def test_convert_forbidden_quote_403():
    r = client.post("/internal/quotes/quote_other/convert",
                    json={"user_id": "usr_01", "confirmed": True})
    assert r.status_code == 403


# ── 센터 예약(O7) ────────────────────────────────────────────────────────────
def test_center_booking_endpoint():
    slots = client.get("/internal/bookings/slots", params={"visit_type": "center"}).json()
    r = client.post("/internal/bookings", json={
        "slot_id": slots[0]["id"], "context_ref": "conv_7",
        "visit_type": "center", "store_id": "store_seocho_svc"})
    body = r.json()
    assert body["status"] == "CONFIRMED"
    assert body["visit_type"] == "center" and body["store_id"] == "store_seocho_svc"
