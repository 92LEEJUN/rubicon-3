"""의존성 컨테이너 — Mock 어댑터/Repository로 서비스를 조립(MVP 와이어링).

실 전환 시 여기서 Mock→Real 어댑터만 바꾸면 서비스/오케스트레이터는 불변(architecture.md §5).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import fixtures as fx
from .adapters import mock
from .companion import CompanionService
from .compaction import CompactionService, RuleBasedCompactor
from .domain import User
from .repositories import (
    InMemoryConversationMemoryRepository,
    InMemoryConversationStore,
    InMemoryEngagementRepository,
)
from .services import (
    CatalogService,
    DeviceService,
    HandoffService,
    KnowledgeService,
    NotificationService,
    OrderService,
)


@dataclass
class Container:
    user: User
    engagement: InMemoryEngagementRepository
    conversation_memory: InMemoryConversationMemoryRepository
    compaction: CompactionService
    companion: CompanionService
    device: DeviceService
    knowledge: KnowledgeService
    catalog: CatalogService
    order: OrderService
    handoff: HandoffService
    notification: NotificationService


def build_container() -> Container:
    engagement = InMemoryEngagementRepository()
    conversation_memory = InMemoryConversationMemoryRepository()
    conversation_store = InMemoryConversationStore()
    # MVP=결정적 컴팩터(LLM 없이 테스트 가능). 실 전환 시 LLMCompactor로 교체(ADR-0020).
    compaction = CompactionService(RuleBasedCompactor())
    companion = CompanionService(conversation_memory, conversation_store, compaction)
    device = DeviceService(mock.MockDeviceAdapter())
    knowledge = KnowledgeService(mock.MockCSKnowledgeAdapter(), mock.MockWarrantyAdapter())
    catalog = CatalogService(mock.MockCatalogAdapter(), engagement)
    order = OrderService(mock.MockOrderAdapter())
    handoff = HandoffService(mock.MockHandoffAdapter())
    notification = NotificationService(device, engagement)
    return Container(
        user=User.model_validate(fx.USER),
        engagement=engagement,
        conversation_memory=conversation_memory,
        compaction=compaction,
        companion=companion,
        device=device,
        knowledge=knowledge,
        catalog=catalog,
        order=order,
        handoff=handoff,
        notification=notification,
    )
