"""도메인 서비스 구현.

각 서비스는 Port(Protocol)/Repository만 의존 → Mock↔실 교체에 영향받지 않는다.
의존성은 생성자 주입(테스트에서 가짜 Port 주입 가능).
"""
from __future__ import annotations

from typing import Optional

from ..domain import (
    Anomaly,
    Booking,
    BookingSlot,
    Device,
    DeviceStatusResult,
    Order,
    Product,
    Solution,
    SolutionSearchResult,
    User,
)
from ..errors import ConfirmationRequired
from ..ports import (
    CatalogPort,
    CSKnowledgePort,
    DevicePort,
    HandoffPort,
    OrderPort,
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


class OrderService:
    """장바구니/주문 — 커밋 게이트(R17)·금액 분해·취소(R21)."""

    def __init__(self, order_port: OrderPort) -> None:
        self._port = order_port

    def checkout(self, user_id: str, part_ids: list[str], confirmed: bool = False) -> Order:
        """확인 없이 호출되면 DRAFT를 만들어 ConfirmationRequired로 게이트한다(R17)."""
        if not confirmed:
            draft = self._port.place_order(user_id, part_ids, confirmed=False)
            raise ConfirmationRequired(draft)
        return self._port.place_order(user_id, part_ids, confirmed=True)

    def cancel(self, order_id: str) -> Order:
        return self._port.cancel_order(order_id)

    def history(self, user_id: Optional[str] = None) -> list[Order]:
        """주문 이력(최신순) — 진행 추적(status_tracker)·홈/CS 노출용."""
        return self._port.list_orders(user_id)


class HandoffService:
    """방문/상담 핸드오프 — 슬롯·예약(R18)."""

    def __init__(self, handoff_port: HandoffPort) -> None:
        self._port = handoff_port

    def list_slots(self, visit_type: str = "REPAIR") -> list[BookingSlot]:
        return self._port.list_slots(visit_type)

    def book(self, slot_id: str, context_ref: Optional[str] = None) -> Booking:
        return self._port.book_slot(slot_id, context_ref)

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
