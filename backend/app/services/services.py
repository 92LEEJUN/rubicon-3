"""도메인 서비스 구현.

각 서비스는 Port(Protocol)/Repository만 의존 → Mock↔실 교체에 영향받지 않는다.
의존성은 생성자 주입(테스트에서 가짜 Port 주입 가능).
"""
from __future__ import annotations

from typing import Optional

from ..concurrency import KeyedLock
from ..domain import (
    Anomaly,
    Booking,
    BookingSlot,
    Device,
    DeviceStatusResult,
    Order,
    Product,
    Quote,
    Solution,
    SolutionSearchResult,
    Store,
    User,
)
from ..errors import (
    ConfirmationRequired,
    OutOfStock,
    PickupTransitionError,
    QuoteExpired,
    QuoteForbidden,
    QuoteNotConvertible,
)
from ..ports import (
    CatalogPort,
    CSKnowledgePort,
    DevicePort,
    HandoffPort,
    OrderPort,
    QuotePort,
    StorePort,
    WarrantyPort,
)
from ..repositories import InMemoryEngagementRepository


class DeviceService:
    """기기 상태 조회 + 이상/임계치 판정(design §6.3, R2·R5)."""

    def __init__(self, device_port: DevicePort) -> None:
        self._port = device_port

    def list_devices(self) -> list[Device]:
        return self._port.list_devices()

    def get_status(self, device_query: str) -> DeviceStatusResult:
        return self._port.get_status(device_query)

    def consumable_alerts(self, device: Device) -> list[Anomaly]:
        """소모품 수명이 임계치 이하인 항목을 이상으로 판정(선제안 트리거)."""
        alerts = []
        for c in device.consumables:
            if c.needs_replacement:
                alerts.append(Anomaly(
                    id=f"alert_{device.id}_{c.name}",
                    device_id=device.id,
                    type="consumable",
                    severity="warning" if c.life_remaining <= c.threshold * 0.75 else "info",
                    detail=f"{c.name} 수명 {int(c.life_remaining * 100)}% 남음(임계치 {int(c.threshold * 100)}%).",
                ))
        return alerts


class KnowledgeService:
    """CS 해결 가이드 + 보증(유·무상) 판정(R3·R16·R22)."""

    def __init__(self, cs_port: CSKnowledgePort, warranty_port: Optional[WarrantyPort] = None) -> None:
        self._cs = cs_port
        self._warranty = warranty_port

    def find_solutions(self, query: str, error_code: Optional[str] = None) -> SolutionSearchResult:
        return self._cs.find_solutions(query, error_code)

    def best_solution(self, query: str, error_code: Optional[str] = None) -> Optional[Solution]:
        res = self._cs.find_solutions(query, error_code)
        return res.solutions[0] if res.solutions else None


class CatalogService:
    """부품 매칭 + 개인화 추천(R4·R8). 이미 본 추천은 Engagement로 억제(R29)."""

    def __init__(self, catalog_port: CatalogPort,
                 engagement: Optional[InMemoryEngagementRepository] = None) -> None:
        self._port = catalog_port
        self._engagement = engagement

    def match_parts(self, device_model: Optional[str] = None,
                    part_ids: Optional[list[str]] = None):
        return self._port.match_parts(device_model, part_ids)

    def recommend(self, user: User) -> list[Product]:
        recs = self._port.recommend(user.preferences.interest_categories)
        if self._engagement:  # 이미 본/무시한 추천 억제
            recs = [p for p in recs if not self._engagement.has_seen(user.id, p.id)]
        return recs


# 동시성 게이트(멀티테넌트 slice 4) — 같은 키의 read-modify-write 임계구역을 직렬화한다.
# 생성자 시그니처를 바꾸지 않도록 모듈 레벨 인스턴스로 둔다(container.py 소유 불변).
# checkout/checkout_pickup 은 user_id 로, advance_pickup 은 order_id 로 키잉한다.
_ORDER_LOCKS = KeyedLock()


# 픽업 라이프사이클 허용 전이(O3-6) — RESERVED→READY→PICKED_UP | (RESERVED|READY)→EXPIRED
_PICKUP_TRANSITIONS: dict[Optional[str], set[str]] = {
    "RESERVED": {"READY", "EXPIRED"},
    "READY": {"PICKED_UP", "EXPIRED"},
    "PICKED_UP": set(),
    "EXPIRED": set(),
}


