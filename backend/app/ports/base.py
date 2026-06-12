"""Port Protocol 정의 — 시그니처·타입은 고정, 구현(Mock/실)은 교체.

외부 시스템 추상화:
  DevicePort      ← SmartThings (기기 상태·이상)
  CSKnowledgePort ← Samsung CS (해결 가이드, 하이브리드 검색)
  CatalogPort     ← 제품/부품 (demand-driven 매칭·추천)
  OrderPort       ← O2O 주문 (성공/실패/취소 시뮬레이션, R21)
  HandoffPort     ← 방문/상담 (슬롯·예약, R18)
  WarrantyPort    ← 보증 (유·무상 판정, R22)
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..domain import (
    Booking,
    BookingSlot,
    Coverage,
    Cta,
    DeviceStatusResult,
    Order,
    PartMatchResult,
    Product,
    Quote,
    SolutionSearchResult,
    Store,
)
from ..domain.models import Device, StoreType


@runtime_checkable
class DevicePort(Protocol):
    def list_devices(self) -> list[Device]: ...
    def get_status(self, device_query: str) -> DeviceStatusResult: ...


@runtime_checkable
class CSKnowledgePort(Protocol):
    def find_solutions(self, query: str, error_code: Optional[str] = None) -> SolutionSearchResult: ...


@runtime_checkable
class CatalogPort(Protocol):
    def match_parts(
        self, device_model: Optional[str] = None, part_ids: Optional[list[str]] = None
    ) -> PartMatchResult: ...
    def recommend(self, categories: list[str]) -> list[Product]: ...


@runtime_checkable
class OrderPort(Protocol):
    def place_order(self, user_id: str, part_ids: list[str], confirmed: bool = False) -> Order: ...
    def cancel_order(self, order_id: str) -> Order: ...
    def list_orders(self, user_id: Optional[str] = None) -> list[Order]: ...


@runtime_checkable
class HandoffPort(Protocol):
    def list_slots(self, visit_type: str = "REPAIR") -> list[BookingSlot]: ...
    def book_slot(
        self, slot_id: str, context_ref: Optional[str] = None,
        visit_type: str = "REPAIR", store_id: Optional[str] = None,
    ) -> Booking: ...
    def list_bookings(self) -> list[Booking]: ...


@runtime_checkable
class WarrantyPort(Protocol):
    def coverage(self, device_model: str, part_id: Optional[str] = None) -> Coverage: ...


@runtime_checkable
class StorePort(Protocol):
    """O2O 거점·재고(위치 기반). MVP: 후속/Mock(data-model.md §6)."""
    def find_stores(
        self, geo: Optional[tuple[float, float]] = None, store_type: Optional[StoreType] = None
    ) -> list[Store]: ...
    def check_stock(self, store_id: str, part_id: str) -> bool: ...


@runtime_checkable
class QuotePort(Protocol):
    """O2O 견적 이어보기(reverse). MVP: 후속/Mock(data-model.md §6)."""
    def get_quote(self, quote_ref: str) -> Optional[Quote]: ...


@runtime_checkable
class ActionGatePort(Protocol):
    """R17 확인 UX 실/처리 Mock(ADR-0033). 되돌릴 수 없는 커밋의 확인 필요 여부 판정."""
    def requires_confirmation(self, cta: Cta) -> bool: ...
