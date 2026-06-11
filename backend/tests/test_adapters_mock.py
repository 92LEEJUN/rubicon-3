"""Mock 어댑터 — Port 구현이 타입 있는 도메인 객체를 정확히 반환하는지."""
from app.adapters import mock
from app.domain import Device, Order, Part, Solution
from app.ports import (
    CatalogPort,
    CSKnowledgePort,
    DevicePort,
    HandoffPort,
    OrderPort,
    WarrantyPort,
)


def test_mock_adapters_satisfy_port_protocols():
    assert isinstance(mock.MockDeviceAdapter(), DevicePort)
    assert isinstance(mock.MockCSKnowledgeAdapter(), CSKnowledgePort)
    assert isinstance(mock.MockCatalogAdapter(), CatalogPort)
    assert isinstance(mock.MockOrderAdapter(), OrderPort)
    assert isinstance(mock.MockHandoffAdapter(), HandoffPort)
    assert isinstance(mock.MockWarrantyAdapter(), WarrantyPort)


# ── DevicePort ──────────────────────────────────────────────────────────────
def test_device_status_by_korean_alias():
    res = mock.MockDeviceAdapter().get_status("세탁기")
    assert res.found
    assert isinstance(res.device, Device)
    assert res.device.type == "washer"
    assert any(a.type == "error_code" for a in res.anomalies)  # 5C


def test_device_status_not_found():
    res = mock.MockDeviceAdapter().get_status("토스터")
    assert not res.found
    assert res.device is None
    assert res.message


# ── CSKnowledgePort (하이브리드 검색) ────────────────────────────────────────
def test_solutions_by_error_code():
    res = mock.MockCSKnowledgeAdapter().find_solutions("", error_code="5C")
    assert res.count == 1
    assert res.solutions[0].id == "sol_washer_5c"


def test_solutions_by_free_text_korean():
    res = mock.MockCSKnowledgeAdapter().find_solutions("세탁기에서 물이 안 빠져요")
    assert res.count == 1
    assert isinstance(res.solutions[0], Solution)


def test_solutions_extract_code_from_query():
    res = mock.MockCSKnowledgeAdapter().find_solutions("세탁기 5C 떠요")
    assert res.solutions[0].id == "sol_washer_5c"


# ── CatalogPort ─────────────────────────────────────────────────────────────
def test_match_parts_by_required_part_id():
    res = mock.MockCatalogAdapter().match_parts(part_ids=["part_drain_filter"])
    assert res.count == 1
    assert isinstance(res.parts[0], Part)
    assert res.parts[0].price == 12000


def test_match_parts_out_of_stock_flag():
    res = mock.MockCatalogAdapter().match_parts(part_ids=["part_hepa"])
    assert res.parts[0].in_stock is False  # J3 품절


def test_recommend_by_interest_category():
    products = mock.MockCatalogAdapter().recommend(["air_purifier"])
    assert any(p.id == "prod_purifier_cube" for p in products)


# ── OrderPort (금액 분해·품절 실패) ──────────────────────────────────────────
def test_place_order_computes_summary():
    order = mock.MockOrderAdapter().place_order("usr_01", ["part_drain_filter"], confirmed=True)
    assert isinstance(order, Order)
    assert order.status == "CONFIRMED"
    assert order.summary.subtotal == 12000
    assert order.summary.total == order.summary.subtotal + order.summary.shipping_fee


def test_place_order_free_shipping_over_threshold():
    order = mock.MockOrderAdapter().place_order("usr_01", ["part_water_filter"], confirmed=True)
    assert order.summary.subtotal == 38000
    assert order.summary.shipping_fee == 0  # 3만원 이상 무료배송


def test_place_order_out_of_stock_fails():
    order = mock.MockOrderAdapter().place_order("usr_01", ["part_hepa"], confirmed=True)
    assert order.status == "FAILED"  # 품절 → 부분 실패(R13)


def test_cancel_order():
    adapter = mock.MockOrderAdapter()
    order = adapter.place_order("usr_01", ["part_drain_filter"], confirmed=True)
    cancelled = adapter.cancel_order(order.id)
    assert cancelled.status == "CANCELLED"


# ── HandoffPort / WarrantyPort ──────────────────────────────────────────────
def test_handoff_slots_and_booking():
    adapter = mock.MockHandoffAdapter()
    slots = adapter.list_slots("REPAIR")
    assert len(slots) >= 1
    booking = adapter.book_slot(slots[0].id, context_ref="conv_1")
    assert booking.status == "CONFIRMED"
    assert booking.slot_id == slots[0].id


def test_warranty_coverage_free_for_fridge_filter():
    assert mock.MockWarrantyAdapter().coverage("RF28R7351SR", "part_water_filter") == "free"