class OrderService:
    """장바구니/주문 — 커밋 게이트(R17)·금액 분해·취소(R21)·픽업(BOPIS)·견적 전환(O3·O4·O6).

    픽업 재고 게이트(O2)·견적 검증(O5·O6)은 StoreService와 협력한다(선택 주입).
    """

    def __init__(self, order_port: OrderPort,
                 store_service: Optional["StoreService"] = None,
                 alert_port: Optional[object] = None) -> None:
        self._port = order_port
        self._store = store_service
        self._alert = alert_port

    def checkout(self, user_id: str, part_ids: list[str], confirmed: bool = False) -> Order:
        """확인 없이 호출되면 DRAFT를 만들어 ConfirmationRequired로 게이트한다(R17).

        동시성(slice 4): 같은 user_id 의 동시 커밋을 직렬화해 재고 read-modify-write
        경쟁/oversell을 막는다. 다른 user_id 끼리는 독립적으로 진행한다.
        """
        with _ORDER_LOCKS.acquire(user_id):
            if not confirmed:
                draft = self._port.place_order(user_id, part_ids, confirmed=False)
                raise ConfirmationRequired(draft)
            return self._port.place_order(user_id, part_ids, confirmed=True)

    # ── 픽업(BOPIS) 라이프사이클 (O3·O4) ────────────────────────────────────
    def checkout_pickup(self, user_id: str, part_ids: list[str], store_id: str,
                        confirmed: bool = False) -> Order:
        """픽업 주문 — 생성 전 재고 게이트(O2), 확정 직전 확인(R17), RESERVED 시작(O3-1).

        동시성(slice 4): 재고 확인(read)부터 주문 생성(write)까지를 user_id 키로
        직렬화해, 같은 사용자의 동시 픽업 커밋이 같은 재고를 중복 점유하지 못하게 한다.
        """
        with _ORDER_LOCKS.acquire(user_id):
            if self._store is not None:
                for pid in part_ids:
                    if not self._store.check_stock(store_id, pid):
                        raise OutOfStock(store_id, pid)
            if not confirmed:
                draft = self._port.place_pickup_order(user_id, part_ids, store_id, confirmed=False)
                raise ConfirmationRequired(draft, "픽업 주문 확인이 필요합니다.")
            return self._port.place_pickup_order(user_id, part_ids, store_id, confirmed=True)

    def advance_pickup(self, order_id: str, action: str) -> Order:
        """픽업 상태 전이 — `ready`/`picked_up`/`expired`. 정의된 전이만 허용(O3-6).

        `READY` 전이 시 준비완료 선제 알림(O3-3·R20). `EXPIRED`는 취소/환불(R21) 연계(O4).
        """
        target = {"ready": "READY", "picked_up": "PICKED_UP", "expired": "EXPIRED"}.get(action)
        # 동시성(slice 4): 같은 order_id 의 상태 read-modify-write 를 직렬화한다.
        # 두 전이가 같은 현재상태를 읽고 둘 다 통과시키는(이중 전이) 경쟁을 막는다.
        with _ORDER_LOCKS.acquire(order_id):
            order = self._port.get_order(order_id)
            if order is None:
                raise KeyError(order_id)
            current = order.pickup_status
            if target is None or target not in _PICKUP_TRANSITIONS.get(current, set()):
                raise PickupTransitionError(current, target or action)
            updated = self._port.update_pickup_status(order_id, target)
            if target == "READY" and self._alert is not None:
                try:
                    self._alert.deliver(order.user_id, "pickup_ready",
                                        f"{order_id} 픽업 준비가 완료되었습니다.", ref=order_id)
                except Exception:
                    pass  # 알림 실패는 흐름을 막지 않는다(R13)
            if target == "EXPIRED":
                # 미수령 만료 → 취소/환불 경로(R21) 연계(O4-2).
                self._port.refund_order(order_id)
                updated = self._port.get_order(order_id) or updated
            return updated

    # ── 견적 → 주문 전환 (O6) ───────────────────────────────────────────────
    def convert_quote(self, quote: Quote, confirmed: bool = False,
                      fulfillment: str = "delivery", store_id: Optional[str] = None) -> Order:
        """ACTIVE 견적만 전환(O6-2). 확인(R17) 후 주문 생성. 전환 주문도 배송/픽업 선택(O6-4).

        견적 본인·만료·현재가 검증은 StoreService.get_quote_for_conversion 이 선행한다.
        """
        if quote.status != "ACTIVE":
            raise QuoteNotConvertible(quote.status)
        part_ids = [i.part_id for i in quote.items]
        if fulfillment == "pickup":
            if store_id is None:
                store_id = quote.store_id
            order = self.checkout_pickup(quote.user_id, part_ids, store_id or "", confirmed=confirmed)
        else:
            order = self.checkout(quote.user_id, part_ids, confirmed=confirmed)
        # 전환 성공 시 견적을 CONVERTED로 표시(상태 영속은 QuotePort 실 전환 시; Mock은 복제 반환).
        quote.status = "CONVERTED"
        return order

    def cancel(self, order_id: str) -> Order:
        return self._port.cancel_order(order_id)

    def get(self, order_id: str) -> Optional[Order]:
        return self._port.get_order(order_id)

    def history(self, user_id: Optional[str] = None) -> list[Order]:
        """주문 이력(최신순) — 진행 추적(status_tracker)·홈/CS 노출용."""
        return self._port.list_orders(user_id)


