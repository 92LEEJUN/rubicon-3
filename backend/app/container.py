"""의존성 컨테이너 — Mock 어댑터/Repository로 서비스를 조립(MVP 와이어링).

실 전환 시 여기서 Mock→Real 어댑터만 바꾸면 서비스/오케스트레이터는 불변(architecture.md §5).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from . import fixtures as fx
from .adapters import mock
from .companion import CompanionService
from .compaction import CompactionService, RuleBasedCompactor
from .domain import User
from .recommendation import RecommendationService
from .reengagement import ReEngagementService
from .repositories import (
    InMemoryConversationMemoryRepository,
    InMemoryConversationStore,
    InMemoryEngagementRepository,
    InMemoryOpenLoopRepository,
)
from .repositories.sqlite import (
    SqliteConversationMemoryRepository,
    SqliteEngagementRepository,
    SqliteOpenLoopRepository,
    SqliteOrderRepository,
)
from .services import (
    CatalogService,
    DeviceService,
    HandoffService,
    KnowledgeService,
    NotificationService,
    OrderService,
    StoreService,
    TriageService,
)


@dataclass
class Container:
    user: User
    # 타입은 인메모리 기준 표기(PERSISTENCE=db면 동일 시그니처의 Sqlite* 구현이 주입됨 — duck-typed).
    engagement: InMemoryEngagementRepository | SqliteEngagementRepository
    conversation_memory: InMemoryConversationMemoryRepository | SqliteConversationMemoryRepository
    compaction: CompactionService
    companion: CompanionService
    reengagement: ReEngagementService
    recommendation: RecommendationService
    device: DeviceService
    knowledge: KnowledgeService
    catalog: CatalogService
    order: OrderService
    handoff: HandoffService
    notification: NotificationService
    store: StoreService            # O2O — 거점·재고·견적(O1·O2·O5)
    triage: TriageService          # O2O — 서비스 트리아지(O7)


def build_container() -> Container:
    # PERSISTENCE 토글(기본 memory=기존 동작). db면 user-키 Repository만 sqlite로 교체.
    # 나머지 와이어링은 불변 — Sqlite 구현이 인메모리와 동일 시그니처라 duck-typed로 합성된다.
    if os.environ.get("PERSISTENCE", "memory").lower() == "db":
        db_path = os.environ.get("SQLITE_PATH", "rubicon.db")
        engagement = SqliteEngagementRepository(db_path)
        conversation_memory = SqliteConversationMemoryRepository(db_path)
        open_loops = SqliteOpenLoopRepository(db_path)
        order_adapter = SqliteOrderRepository(db_path)
    else:
        engagement = InMemoryEngagementRepository()
        conversation_memory = InMemoryConversationMemoryRepository()
        open_loops = InMemoryOpenLoopRepository()
        order_adapter = mock.MockOrderAdapter()
    # ConversationStore(워킹 메시지·TTL성)는 이번 slice 영속 대상 아님 — 인메모리 유지.
    conversation_store = InMemoryConversationStore()
    # MVP=결정적 컴팩터(LLM 없이 테스트 가능). 실 전환 시 LLMCompactor로 교체(ADR-0020).
    compaction = CompactionService(RuleBasedCompactor())
    companion = CompanionService(conversation_memory, conversation_store, compaction, open_loops)
    reengagement = ReEngagementService(companion, engagement)
    device = DeviceService(mock.MockDeviceAdapter())
    warranty_adapter = mock.MockWarrantyAdapter()
    knowledge = KnowledgeService(mock.MockCSKnowledgeAdapter(), warranty_adapter)
    catalog_adapter = mock.MockCatalogAdapter()
    catalog = CatalogService(catalog_adapter, engagement)
    # O2O — StoreService(거점·재고·견적), 픽업 알림(AlertPort), 픽업 게이트는 OrderService와 협력.
    store = StoreService(mock.MockStoreAdapter(), mock.MockQuoteAdapter(), catalog_adapter)
    alert = mock.MockAlertAdapter()
    order = OrderService(order_adapter, store_service=store, alert_port=alert)
    handoff = HandoffService(mock.MockHandoffAdapter())
    notification = NotificationService(device, engagement)
    triage = TriageService(warranty_adapter)
    # 추천 코어 — CatalogPort·Engagement·DeviceService만 의존(선제는 컴패니언 게이트 재사용).
    recommendation = RecommendationService(catalog_adapter, engagement, device)
    return Container(
        user=User.model_validate(fx.USER),
        engagement=engagement,
        conversation_memory=conversation_memory,
        compaction=compaction,
        companion=companion,
        reengagement=reengagement,
        recommendation=recommendation,
        device=device,
        knowledge=knowledge,
        catalog=catalog,
        order=order,
        handoff=handoff,
        notification=notification,
        store=store,
        triage=triage,
    )
