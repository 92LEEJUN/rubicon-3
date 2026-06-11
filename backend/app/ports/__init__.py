"""Port 인터페이스 — Mock↔실 교체 경계(architecture.md §5, data-model.md §6).

도메인 서비스는 이 Protocol에만 의존한다. Mock(adapters.mock)·실(adapters.real) 구현을 주입한다.
"""
from .base import (  # noqa: F401
    CatalogPort,
    CSKnowledgePort,
    DevicePort,
    HandoffPort,
    OrderPort,
    WarrantyPort,
)
