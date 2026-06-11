"""BFF 결정적 엔드포인트 — 인증 게이트·중계·커밋 게이트·폴백(api-contract §2·§4)."""
from tests.conftest import AUTH


# ── 인증 게이트(§3) ──────────────────────────────────────────────────────────
def test_devices_requires_auth(client):
    assert client.get("/devices").status_code == 401


def test_devices_with_auth(client):
    r = client.get("/devices", headers=AUTH)
    assert r.status_code == 200
    assert any(d["id"] == "dev_washer_01" for d in r.json())


# ── 중계(§2.2) ───────────────────────────────────────────────────────────────
def test_device_detail_relayed(client):
    r = client.get("/devices/dev_washer_01", headers=AUTH)
    assert r.json()["found"] is True


def test_device_not_found_status_preserved(client):
    assert client.get("/devices/없는기기", headers=AUTH).status_code == 404


def test_home_aggregation_relayed(client):
    body = client.get("/home", headers=AUTH).json()
    assert body["kind"] == "home_summary"
    assert len(body["data"]["devices"]) == 3


def test_recommend(client):
    r = client.get("/catalog/recommend", headers=AUTH)
    assert any(p["id"] == "prod_purifier_cube" for p in r.json())


# ── 커밋 게이트(R17) — 409 그대로 중계 ──────────────────────────────────────
def test_order_409_relayed_with_confirmation_template(client):
    r = client.post("/orders", json={"part_ids": ["part_drain_filter"]}, headers=AUTH)
    assert r.status_code == 409
    assert r.json()["template"]["kind"] == "confirmation"
    # 계약 합치: BE가 계산한 금액 분해가 그대로 전달
    assert r.json()["template"]["data"]["summary"]["subtotal"] == 12000


def test_order_confirmed_succeeds(client):
    r = client.post("/orders", json={"part_ids": ["part_drain_filter"], "confirmed": True}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED"


# ── 예약(R18) / surface(§2.3) ────────────────────────────────────────────────
def test_booking_flow(client):
    slots = client.get("/bookings/slots", headers=AUTH).json()
    r = client.post("/bookings", json={"slot_id": slots[0]["id"], "context_ref": "conv_1"}, headers=AUTH)
    assert r.json()["status"] == "CONFIRMED"


def test_surface_bridge(client):
    r = client.post("/surface", json={"card_type": "consumable", "ref": "냉장고"}, headers=AUTH)
    assert r.json()["surface"] == "bridge"


# ── 폴백 정규화(R13) — 업스트림 장애 ────────────────────────────────────────
def test_fallback_when_backend_down(broken_client):
    r = broken_client.get("/home", headers=AUTH)
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "upstream_unavailable"
    assert body["fallback"]["kind"] == "text"
