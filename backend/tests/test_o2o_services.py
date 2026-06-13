"""O2O 도메인 서비스 — 거점·재고·픽업 라이프사이클·견적·트리아지(O1~O7).

결정적/Mock 테스트(LLM·네트워크 불필요). container 픽스처(conftest)로 Mock 어댑터 조립.
"""

import pytest

from app.domain import Cta, Solution, SolutionStep
from app.errors import (
    ConfirmationRequired,
    OutOfStock,
    PickupTransitionError,
    QuoteExpired,
    QuoteForbidden,
    QuoteNotConvertible,
)


# ── StoreService: 거점·재고 (O1·O2) ─────────────────────────────────────────
def test_find_stores_filters_by_type(container):
    centers = container.store.find_stores(store_type="service_center")
    assert centers and all(s.type == "service_center" for s in centers)


def test_find_stores_sorts_by_geo(container):
    near = container.store.find_stores(geo=(37.4979, 127.0276))  # 강남 좌표
    assert near[0].id == "store_gangnam"


def test_find_stores_no_geo_returns_all(container):
    # 위치 없음 → 흐름 차단 금지, 전체 반환(O1-3 폴백)
    assert len(container.store.find_stores()) == 3


def test_check_stock_gate(container):
    assert container.store.check_stock("store_gangnam", "part_drain_filter") is True
    assert container.store.check_stock("store_hongdae", "part_drain_filter") is False


def test_stores_with_stock_alternatives(container):
    alts = container.store.stores_with_stock("part_water_filter")
    ids = {s.id for s in alts}
    assert "store_gangnam" in ids and "store_hongdae" in ids  # 둘 다 정수필터 보유


# ── 픽업(BOPIS) 주문 생성 + 재고 게이트 (O2·O3) ─────────────────────────────
def test_pickup_checkout_blocked_when_out_of_stock(container):
    with pytest.raises(OutOfStock):
        container.order.checkout_pickup("usr_01", ["part_drain_filter"], "store_hongdae",
                                        confirmed=True)


def test_pickup_checkout_requires_confirmation(container):
    with pytest.raises(ConfirmationRequired) as exc:
        container.order.checkout_pickup("usr_01", ["part_drain_filter"], "store_gangnam",
                                        confirmed=False)
    assert exc.value.draft.fulfillment == "pickup"
    assert exc.value.draft.store_id == "store_gangnam"


def test_pickup_checkout_confirmed_starts_reserved(container):
    order = container.order.checkout_pickup("usr_01", ["part_drain_filter"], "store_gangnam",
                                            confirmed=True)
    assert order.status == "CONFIRMED"
    assert order.fulfillment == "pickup"
    assert order.pickup_status == "RESERVED"
    assert order.summary.shipping_fee == 0  # 픽업은 배송비 없음


# ── 픽업 상태머신 (O3-6·O4) ──────────────────────────────────────────────────
def _new_pickup(container):
    return container.order.checkout_pickup("usr_01", ["part_drain_filter"], "store_gangnam",
                                           confirmed=True)


def test_pickup_happy_path_transitions(container):
    o = _new_pickup(container)
    assert container.order.advance_pickup(o.id, "ready").pickup_status == "READY"
    assert container.order.advance_pickup(o.id, "picked_up").pickup_status == "PICKED_UP"


def test_pickup_ready_emits_alert(container):
    o = _new_pickup(container)
    container.order.advance_pickup(o.id, "ready")
    delivered = container.order._alert.delivered
    assert any(m["kind"] == "pickup_ready" and m["ref"] == o.id for m in delivered)


def test_pickup_reverse_transition_rejected(container):
    o = _new_pickup(container)
    container.order.advance_pickup(o.id, "ready")
    container.order.advance_pickup(o.id, "picked_up")
    # PICKED_UP → ready 역전이 거부(O3-6)
    with pytest.raises(PickupTransitionError):
        container.order.advance_pickup(o.id, "ready")


def test_pickup_skip_transition_rejected(container):
    o = _new_pickup(container)
    # RESERVED → picked_up (READY 건너뜀) 거부
    with pytest.raises(PickupTransitionError):
        container.order.advance_pickup(o.id, "picked_up")


def test_pickup_expired_links_refund(container):
    o = _new_pickup(container)
    refunded = container.order.advance_pickup(o.id, "expired")
    assert refunded.pickup_status == "EXPIRED"
    assert refunded.status == "REFUNDED"  # 취소/환불(R21) 연계(O4-2)


