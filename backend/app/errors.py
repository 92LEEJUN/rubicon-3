"""도메인 예외 — API 계층에서 계약(폴백·게이트)으로 정규화한다(api-contract.md §4)."""
from __future__ import annotations

from .domain import Order


class ConfirmationRequired(Exception):
    """되돌릴 수 없는 커밋(R17) 전 확인 게이트. API는 409 + confirmation 템플릿으로 변환."""

    def __init__(self, draft: Order, message: str = "주문 확인이 필요합니다.") -> None:
        super().__init__(message)
        self.draft = draft
        self.message = message
