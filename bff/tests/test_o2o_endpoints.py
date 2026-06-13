"""BFF O2O 패스스루 — 거점·재고·픽업·견적·전환을 BE에 인프로세스 중계(O1~O6).

인증 게이트 + 상태코드(403/409/410) 그대로 중계를 검증한다(api-contract §2·§4).
"""
from tests.conftest import AUTH


# ── 신원 해석 — 게스트(비로그인)도 거점 조회 허용 ───────────────────────────
def test_stores_allows_guest(client):
    assert client.get("/stores").status_code == 200


# ── 거점·재고(O1·O2) ────────────────────────────────────────────────────────
def test_stores_relayed(client):
    r = client.get("/stores", headers=AUTH)
    assert r.status_code == 200
    assert any(s["id"] == "store_gangnam" for s in r.json())


def test_stores_type_filter_relayed(client):
    r = client.get("/stores", params={"type": "service_center"}, headers=AUTH)
    assert all(s["type"] == "service_center" for s in r.json())


def test_stock_relayed(client):
    r = client.get("/stores/store_gangnam/stock/part_drain_filter", headers=AUTH)
    assert r.json()["in_stock"] is True


# ── 픽업(O3·O4) ──────────────────────────────────────────────────────────────
def test_pickup_order_confirmation_409_relayed(client):
    r = client.post("/orders", json={
        "part_ids": ["part_drain_filter"], "fulfillment": "pickup",
        "store_id": "store_gangnam"}, headers=AUTH)
    assert r.status_code == 409
    assert r.json()["template"]["data"]["order"]["fulfillment"] == "pickup"


def test_pickup_out_of_stock_409_relayed(client):
    r = client.post("/orders", json={
        "part_ids": ["part_drain_filter"], "fulfillment": "pickup",
        "store_id": "store_hongdae", "confirmed": True}, headers=AUTH)
    assert r.status_code == 409 and r.json()["code"] == "OutOfStock"


def test_pickup_lifecycle_relayed(client):
    oid = client.post("/orders", json={
        "part_ids": ["part_drain_filter"], "fulfillment": "pickup",
        "store_id": "store_gangnam", "confirmed": True}, headers=AUTH).json()["id"]
    assert client.get(f"/orders/{oid}", headers=AUTH).json()["pickup_status"] == "RESERVED"
    r = client.post(f"/orders/{oid}/pickup", json={"action": "ready"}, headers=AUTH)
    assert r.json()["pickup_status"] == "READY"
    # 역전이 409 그대로 중계
    bad = client.post(f"/orders/{oid}/pickup", json={"action": "ready"}, headers=AUTH)
    # READY→READY 도 정의 안 된 전이 → 409
    assert bad.status_code == 409


# ── 견적(O5·O6) ──────────────────────────────────────────────────────────────
def test_quote_relayed(client):
    r = client.get("/quotes/quote_active", headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"


def test_quote_forbidden_403_relayed(client):
    assert client.get("/quotes/quote_other", headers=AUTH).status_code == 403


def test_quote_expired_410_relayed(client):
    assert client.get("/quotes/quote_expired", headers=AUTH).status_code == 410


def test_convert_confirmation_409_relayed(client):
    r = client.post("/quotes/quote_active/convert", json={"confirmed": False}, headers=AUTH)
    assert r.status_code == 409 and r.json()["code"] == "ConfirmationRequired"


def test_convert_confirmed_relayed(client):
    r = client.post("/quotes/quote_active/convert", json={"confirmed": True}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["quote_status"] == "CONVERTED"


# ── 폴백(R13) — 업스트림 장애 ────────────────────────────────────────────────
def test_stores_fallback_when_backend_down(broken_client):
    r = broken_client.get("/stores", headers=AUTH)
    assert r.status_code == 503 and r.json()["code"] == "upstream_unavailable"
