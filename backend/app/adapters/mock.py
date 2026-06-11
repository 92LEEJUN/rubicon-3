"""Mock 어댑터 — Port의 MVP 구현(fixtures 반환, 타입 변환 = ACL 역할).

실 전환 시 동일 Port를 SmartThings/CS/제품/O2O Real 어댑터로 교체한다(시그니처 불변).
검색은 데모용 동의어/코드 매칭 — 실 전환 시 벡터 임베딩 유사도로 대체.
"""
from __future__ import annotations

import itertools
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from .. import fixtures as fx
from ..domain import (
    Anomaly,
    Booking,
    BookingSlot,
    Coverage,
    Device,
    DeviceStatusResult,
    Order,
    OrderItem,
    OrderSummary,
    Part,
    PartMatchResult,
    Product,
    Solution,
    SolutionSearchResult,
)

# 한국어 별칭 매핑(데모용)
_ALIAS = {"세탁기": "washer", "냉장고": "refrigerator", "공기청정기": "air_purifier"}

# 데모용 증상 동의어(실 전환 시 벡터 검색으로 대체)
_SYN = {
    "sol_washer_5c": ["배수", "물", "빠", "안빠", "드레인", "drain", "세탁", "5c"],
    "sol_fridge_filter": ["정수", "필터", "냉장", "물맛", "교체", "filter"],
}


def _devices() -> list[Device]:
    return [Device.model_validate(d) for d in fx.DEVICES]


def _anomalies() -> list[Anomaly]:
    return [Anomaly.model_validate(a) for a in fx.ANOMALIES]


def _solutions() -> list[Solution]:
    return [Solution.model_validate(s) for s in fx.SOLUTIONS]


def _parts() -> list[Part]:
    return [Part.model_validate(p) for p in fx.PARTS]


def _products() -> list[Product]:
    return [Product.model_validate(p) for p in fx.PRODUCTS]


class MockDeviceAdapter:
    """DevicePort — SmartThings Mock."""

    def list_devices(self) -> list[Device]:
        return _devices()

    def get_status(self, device_query: str) -> DeviceStatusResult:
        q = (device_query or "").lower()
        devices = _devices()
        dev = next(
            (d for d in devices
             if q and (q in d.id.lower() or q in d.type.lower() or q in d.model.lower())),
            None,
        )
        if not dev:  # 한국어 별칭
            for k, v in _ALIAS.items():
                if k in (device_query or ""):
                    dev = next((d for d in devices if d.type == v), None)
                    break
        if not dev:
            return DeviceStatusResult(found=False, message="해당 기기를 찾지 못했습니다(미연동 가능).")
        anomalies = [a for a in _anomalies() if a.device_id == dev.id]
        return DeviceStatusResult(found=True, device=dev, anomalies=anomalies)


class MockCSKnowledgeAdapter:
    """CSKnowledgePort — 오류코드 정확 매칭(키) + 자유 증상 키워드(하이브리드)."""

    def find_solutions(self, query: str, error_code: Optional[str] = None) -> SolutionSearchResult:
        code = (error_code or "").strip().upper()
        if not code:  # 질의에서 코드 추출(예: "5C")
            m = re.search(r"\b([0-9][A-Z]|[A-Z][0-9])\b", (query or "").upper())
            code = m.group(1) if m else ""
        q = query or ""

        results: list[Solution] = []
        anomalies = {a.id: a for a in _anomalies()}
        for sol in _solutions():
            ano = anomalies.get(sol.anomaly_id)
            detail = (ano.detail if ano else "") + " " + " ".join(s.instruction for s in sol.steps)
            keywords = _SYN.get(sol.id, [])
            if code and code in detail.upper():
                results.append(sol)
            elif q and (any(k in q for k in keywords)
                        or any(w in detail for w in q.split() if len(w) > 1)):
                results.append(sol)
        return SolutionSearchResult(count=len(results), solutions=results)