class HandoffService:
    """방문/상담 핸드오프 — 슬롯·예약(R18)."""

    def __init__(self, handoff_port: HandoffPort) -> None:
        self._port = handoff_port

    def list_slots(self, visit_type: str = "REPAIR") -> list[BookingSlot]:
        return self._port.list_slots(visit_type)

    def book(self, slot_id: str, context_ref: Optional[str] = None,
             visit_type: str = "REPAIR", store_id: Optional[str] = None) -> Booking:
        """방문 예약 — 센터 방문(O7-4)은 visit_type/store_id로 거점 동반, 맥락 전달(O7-5)."""
        return self._port.book_slot(slot_id, context_ref, visit_type=visit_type, store_id=store_id)

    def list_bookings(self) -> list[Booking]:
        """예약 이력 — 홈/CS '진행 중' 노출용(R18)."""
        return self._port.list_bookings()


class NotificationService:
    """선제 알림(R5·R20·R26·R29) — 임계치 감지 → 동의·중복 게이트 통과분만 전달.

    architecture.md §10 선제 파이프라인의 도메인 부분(전달 채널 AlertPort는 BFF/실).
    """

    def __init__(self, device_service: DeviceService,
                 engagement: InMemoryEngagementRepository) -> None:
        self._devices = device_service
        self._engagement = engagement

    def pending_alerts(self, user: User) -> list[Anomaly]:
        """opt-in + 동의 + 미열람(중복 억제)을 통과한 소모품 이상만 반환."""
        if not user.preferences.notify_opt_in or "device_data" not in user.consent.scopes:
            return []
        alerts: list[Anomaly] = []
        for device in self._devices.list_devices():
            if device.id not in user.linked_device_ids:
                continue
            for a in self._devices.consumable_alerts(device):
                if not self._engagement.has_seen(user.id, a.id):
                    alerts.append(a)
        # 심각도 우선순위 정렬(R27): critical > warning > info
        order = {"critical": 0, "warning": 1, "info": 2}
        return sorted(alerts, key=lambda a: order.get(a.severity, 9))


