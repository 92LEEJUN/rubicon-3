"""BE 내부 API — 결정적 엔드포인트·커밋 게이트·surface·WS 스트림(api-contract §2.4)."""
import pytest
from fastapi.testclient import TestClient

from app.api.internal import app

client = TestClient(app)


# ── 조회(§2.2) ───────────────────────────────────────────────────────────────
def test_list_devices():
    r = client.get("/internal/devices")
    assert r.status_code == 200
    assert any(d["id"] == "dev_washer_01" for d in r.json())


def test_get_device_with_anomalies():
    r = client.get("/internal/devices/dev_washer_01")
    assert r.status_code == 200
    assert r.json()["found"] is True
    assert r.json()["anomalies"]


def test_get_device_not_found():
    assert client.get("/internal/devices/없는기기xyz").status_code == 404


def test_home_summary_aggregation():
    body = client.get("/internal/home").json()
    assert body["kind"] == "home_summary"
    assert len(body["data"]["devices"]) == 3
    assert len(body["data"]["alerts"]) >= 1  # 정수/HEPA 임박


def test_recommend_endpoint():
    r = client.get("/internal/catalog/recommend")
    assert any(p["id"] == "prod_purifier_cube" for p in r.json())


# ── 커밋 게이트(R17) ─────────────────────────────────────────────────────────
def test_order_without_confirmation_returns_409():
    r = client.post("/internal/orders", json={"part_ids": ["part_drain_filter"], "confirmed": False})
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "ConfirmationRequired"
    assert body["template"]["kind"] == "confirmation"
    assert body["template"]["data"]["summary"]["subtotal"] == 12000


def test_order_with_confirmation_succeeds():
    r = client.post("/internal/orders", json={"part_ids": ["part_drain_filter"], "confirmed": True})
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED"


# ── 예약(R18) ────────────────────────────────────────────────────────────────
def test_booking_slots_and_create():
    slots = client.get("/internal/bookings/slots").json()
    assert slots
    r = client.post("/internal/bookings", json={"slot_id": slots[0]["id"], "context_ref": "conv_1"})
    assert r.json()["status"] == "CONFIRMED"


# ── surface(§2.3) ────────────────────────────────────────────────────────────
def test_surface_consumable_returns_bridge():
    r = client.post("/internal/surface", json={"card_type": "consumable", "ref": "냉장고"})
    body = r.json()
    assert body["surface"] == "bridge"
    assert body["template"]["kind"] == "bridge"


def test_surface_complex_returns_panel():
    r = client.post("/internal/surface", json={"card_type": "troubleshoot", "ref": "x"})
    assert r.json()["surface"] == "panel"


# ── WS 스트림(§2.1) ─────────────────────────────────────────────────────────
def test_http_turn_streams_ndjson():
    import json
    r = client.post("/internal/turn", json={"text": "세탁기 물이 안 빠져요. 부품도 주문할래요"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/x-ndjson")
    chunks = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    assert chunks[-1]["type"] == "done"
    assert any(c["type"] == "section" and c["section"]["template"]["kind"] == "guide_steps"
               for c in chunks)


def test_ws_turn_streams_sections():
    with client.websocket_connect("/internal/turn") as ws:
        ws.send_json({"session_id": "s1", "text": "세탁기에서 물이 안 빠져요. 부품도 주문할래요"})
        types, kinds = [], []
        while True:
            chunk = ws.receive_json()
            types.append(chunk["type"])
            if chunk["type"] == "section":
                kinds.append(chunk["section"]["template"]["kind"])
            if chunk["type"] == "done":
                break
        assert "section" in types and types[-1] == "done"
        assert "guide_steps" in kinds


# ── 이어가기(컴패니언 §1) — 턴 기록 후 resume에 맥락 복원 ─────────────────────
def test_resume_after_turn_records_context():
    c = TestClient(app)  # 격리 위해 새 클라이언트(모듈 컨테이너 공유 상태 주의)
    assert c.get("/internal/resume?fresh=true").json()["has_context"] is False
    c.post("/internal/turn", json={"text": "세탁기 5C 에러"})  # 턴 기록 → 컴팩션 배선
    r = c.get("/internal/resume").json()
    assert r["has_context"] is True
    assert r["elapsed_label"] is not None