class MockCatalogAdapter:
    """CatalogPort — demand-driven 매칭/추천(브라우즈 없음)."""

    def match_parts(
        self, device_model: Optional[str] = None, part_ids: Optional[list[str]] = None
    ) -> PartMatchResult:
        parts = _parts()
        if part_ids:
            matched = [p for p in parts if p.id in part_ids]
        elif device_model:
            matched = [p for p in parts if device_model.lower() in p.device_model.lower()]
        else:
            matched = []
        return PartMatchResult(count=len(matched), parts=matched)

    def recommend(self, categories: list[str]) -> list[Product]:
        cats = {c.lower() for c in categories}
        return [p for p in _products() if p.category.lower() in cats and p.in_stock]


# 배송/금액 정책(데모) — 실 전환 시 OrderPort 실 연동으로 대체
_FREE_SHIPPING_THRESHOLD = 30_000
_SHIPPING_FEE = 3_000


def _summarize(items: list[OrderItem]) -> OrderSummary:
    subtotal = sum(i.line_total for i in items)
    shipping = 0 if subtotal == 0 or subtotal >= _FREE_SHIPPING_THRESHOLD else _SHIPPING_FEE
    return OrderSummary(subtotal=subtotal, shipping_fee=shipping, tax=0, discount=0,
                        total=subtotal + shipping)


class MockOrderAdapter:
    """OrderPort — O2O 주문 Mock(성공/실패/취소 시뮬레이션, R21).

    품절 부품은 주문 실패(FAILED)로 처리해 부분 실패(R13)를 표현한다.
    """

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._ids = itertools.count(1)

    def place_order(self, user_id: str, part_ids: list[str], confirmed: bool = False) -> Order:
        catalog = {p.id: p for p in _parts()}
        items, out_of_stock = [], []
        for pid in part_ids:
            part = catalog.get(pid)
            if part is None:
                continue
            if not part.in_stock:
                out_of_stock.append(pid)
                continue
            items.append(OrderItem(part_id=part.id, name=part.name, unit_price=part.price, qty=1))

        oid = f"ord_{next(self._ids):04d}"
        status = "DRAFT"
        if out_of_stock and not items:
            status = "FAILED"
        elif confirmed and items:
            status = "CONFIRMED"
        order = Order(id=oid, user_id=user_id, items=items, status=status,
                      summary=_summarize(items), created_at=datetime.now(timezone.utc))
        self._orders[oid] = order
        return order

    def cancel_order(self, order_id: str) -> Order:
        order = self._orders[order_id]
        order.status = "CANCELLED"
        return order


class MockHandoffAdapter:
    """HandoffPort — 방문 예약 슬롯/예약 Mock(R18)."""

    def __init__(self) -> None:
        self._bookings: dict[str, Booking] = {}
        self._ids = itertools.count(1)

    def list_slots(self, visit_type: str = "REPAIR") -> list[BookingSlot]:
        base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        slots = []
        for day, hour in [(1, 10), (1, 14), (2, 10)]:
            start = base + timedelta(days=day, hours=hour - base.hour)
            slots.append(BookingSlot(id=f"slot_{day}_{hour}", start=start,
                                     end=start + timedelta(hours=2), visit_type=visit_type))
        return slots

    def book_slot(self, slot_id: str, context_ref: Optional[str] = None) -> Booking:
        bid = f"bk_{next(self._ids):04d}"
        booking = Booking(id=bid, slot_id=slot_id, status="CONFIRMED", context_ref=context_ref)
        self._bookings[bid] = booking
        return booking


class MockWarrantyAdapter:
    """WarrantyPort — 샘플 보증 규칙(R22). 해결책 coverage를 우선 사용."""

    def coverage(self, device_model: str, part_id: Optional[str] = None) -> Coverage:
        for sol in _solutions():
            if part_id and part_id in sol.required_parts and sol.coverage != "unknown":
                return sol.coverage
        return "unknown"
