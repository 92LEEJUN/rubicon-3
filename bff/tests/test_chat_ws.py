"""BFF WS /chat — BE 섹션 스트림 중계·인터랙션 회신·인증·폴백(api-contract §2.1)."""
from tests.conftest import AUTH


def _drain(ws):
    chunks = []
    while True:
        c = ws.receive_json()
        chunks.append(c)
        if c["type"] in ("done", "error"):
            break
    return chunks


# ── J1: 자연어 → 섹션 스트림 중계 ───────────────────────────────────────────
def test_chat_streams_sections(client):
    with client.websocket_connect("/chat", headers=AUTH) as ws:
        ws.send_json({"type": "user_message", "session_id": "s1",
                      "text": "세탁기에서 물이 안 빠져요. 부품도 주문할래요"})
        chunks = _drain(ws)
    types = [c["type"] for c in chunks]
    kinds = [c["section"]["template"]["kind"] for c in chunks if c["type"] == "section"]
    assert types[-1] == "done"
    assert "guide_steps" in kinds          # 해결 가이드
    assert "product_card" in kinds         # 배수필터 주문 카드(맥락 전달)


# ── J5: 복합 — handled/unhandled 섹션 중계 ──────────────────────────────────
def test_chat_compound_handled_unhandled(client):
    msg = "세탁기 물 안 빠지는 거 해결법 알려주고, 냉장고 정수필터랑 공기청정기 HEPA 필터도 주문해줘"
    with client.websocket_connect("/chat", headers=AUTH) as ws:
        ws.send_json({"type": "user_message", "text": msg})
        chunks = _drain(ws)
    sections = [c["section"] for c in chunks if c["type"] == "section"]
    handled = {s["template"]["data"].get("id"): s["handled"]
               for s in sections if s["intent"] == "order" and s["template"]["kind"] == "product_card"}
    assert handled.get("part_water_filter") is True
    assert any(s["handled"] is False for s in sections)  # HEPA 품절 미처리


# ── 인터랙션 회신(confirmation) ─────────────────────────────────────────────
def test_chat_interaction_reply(client):
    with client.websocket_connect("/chat", headers=AUTH) as ws:
        ws.send_json({"type": "interaction_reply", "kind": "confirmation",
                      "ref": "msg_1", "payload": {"confirmed": True}})
        chunks = _drain(ws)
    assert chunks[-1]["type"] == "done"      # 회신도 다음 턴으로 처리


# ── 인증·폴백 ────────────────────────────────────────────────────────────────
def test_chat_unauthorized(client):
    with client.websocket_connect("/chat") as ws:   # 토큰 없음
        c = ws.receive_json()
    assert c["type"] == "error" and c["code"] == "unauthorized"


def test_chat_fallback_when_backend_down(broken_client):
    with broken_client.websocket_connect("/chat", headers=AUTH) as ws:
        ws.send_json({"type": "user_message", "text": "세탁기 상태 알려줘"})
        c = ws.receive_json()
    assert c["type"] == "error"
    assert c["fallback"]["kind"] == "text"
