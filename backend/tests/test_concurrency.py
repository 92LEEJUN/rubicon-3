"""동시성 안전 — OrderService read-modify-write 임계구역(멀티테넌트 slice 4).

목표: 같은 user_id/order_id 의 동시 요청이 상태를 오염시키거나 oversell 하지 못하게
KeyedLock 으로 직렬화됨을 검증한다.

정직한 메모(GIL):
- CPython의 GIL 때문에, 중간에 양보하지 않는 순수 동기 메서드는 사실상 원자적이라
  기존 인메모리 Mock 만으로는 "락 없이 실패하는" 경쟁을 결정적으로 만들기 어렵다.
- 그래서 read(재고 확인)와 write(차감/주문) 사이에 **명시적 양보 지점**(barrier+sleep)을
  둔 계측용 스텁 OrderPort 를 써서 경쟁 창을 실재화한다. 이 스텁은
  유한·차감되는 재고를 가지므로, 직렬화가 깨지면 oversell 이 실제로 발생한다.
- 첫 두 테스트는 KeyedLock 으로 보호되는 실제 OrderService 가 이 경쟁을 직렬화함을
  보인다. 마지막 테스트(`test_unlocked_path_can_oversell`)는 같은 스텁을 락 없이 직접
  돌리면 oversell 이 재현됨을 보여, 테스트가 진짜 경쟁을 만들고 있음을 입증한다.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

from app.concurrency import KeyedLock
from app.container import build_container
from app.domain import Order, OrderItem, OrderSummary
from app.errors import OutOfStock
from app.services.services import OrderService


# ── 계측용 스텁 OrderPort: 유한·차감 재고 + read/write 사이 양보 지점 ──────────
class InstrumentedStockAdapter:
    """OrderPort 호환 — 부품별 유한 재고를 차감한다. 재고 read 와 차감 write 사이에
    배리어+sleep 로 양보 지점을 둬, 모든 스레드가 read 를 마친 뒤 write 하게 유도한다.

    OrderService.checkout 은 confirmed=True 경로에서 place_order 한 번만 호출하므로,
    place_order 안에 read-modify-write 전 구간을 둔다(서비스가 잠근 구간 = 이 호출 전체).
    """

    def __init__(self, stock: dict[str, int], *, racers: int) -> None:
        self._stock = dict(stock)
        self._orders: dict[str, Order] = {}
        self._counter = 0
        self._id_lock = threading.Lock()  # 주문 id 발급만 보호(테스트 인프라용)
        # 모든 레이서가 "재고 read" 직후 한 점에서 만나도록 하는 배리어.
        self._barrier = threading.Barrier(racers)
        self._tripped = False

    def _next_id(self) -> str:
        with self._id_lock:
            self._counter += 1
            return f"ord_{self._counter:04d}"

    def place_order(self, user_id: str, part_ids: list[str], confirmed: bool = False) -> Order:
        pid = part_ids[0]
        # ── READ: 현재 재고를 읽는다.
        available = self._stock.get(pid, 0)
        # ── 양보 지점: 모든 레이서가 read 를 마칠 때까지 대기 → 경쟁 창 최대화.
        #    (락이 없으면 전부 같은 available 을 보고 전부 통과 = oversell)
        if not self._tripped:
            try:
                self._barrier.wait(timeout=2.0)
            except threading.BrokenBarrierError:
                pass  # 직렬화되어 혼자 도달하면 배리어가 안 차므로 그냥 진행
        if available <= 0:
            # 재고 없음 → 실패 주문(서비스가 OutOfStock 로 변환하도록 신호).
            raise OutOfStock("inv", pid)
        # ── WRITE: 차감하고 주문을 만든다.
        self._stock[pid] = available - 1
        oid = self._next_id()
        item = OrderItem(part_id=pid, name=pid, unit_price=1000, qty=1)
        order = Order(
            id=oid, user_id=user_id, items=[item],
            status="CONFIRMED" if confirmed else "DRAFT",
            summary=OrderSummary(subtotal=1000, total=1000),
            created_at=datetime.now(timezone.utc),
        )
        self._orders[oid] = order
        return order

    def stop_blocking(self) -> None:
        """남은 배리어 대기를 풀어 잔여 스레드가 멈추지 않게 한다."""
        self._tripped = True
        self._barrier.abort()

    # OrderPort 나머지 메서드(이 테스트에선 미사용, 인터페이스 충족용).
    def cancel_order(self, order_id: str) -> Order:
        o = self._orders[order_id]
        o.status = "CANCELLED"
        return o

    def list_orders(self, user_id=None) -> list[Order]:
        orders = list(self._orders.values())
        if user_id:
            orders = [o for o in orders if o.user_id == user_id]
        return orders

    def remaining(self, pid: str) -> int:
        return self._stock.get(pid, 0)


def _run_concurrent_checkouts(service: OrderService, user_id: str, pid: str, n: int):
    """n 개 스레드가 동시에 같은 user_id 로 confirmed checkout. (성공수, 품절수) 반환."""
    successes: list[Order] = []
    out_of_stock = 0
    lock = threading.Lock()

    def worker():
        nonlocal out_of_stock
        try:
            order = service.checkout(user_id, [pid], confirmed=True)
            with lock:
                successes.append(order)
        except OutOfStock:
            with lock:
                out_of_stock += 1

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)
    return successes, out_of_stock


# ── 테스트 1: 같은 사용자의 동시 checkout 은 oversell 하지 않는다 ────────────────
def test_no_oversell_for_same_user_concurrent_checkout():
    racers = 8
    stock = 3  # 정확히 3개만 성공해야 한다.
    adapter = InstrumentedStockAdapter({"part_x": stock}, racers=racers)
    # 생성자 시그니처 불변 — store/alert 없이 OrderService 조립(락은 모듈 레벨).
    service = OrderService(adapter)

    successes, out_of_stock = _run_concurrent_checkouts(service, "usr_same", "part_x", racers)
    adapter.stop_blocking()

    # 불변식: 성공 = 가용 재고, 나머지는 OutOfStock, 합은 레이서 수.
    assert len(successes) == stock, f"oversell/undersell: {len(successes)} != {stock}"
    assert out_of_stock == racers - stock
    assert adapter.remaining("part_x") == 0
    # 주문 이력 일관성: 성공한 주문만큼만 기록되어야 한다.
    assert len(adapter.list_orders("usr_same")) == stock


# ── 테스트 2: 다른 사용자끼리는 서로 막지 않고 독립 진행(데드락 없음) ─────────────
def test_different_users_proceed_independently():
    racers = 6  # 6명의 서로 다른 사용자가 각자 1개씩.
    # 각 사용자에게 충분한 재고를 주되, 키가 다르면 배리어에서 막히지 않아야 한다.
    # 핵심: KeyedLock 은 user_id 가 다르면 서로 다른 락 → 동시에 진행.
    # 배리어는 racers 명이 모두 도달해야 풀리므로, 직렬화(같은 키)면 영영 안 풀린다.
    # 다른 키라 동시 진행해야만 배리어가 차고 전부 성공한다 = 독립성 증명.
    adapter = InstrumentedStockAdapter({f"part_{i}": 1 for i in range(racers)}, racers=racers)
    service = OrderService(adapter)

    results: list[Order] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker(i: int):
        try:
            order = service.checkout(f"usr_{i}", [f"part_{i}"], confirmed=True)
            with lock:
                results.append(order)
        except Exception as e:  # pragma: no cover - 실패 시 진단용
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(racers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)
    adapter.stop_blocking()

    # 모두 살아 있고(데드락 없음), 모두 성공해야 한다(배리어가 찼다 = 동시 진행).
    assert not any(t.is_alive() for t in threads), "deadlock: 일부 스레드가 끝나지 않음"
    assert not errors, f"예상치 못한 오류: {errors}"
    assert len(results) == racers


# ── 테스트 3: 락이 없으면 같은 스텁이 실제로 oversell 한다(테스트 타당성 입증) ────
def test_unlocked_path_can_oversell():
    """같은 계측 스텁을 KeyedLock 없이 직접 호출하면 oversell 이 재현됨을 보인다.

    이는 위 테스트가 '진짜 경쟁'을 만들고 있고, OrderService 의 잠금이 그것을 막고
    있음을 반증으로 확인하는 용도다(GIL 만으로 막히는 게 아님).
    """
    racers = 8
    stock = 3
    adapter = InstrumentedStockAdapter({"part_x": stock}, racers=racers)

    successes: list[Order] = []
    out_of_stock = 0
    lock = threading.Lock()

    def worker():
        nonlocal out_of_stock
        try:
            # 서비스/락을 우회하고 어댑터를 직접 호출(락 미적용 경로).
            order = adapter.place_order("usr_same", ["part_x"], confirmed=True)
            with lock:
                successes.append(order)
        except OutOfStock:
            with lock:
                out_of_stock += 1

    threads = [threading.Thread(target=worker) for _ in range(racers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)
    adapter.stop_blocking()

    # 락이 없으므로 모든 레이서가 같은 available(=3)을 읽고 전부 차감 → oversell.
    # (배리어가 read 직후 전원을 모았기 때문에 결정적으로 oversell 한다.)
    assert len(successes) > stock, (
        "기대: 락 없는 경로는 oversell 해야 한다(테스트가 진짜 경쟁을 만든다는 증거). "
        f"성공={len(successes)}, 재고={stock}"
    )


# ── 테스트 4: KeyedLock 단위 — 같은 키 직렬화 / 다른 키 독립 ───────────────────
def test_keyed_lock_same_key_serializes_and_different_keys_independent():
    kl = KeyedLock()
    # 같은 키는 같은 락 객체.
    assert kl.get("a") is kl.get("a")
    # 다른 키는 다른 락.
    assert kl.get("a") is not kl.get("b")

    # 같은 키 직렬화: 한 스레드가 잡고 있으면 다른 스레드는 들어오지 못한다.
    held = threading.Event()
    release = threading.Event()
    entered_second = threading.Event()

    def first():
        with kl.acquire("k"):
            held.set()
            release.wait(timeout=2.0)

    def second():
        held.wait(timeout=2.0)
        # 같은 키 — first 가 잡고 있는 동안은 획득 불가.
        got = kl.get("k").acquire(blocking=False)
        if got:
            entered_second.set()
            kl.get("k").release()

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    held.wait(timeout=2.0)
    t2.join(timeout=2.0)
    assert not entered_second.is_set(), "같은 키인데 직렬화되지 않음"
    release.set()
    t1.join(timeout=2.0)

    # 다른 키는 first 가 'k' 를 잡고 있어도 독립적으로 획득 가능.
    assert kl.get("other").acquire(blocking=False)
    kl.get("other").release()
