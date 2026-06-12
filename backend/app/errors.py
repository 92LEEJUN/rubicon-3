"""도메인 예외 — API 계층에서 계약(폴백·게이트)으로 정규화한다(api-contract.md §4)."""
from __future__ import annotations

from typing import Optional

from .domain import Order


class ConfirmationRequired(Exception):
    """되돌릴 수 없는 커밋(R17) 전 확인 게이트. API는 409 + confirmation 템플릿으로 변환."""

    def __init__(self, draft: Order, message: str = "주문 확인이 필요합니다.") -> None:
        super().__init__(message)
        self.draft = draft
        self.message = message


# ── O2O 도메인 예외 ──────────────────────────────────────────────────────────
class OutOfStock(Exception):
    """선택 매장에 픽업 재고 없음(O2-2·O2-3). API는 409 — 대체 매장/배송 제안."""

    def __init__(self, store_id: str, part_id: str,
                 message: str = "선택한 매장에 재고가 없습니다.") -> None:
        super().__init__(message)
        self.store_id = store_id
        self.part_id = part_id
        self.message = message


class PickupTransitionError(Exception):
    """픽업 상태 역전이/잘못된 전이(O3-6). API는 409 — 현재 상태 안내."""

    def __init__(self, current: Optional[str], requested: str,
                 message: Optional[str] = None) -> None:
        message = message or f"픽업 상태를 {current}→{requested} 로 전이할 수 없습니다."
        super().__init__(message)
        self.current = current
        self.requested = requested
        self.message = message


class QuoteForbidden(Exception):
    """본인 견적이 아님(O5-2). API는 403."""

    def __init__(self, message: str = "본인의 견적만 조회할 수 있습니다.") -> None:
        super().__init__(message)
        self.message = message


class QuoteExpired(Exception):
    """견적 만료(O5-3). API는 410 — 재견적 안내."""

    def __init__(self, message: str = "견적이 만료되었습니다. 재견적이 필요합니다.") -> None:
        super().__init__(message)
        self.message = message


class QuoteNotConvertible(Exception):
    """ACTIVE 가 아닌 견적 전환 시도(O6-2). API는 409 — 사유 안내."""

    def __init__(self, status: str,
                 message: str = "활성(ACTIVE) 견적만 주문으로 전환할 수 있습니다.") -> None:
        super().__init__(message)
        self.status = status
        self.message = message
