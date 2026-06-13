"""BFF 분석 싱크(docs/analytics.md) — FE→BFF 이벤트 수신·read-back·비차단 검증.

이 경로는 BE를 호출하지 않으므로 더미 BE(MockTransport)로 충분하다(test_health.py와 동일).
- POST /internal/events → GET /internal/events 가 그 이벤트를 보여준다(왕복).
- 택소노미(analytics.md §4) 이름은 known=True로 받는다(미상도 거부하지 않고 태깅).
- 신원 인지: Authorization 있으면 principal=user, 없으면 guest 토큰으로 태깅.
- 비차단: 빈/잘못된 본문도 500을 내지 않는다(분석은 UX/중계를 막지 않음).
"""
import httpx
from fastapi.testclient import TestClient

from gateway.backend_client import BackendClient
from gateway.main import create_app

AUTH = {"Authorization": "Bearer test-token"}


def _client() -> TestClient:
    """분석 경로만 검증 — BE 호출이 없으니 더미 BE로 충분."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    return TestClient(create_app(BackendClient(base_url="http://be", transport=transport)))


def test_post_event_then_get_shows_it():
    client = _client()
    r = client.post("/internal/events", json={"name": "message_sent", "props": {"modality": "text"}})
    assert r.status_code == 200
    assert r.json()["accepted"] == 1

    g = client.get("/internal/events")
    assert g.status_code == 200
    names = [e["name"] for e in g.json()["events"]]
    assert "message_sent" in names
    last = g.json()["events"][-1]
    assert last["props"] == {"modality": "text"}
    assert last["known"] is True


def test_taxonomy_name_accepted_as_known():
    client = _client()
    client.post("/internal/events", json={"name": "cta_clicked"})
    last = client.get("/internal/events").json()["events"][-1]
    assert last["name"] == "cta_clicked"
    assert last["known"] is True


def test_unknown_name_accepted_but_tagged():
    client = _client()
    r = client.post("/internal/events", json={"name": "totally_made_up"})
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 1
    assert body["unknown"] >= 1
    last = client.get("/internal/events").json()["events"][-1]
    assert last["known"] is False


def test_batch_events_accepted():
    client = _client()
    r = client.post(
        "/internal/events",
        json={"events": [{"name": "screen_viewed"}, {"name": "chat_opened"}]},
    )
    assert r.json()["accepted"] == 2
    r2 = client.post("/internal/events", json=[{"name": "card_tapped"}, {"name": "cta_shown"}])
    assert r2.json()["accepted"] == 2


def test_identity_aware_principal_tagging():
    client = _client()
    # 로그인(Authorization) → principal = 사용자 id(MOCK_USER_ID).
    client.post("/internal/events", json={"name": "order_confirmed"}, headers=AUTH)
    user_evt = client.get("/internal/events").json()["events"][-1]
    assert user_evt["principal"] == "usr_01"

    # 게스트(무토큰, ?guest_token=) → principal = 게스트 토큰.
    client.post("/internal/events?guest_token=g-abc123", json={"name": "screen_viewed"})
    guest_evt = client.get("/internal/events").json()["events"][-1]
    assert guest_evt["principal"] == "g-abc123"


def test_non_blocking_on_bad_or_empty_body():
    client = _client()
    # 빈 본문 / 잘못된 JSON / name 누락 — 절대 500을 내지 않고 accepted=0.
    r1 = client.post("/internal/events", content=b"", headers={"Content-Type": "application/json"})
    assert r1.status_code == 200
    assert r1.json()["accepted"] == 0

    r2 = client.post("/internal/events", json={"props": {"x": 1}})  # name 누락
    assert r2.status_code == 200
    assert r2.json()["accepted"] == 0

    r3 = client.post("/internal/events", json="not-an-object")
    assert r3.status_code == 200
    assert r3.json()["accepted"] == 0


def test_get_limit_caps_readback():
    client = _client()
    for _ in range(5):
        client.post("/internal/events", json={"name": "screen_viewed"})
    capped = client.get("/internal/events?limit=2").json()["events"]
    assert len(capped) == 2