class StoreService:
    """거점·재고·견적 이어보기 — StorePort·QuotePort 조합(O1·O2·O5·O8).

    실패/미연동은 폴백(빈 결과/None)으로 흡수해 흐름을 막지 않는다(O8-1·R13).
    """

    def __init__(self, store_port: StorePort, quote_port: QuotePort,
                 catalog_port: Optional[CatalogPort] = None) -> None:
        self._store = store_port
        self._quote = quote_port
        self._catalog = catalog_port

    # ── 거점 조회 (O1) ──────────────────────────────────────────────────────
    def find_stores(self, geo: Optional[tuple[float, float]] = None,
                    store_type: Optional[str] = None) -> list[Store]:
        """위치 기반 거점 조회 + 유형 필터(O1-1·O1-2). 위치 없으면 전체 반환(O1-3 폴백)."""
        try:
            return self._store.find_stores(geo, store_type)
        except Exception:
            return []  # StorePort 실패 → 빈 결과 폴백(O8-1)

    # ── 픽업 재고 (O2) ──────────────────────────────────────────────────────
    def check_stock(self, store_id: str, part_id: str) -> bool:
        try:
            return self._store.check_stock(store_id, part_id)
        except Exception:
            return False  # 재고 확인 실패 → 보수적으로 없음 처리(임의 진행 금지)

    def stores_with_stock(self, part_id: str,
                          geo: Optional[tuple[float, float]] = None) -> list[Store]:
        """재고 있는 대체 매장 목록(O2-2·O4-3) — 재고 없음 시 사용자 선택지 제시."""
        return [s for s in self.find_stores(geo) if self.check_stock(s.id, part_id)]

    # ── 견적 이어보기 (O5) ──────────────────────────────────────────────────
    def _current_price(self, part_id: str) -> Optional[int]:
        if self._catalog is None:
            return None
        res = self._catalog.match_parts(part_ids=[part_id])
        return res.parts[0].price if res.parts else None

    def get_quote(self, quote_ref: str, user_id: str, *, now=None) -> Quote:
        """견적 조회 — 본인 확인(O5-2)·만료 검증(O5-3). 미발견/실패는 None 폴백 후 KeyError."""
        from datetime import datetime, timezone
        now = now or datetime.now(timezone.utc)
        try:
            quote = self._quote.get_quote(quote_ref)
        except Exception:
            quote = None
        if quote is None:
            raise KeyError(quote_ref)  # 미발견 — API는 404/재견적 안내(O8-1)
        if quote.user_id != user_id:
            raise QuoteForbidden()  # 본인 아님(O5-2)
        if quote.expires_at is not None and quote.expires_at <= now:
            raise QuoteExpired()  # 만료(O5-3)
        if quote.status == "EXPIRED":
            raise QuoteExpired()
        return quote

    def price_changes(self, quote: Quote) -> list[dict]:
        """전환/표시 시 현재가·재고 변동 검증(O5-4·O6-3) — 차이 목록 반환(없으면 빈 리스트)."""
        changes: list[dict] = []
        for item in quote.items:
            current = self._current_price(item.part_id)
            if current is not None and current != item.unit_price:
                changes.append({"part_id": item.part_id, "quoted": item.unit_price,
                                "current": current})
        return changes


# 트리아지 결정 결과 — self(셀프) / repair(기사 방문) / center(센터 방문) / agent(상담원)
TriagePath = str


class TriageService:
    """서비스 트리아지 — self/기사/센터/상담원 경로 결정(O7).

    하이브리드(design §7.4): 안전(R23)·셀프 부적절은 규칙으로 강제, 불확실은 상담원.
    """

    def __init__(self, warranty_port: Optional[WarrantyPort] = None) -> None:
        self._warranty = warranty_port

    def decide(self, solution: Optional[Solution], *, uncertain: bool = False) -> dict:
        """진단 결과(Solution)로 경로를 판단(O7-1·O7-2·O7-6).

        반환: {"path", "reason", "coverage"}. path ∈ {self, repair, center, agent}.
        """
        if uncertain or solution is None:
            return {"path": "agent", "reason": "트리아지 불확실 — 상담원 연결", "coverage": "unknown"}

        coverage = solution.coverage if solution.coverage != "unknown" else "unknown"
        # 위험·전문 필요 단계가 있으면 셀프 차단 → 기사/센터 우선(O7-2·R23)
        danger = any(s.safety == "danger" for s in solution.steps)
        pro = any(s.pro_required for s in solution.steps)
        if solution.escalation_needed or danger:
            return {"path": "center", "reason": "위험·전문 작업 — 센터 방문 우선", "coverage": coverage}
        if pro:
            return {"path": "repair", "reason": "전문 수리 필요 — 기사 방문 안내", "coverage": coverage}
        return {"path": "self", "reason": "셀프 해결 가능", "coverage": coverage}
