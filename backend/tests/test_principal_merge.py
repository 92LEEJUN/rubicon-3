"""멀티테넌트 task 5.2 — 게스트→로그인 머지 테스트.

게스트(`guest:<token>`) 상태(주문·대화·미해결·engagement)를 로그인 user_id로 이관(re-keying).
이관 후 사용자가 보고, 게스트는 비워진다. 충돌(대화/ref) 엣지 케이스도 검증한다.

직접 `merge_principal_state(container, guest_id, user_id)`를 호출(헬퍼 단위) + 엔드포인트(머지)
양쪽을 검증한다.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import fixtures as fx
from app.container import build_container
from app.principal import guest_principal, merge_principal_state


def _in_stock_part_ids(n: int = 1) -> list[str]:
    return [p["id"] for p in fx.PARTS if p.get("in_stock", True)][:n]


def _seed_guest(container, guest_id: str) -> str:
    """게스트 상태 시드: 주문 + 대화 + open-loop + engagement. 주문 id 반환."""
    order = container.order._port.place_order(guest_id, _in_stock_part_ids(1), confirmed=True)
    container.companion.record_turn(guest_id, "세탁기 5C 에러", "확인해볼게요")
    container.companion.track_loop(guest_id, "issue", "ref_x", "수리 이어보기", priority=2)
    container.engagement.record(guest_id, "rec_1", "viewed")
    return order.id


# ── 헬퍼 단위 테스트 ─────────────────────────────────────────────────────────
def test_merge_transfers_orders_to_user():
    container = build_container()
    guest_id = guest_principal("tok1").id
    order_id = _seed_guest(container, guest_id)

    summary = merge_principal_state(container, guest_id, "usr_login")

    assert summary["orders"] == 1
    # 사용자가 주문을 본다.
    user_orders = container.order.history("usr_login")
    assert order_id in {o.id for o in user_orders}
    assert user_orders[0].user_id == "usr_login"
    # 게스트는 비워졌다.
    assert container.order.history(guest_id) == []


def test_merge_transfers_conversation_and_loops():
    container = build_container()
    guest_id = guest_principal("tok2").id
    _seed_guest(container, guest_id)

    summary = merge_principal_state(container, guest_id, "usr_login")

    assert summary["conversation"] == 1
    assert summary["open_loops"] >= 1
    # 사용자가 대화 메모리/미해결 스레드를 본다.
    assert container.conversation_memory.get("usr_login") != container.conversation_memory.get("nobody")
    user_loops = {loop.ref for loop in container.companion.open_loops("usr_login")}
    assert "ref_x" in user_loops
    # 게스트 비움.
    assert container.companion.open_loops(guest_id) == []
    assert not container.conversation_memory.get(guest_id).facts


def test_merge_transfers_engagement():
    container = build_container()
    guest_id = guest_principal("tok3").id
    _seed_guest(container, guest_id)

    summary = merge_principal_state(container, guest_id, "usr_login")

    assert summary["engagement"] == 1
    assert container.engagement.has_seen("usr_login", "rec_1") is True


def test_merge_does_not_clobber_existing_user_conversation():
    """충돌: 로그인 사용자에게 이미 대화가 있으면 게스트로 덮어쓰지 않는다(로그인 우선)."""
    container = build_container()
    guest_id = guest_principal("tok4").id
    _seed_guest(container, guest_id)
    # 사용자에게 선존재 대화(사실 추출되는 텍스트 — 비어있지 않은 메모리).
    container.companion.record_turn("usr_login", "냉장고 6C 에러 확인", "네")
    before = container.conversation_memory.get("usr_login")
    assert before.facts  # 선존재 대화가 실제로 비어있지 않음(가드 전제)

    summary = merge_principal_state(container, guest_id, "usr_login")

    assert summary["conversation"] == 0  # 덮어쓰지 않음
    assert container.conversation_memory.get("usr_login") == before


def test_merge_empty_guest_is_noop():
    container = build_container()
    guest_id = guest_principal("tok5").id
    summary = merge_principal_state(container, guest_id, "usr_login")
    assert summary == {"orders": 0, "conversation": 0, "open_loops": 0, "engagement": 0}


# ── 엔드포인트 테스트 ────────────────────────────────────────────────────────
def test_merge_endpoint_returns_summary():
    from app.api import internal

    client = TestClient(internal.app)
    container = internal._container
    guest_id = guest_principal("ep_tok").id
    order_id = _seed_guest(container, guest_id)

    resp = client.post("/internal/principal/merge",
                       json={"guest_token": "ep_tok", "user_id": "usr_ep"})
    assert resp.status_code == 200
    merged = resp.json()["merged"]
    assert merged["orders"] == 1
    assert merged["open_loops"] >= 1
    # 머지 후 사용자가 주문을 본다(같은 공유 컨테이너).
    assert order_id in {o.id for o in container.order.history("usr_ep")}
