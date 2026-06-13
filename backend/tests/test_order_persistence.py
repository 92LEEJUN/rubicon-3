"""멀티테넌트 task 3.5 — 주문 영속(sqlite) Repository 테스트.

- 계약 동등성: Mock(인메모리)/Sqlite 어댑터가 동일 동작(place→list→get, user 격리).
- 영속/복원: Sqlite로 주문을 쓴 뒤 같은 파일로 새 인스턴스를 만들면 주문이 복원된다.
- 토글: build_container()가 PERSISTENCE에 따라 어떤 주문 어댑터를 주입하는지.

주문 생성 로직(재고/금액/상태)은 Mock과 동일하게 재사용 — 저장소만 sqlite로 교체.
fixtures(PARTS)에 in_stock 부품이 있어야 하므로, 실제 fixture part_id로 테스트한다.
"""
from __future__ import annotations

import pytest

from app import fixtures as fx
from app.adapters.mock import MockOrderAdapter
from app.repositories.sqlite import SqliteOrderRepository


def _in_stock_part_ids(n: int = 2) -> list[str]:
    ids = [p["id"] for p in fx.PARTS if p.get("in_stock", True)]
    assert len(ids) >= n, "fixtures PARTS에 in_stock 부품이 부족합니다."
    return ids[:n]


def _make(kind: str, tmp_path):
    if kind == "memory":
        return MockOrderAdapter()
    return SqliteOrderRepository(str(tmp_path / "orders.db"))


BACKENDS = ["memory", "db"]


@pytest.mark.parametrize("kind", BACKENDS)
def test_place_list_get(kind, tmp_path):
    repo = _make(kind, tmp_path)
    part_ids = _in_stock_part_ids(1)
    order = repo.place_order("alice", part_ids, confirmed=True)
    assert order.user_id == "alice"
    assert order.status == "CONFIRMED"
    assert len(order.items) == 1
    # get 라운드트립.
    got = repo.get_order(order.id)
    assert got is not None and got.id == order.id and got.status == "CONFIRMED"
    # list_orders(user) — alice의 주문 포함.
    listed = repo.list_orders("alice")
    assert [o.id for o in listed] == [order.id]


@pytest.mark.parametrize("kind", BACKENDS)
def test_user_isolation(kind, tmp_path):
    repo = _make(kind, tmp_path)
    part_ids = _in_stock_part_ids(1)
    a = repo.place_order("alice", part_ids, confirmed=True)
    b = repo.place_order("bob", part_ids, confirmed=True)
    assert {o.id for o in repo.list_orders("alice")} == {a.id}
    assert {o.id for o in repo.list_orders("bob")} == {b.id}
    # 전체 조회(user_id 없음)는 둘 다.
    assert {o.id for o in repo.list_orders()} == {a.id, b.id}


@pytest.mark.parametrize("kind", BACKENDS)
def test_draft_and_unknown_get(kind, tmp_path):
    repo = _make(kind, tmp_path)
    part_ids = _in_stock_part_ids(1)
    draft = repo.place_order("alice", part_ids, confirmed=False)
    assert draft.status == "DRAFT"
    # 미존재 주문은 None.
    assert repo.get_order("ord_9999") is None


@pytest.mark.parametrize("kind", BACKENDS)
def test_cancel_and_refund(kind, tmp_path):
    repo = _make(kind, tmp_path)
    part_ids = _in_stock_part_ids(1)
    order = repo.place_order("alice", part_ids, confirmed=True)
    assert repo.cancel_order(order.id).status == "CANCELLED"
    assert repo.refund_order(order.id).status == "REFUNDED"
    # 영속 반영 확인.
    assert repo.get_order(order.id).status == "REFUNDED"


@pytest.mark.parametrize("kind", BACKENDS)
def test_pickup_order_and_status(kind, tmp_path):
    repo = _make(kind, tmp_path)
    part_ids = _in_stock_part_ids(1)
    order = repo.place_pickup_order("alice", part_ids, "store_1", confirmed=True)
    assert order.fulfillment == "pickup"
    assert order.store_id == "store_1"
    assert order.pickup_status == "RESERVED"
    updated = repo.update_pickup_status(order.id, "READY")
    assert updated.pickup_status == "READY"
    assert repo.get_order(order.id).pickup_status == "READY"


# ── 영속/복원: 새 인스턴스가 같은 파일에서 주문을 복원 ─────────────────────────
def test_sqlite_orders_persist_across_instances(tmp_path):
    db = str(tmp_path / "orders.db")
    part_ids = _in_stock_part_ids(1)
    first = SqliteOrderRepository(db)
    order = first.place_order("alice", part_ids, confirmed=True)
    restored = SqliteOrderRepository(db)  # 새 인스턴스, 같은 파일.
    got = restored.get_order(order.id)
    assert got is not None and got.status == "CONFIRMED"
    assert [o.id for o in restored.list_orders("alice")] == [order.id]


def test_sqlite_order_ids_do_not_collide_after_restore(tmp_path):
    """재시작/복원 후 ID 시퀀스가 충돌하지 않는다(기존 최대+1부터 발급)."""
    db = str(tmp_path / "orders.db")
    part_ids = _in_stock_part_ids(1)
    first = SqliteOrderRepository(db)
    o1 = first.place_order("alice", part_ids, confirmed=True)
    restored = SqliteOrderRepository(db)
    o2 = restored.place_order("alice", part_ids, confirmed=True)
    assert o1.id != o2.id
    # 두 주문 모두 보존.
    assert {o.id for o in restored.list_orders("alice")} == {o1.id, o2.id}


# ── 토글: build_container()가 PERSISTENCE에 따라 주문 어댑터를 주입 ────────────
def test_container_default_order_is_mock(monkeypatch):
    monkeypatch.delenv("PERSISTENCE", raising=False)
    from app.container import build_container

    c = build_container()
    assert isinstance(c.order._port, MockOrderAdapter)


def test_container_db_toggle_order_is_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE", "db")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "container.db"))
    from app.container import build_container

    c = build_container()
    assert isinstance(c.order._port, SqliteOrderRepository)
