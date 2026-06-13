"""BFF 결정적 엔드포인트 — 신원 포워딩·중계·커밋 게이트·폴백(api-contract §2·§4)."""
import httpx
from fastapi.testclient import TestClient

from gateway.backend_client import BackendClient
from gateway.main import create_app
from tests.conftest import AUTH


class _Captured:
    """BE 호출에 실린 헤더를 가로채는 더미 BE 응답."""
    def __init__(self):
        self.headers = {}


def _capturing_client():
    """모든 BE 호출의 요청 헤더를 캡처하고 빈 JSON 200을 돌려주는 클라이언트."""
    cap = _Captured()

    def _handler(request: httpx.Request) -> httpx.Response:
        cap.headers = dict(request.headers)
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(_handler)
    client = TestClient(create_app(BackendClient(base_url="http://be", transport=transport)))
    return client, cap


# ── 신원 포워딩(공유 계약) — HTTP 호출에 X-User-Id/X-Guest-Token ─────────────
def test_http_forwards_user_id_header():
    client, cap = _capturing_client()
    client.get("/home", headers=AUTH)
    assert cap.headers.get("x-user-id") == "usr_01"
    assert "x-guest-token" not in cap.headers


def test_http_forwards_guest_token_header():
    client, cap = _capturing_client()
    client.get("/home", params={"guest_token": "g-abc"})   # 토큰 없음 → 게스트
    assert cap.headers.get("x-guest-token") == "g-abc"
    assert "x-user-id" not in cap.headers


def test_commit_forwards_identity_header():
    client, cap = _capturing_client()
    client.post("/orders", json={"part_ids": ["p1"], "confirmed": True}, headers=AUTH)
    assert cap.headers.get("x-user-id") == "usr_01"


# ── 신원 해석(§3) — 게스트(비로그인)도 조회 허용(401로 막지 않음) ────────────
def test_devices_allows_guest(client):
    # 토큰 없음 → 게스트로 폴백. BE는 MULTITENANT off면 기본 사용자로 처리 → 200.
    assert client.get("/devices").status_code == 200


def test_devices_with_auth(client):
    r = client.get("/devices", headers=AUTH)
    assert r.status_code == 200
    assert any(d["id"] == "dev_washer_01" for d in r.json())


# ── 중계(§2.2) ───────────────────────────────────────────────────────────────
def test_device_detail_relayed(client):
    r = client.get("/devices/dev_washer_01", headers=AUTH)
    assert r.json()["found"] is True


# ── 이어가기(컴패니언 §1) ────────────────────────────────────────────────────
def test_resume_allows_guest(client):
    assert client.get("/resume").status_code == 200


def test_resume_relayed(client):
    body = client.get("/resume?fresh=true", headers=AUTH).json()
    assert body["has_context"] is False        # fresh → 깨끗한 시작


def test_reengagement_allows_guest(client):
    assert client.get("/reengagement").status_code == 200


def test_reengagement_relayed(client):
    assert client.get("/reengagement", headers=AUTH).status_code == 200


def test_recommendations_relayed(client):
    body = client.get("/recommendations", headers=AUTH).json()
    assert "items" in body                     # 추천 코어 산출(개인화·동의 차등)


def test_reengagement_deliver_relayed(client):
    assert client.post("/reengagement/deliver", headers=AUTH).status_code == 200


def test_open_loop_action_relayed(client):
    # 미존재 ref → BE 404를 그대로 중계
    assert client.post("/open-loops/none_xyz/resolve", headers=AUTH).status_code == 404


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
    # 확인 게이트(R17) — confirmed=True 여야 예약 확정(주문과 동일).
    r = client.post("/bookings", json={"slot_id": slots[0]["id"], "context_ref": "conv_1",
                                       "confirmed": True}, headers=AUTH)
    assert r.json()["status"] == "CONFIRMED"


def test_surface_bridge(client):
    r = client.post("/surface", json={"card_type": "consumable", "ref": "냉장고"}, headers=AUTH)
    assert r.json()["surface"] == "bridge"


# ── 게스트 커밋 게이트 — BE 401(LoginRequired) 그대로 중계(MULTITENANT on) ───
def test_guest_order_relays_login_required(client, monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    # 토큰 없음 → 게스트. BFF는 막지 않고 BE가 401 LoginRequired를 돌려주면 그대로 중계.
    r = client.post("/orders", json={"part_ids": ["part_drain_filter"], "confirmed": True})
    assert r.status_code == 401
    assert r.json()["code"] == "LoginRequired"


def test_login_user_order_passes_with_multitenant(client, monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.post("/orders", json={"part_ids": ["part_drain_filter"], "confirmed": True},
                    headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED"


# ── 예약 확인 게이트 — 미확인 시 BE 409(ConfirmationRequired) 그대로 중계 ────
def test_booking_confirmation_409_relayed(client):
    slots = client.get("/bookings/slots", headers=AUTH).json()
    r = client.post("/bookings", json={"slot_id": slots[0]["id"], "context_ref": "conv_1",
                                       "confirmed": False}, headers=AUTH)
    assert r.status_code == 409 and r.json()["code"] == "ConfirmationRequired"


# ── 폴백 정규화(R13) — 업스트림 장애 ────────────────────────────────────────
def test_fallback_when_backend_down(broken_client):
    r = broken_client.get("/home", headers=AUTH)
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "upstream_unavailable"
    assert body["fallback"]["kind"] == "text"