# ── 견적 이어보기 (O5) ───────────────────────────────────────────────────────
def test_get_quote_own_active(container):
    q = container.store.get_quote("quote_active", "usr_01")
    assert q.status == "ACTIVE" and q.user_id == "usr_01"


def test_get_quote_forbidden_for_other_user(container):
    with pytest.raises(QuoteForbidden):
        container.store.get_quote("quote_other", "usr_01")


def test_get_quote_expired(container):
    with pytest.raises(QuoteExpired):
        container.store.get_quote("quote_expired", "usr_01")


def test_get_quote_missing_raises_keyerror(container):
    with pytest.raises(KeyError):
        container.store.get_quote("quote_none", "usr_01")


def test_quote_price_changes_detected(container):
    q = container.store.get_quote("quote_pricedrift", "usr_01")
    changes = container.store.price_changes(q)
    # 견적가 35000 vs 현재가 38000(catalog) → 차이 고지(O5-4)
    assert changes and changes[0]["quoted"] == 35000 and changes[0]["current"] == 38000


# ── 견적 → 주문 전환 (O6) ───────────────────────────────────────────────────
def test_convert_requires_confirmation(container):
    q = container.store.get_quote("quote_active", "usr_01")
    with pytest.raises(ConfirmationRequired):
        container.order.convert_quote(q, confirmed=False)


def test_convert_active_to_order_and_converted(container):
    q = container.store.get_quote("quote_active", "usr_01")
    order = container.order.convert_quote(q, confirmed=True)
    assert order.status == "CONFIRMED"
    assert q.status == "CONVERTED"  # 견적 전이(O6-1)


def test_convert_non_active_rejected(container):
    q = container.store.get_quote("quote_active", "usr_01")
    q.status = "CONVERTED"
    with pytest.raises(QuoteNotConvertible):
        container.order.convert_quote(q, confirmed=True)


def test_convert_with_pickup_fulfillment(container):
    q = container.store.get_quote("quote_active", "usr_01")  # store_gangnam, drain_filter 재고O
    order = container.order.convert_quote(q, confirmed=True, fulfillment="pickup")
    assert order.fulfillment == "pickup" and order.pickup_status == "RESERVED"


# ── 트리아지 (O7) ────────────────────────────────────────────────────────────
def _sol(steps):
    return Solution(id="s1", steps=steps)


def test_triage_self_for_simple(container):
    sol = _sol([SolutionStep(order=1, instruction="필터 청소", safety="none")])
    assert container.triage.decide(sol)["path"] == "self"


def test_triage_repair_for_pro_required(container):
    sol = _sol([SolutionStep(order=1, instruction="기판 교체", pro_required=True)])
    assert container.triage.decide(sol)["path"] == "repair"


def test_triage_center_for_danger(container):
    sol = _sol([SolutionStep(order=1, instruction="고전압 부품", safety="danger")])
    assert container.triage.decide(sol)["path"] == "center"


def test_triage_agent_when_uncertain(container):
    assert container.triage.decide(None, uncertain=True)["path"] == "agent"
    assert container.triage.decide(None)["path"] == "agent"


# ── 센터 예약 핸드오프 (O7-4·O7-5) ───────────────────────────────────────────
def test_center_booking_with_store_and_context(container):
    slots = container.handoff.list_slots("center")
    bk = container.handoff.book(slots[0].id, context_ref="conv_42",
                                visit_type="center", store_id="store_seocho_svc")
    assert bk.status == "CONFIRMED"
    assert bk.visit_type == "center" and bk.store_id == "store_seocho_svc"
    assert bk.context_ref == "conv_42"  # 대화 맥락 전달(O7-5)


# ── ActionGate (R17·ADR-0033) ───────────────────────────────────────────────
def test_action_gate_requires_confirmation_for_commit(container):
    from app.adapters.mock import MockActionGateAdapter
    gate = MockActionGateAdapter()
    assert gate.requires_confirmation(Cta(label="픽업 확정", action="commit")) is True
    assert gate.requires_confirmation(Cta(label="자세히", action="chat", kind="explain")) is False
    assert gate.requires_confirmation(Cta(label="견적 전환", action="chat", kind="convert")) is True


# ── 폴백 (O8-1·R13) ─────────────────────────────────────────────────────────
def test_store_find_failure_falls_back_to_empty(container):
    class _Boom:
        def find_stores(self, *a, **k): raise RuntimeError("down")
        def check_stock(self, *a, **k): raise RuntimeError("down")
    from app.services import StoreService
    svc = StoreService(_Boom(), container.store._quote)
    assert svc.find_stores() == []          # 실패 → 빈 결과 폴백
    assert svc.check_stock("x", "y") is False  # 실패 → 보수적 없음
