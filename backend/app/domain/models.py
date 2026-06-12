"""도메인 엔티티/DTO (Pydantic v2).

`specs/mvp-concierge/fixtures/`·`docs/data-model.md` 와 정합. 외부 raw가 아니라 **변환된 도메인 타입**이다.
관용(R13): 누락 필드는 기본값/None 허용, 알 수 없는 외부 필드는 무시(extra="ignore").
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# 공통 별칭
Id = str
Severity = Literal["info", "warning", "critical"]
AnomalyType = Literal["error_code", "consumable", "connectivity"]
DeviceHealth = Literal["ONLINE", "UNHEALTHY", "OFFLINE"]
Coverage = Literal["free", "paid", "unknown"]
Safety = Literal["none", "caution", "danger"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ── 기기 / 이상 (Device · IoT) ─────────────────────────────────────────────
class Consumable(_Base):
    name: str
    life_remaining: float            # 0.0~1.0
    threshold: float

    @property
    def needs_replacement(self) -> bool:
        """수명이 임계치 이하 → 교체 필요(선제안 트리거, R5)."""
        return self.life_remaining <= self.threshold


class Device(_Base):
    id: Id
    type: str                        # washer · refrigerator · air_purifier ...
    model: str
    status: DeviceHealth = "ONLINE"
    consumables: list[Consumable] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class Anomaly(_Base):
    id: Id
    device_id: Id
    type: AnomalyType
    severity: Severity = "warning"
    detail: str = ""
    detected_at: Optional[datetime] = None
    error_code: Optional[str] = None


class DeviceStatusResult(_Base):
    """get_status 결과 — 기기 + 감지된 이상(미연동 시 found=False)."""
    found: bool
    device: Optional[Device] = None
    anomalies: list[Anomaly] = Field(default_factory=list)
    message: Optional[str] = None


# ── CS 지식 / 해결 (Knowledge) ─────────────────────────────────────────────
class Source(_Base):
    title: str
    ref: str
    confidence: float = 0.0


class SolutionStep(_Base):
    order: int
    instruction: str
    media: list[dict] = Field(default_factory=list)
    safety: Safety = "none"
    pro_required: bool = False


class Solution(_Base):
    id: Id
    anomaly_id: Optional[Id] = None
    steps: list[SolutionStep] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    required_parts: list[Id] = Field(default_factory=list)
    escalation_needed: bool = False
    coverage: Coverage = "unknown"


class SolutionSearchResult(_Base):
    count: int
    solutions: list[Solution] = Field(default_factory=list)


# ── 제품 / 부품 (Catalog) ──────────────────────────────────────────────────
class Part(_Base):
    id: Id
    device_model: str
    name: str
    sku: str
    price: int
    in_stock: bool = True


class Product(_Base):
    id: Id
    category: str
    name: str
    model: str
    price: int
    image: Optional[str] = None
    specs: dict = Field(default_factory=dict)
    in_stock: bool = True


class PartMatchResult(_Base):
    count: int
    parts: list[Part] = Field(default_factory=list)


# ── 주문 / 커머스 (Commerce · O2O) ─────────────────────────────────────────
OrderStatus = Literal["DRAFT", "CONFIRMED", "CANCELLED", "FAILED"]


class OrderItem(_Base):
    part_id: Id
    name: str
    unit_price: int
    qty: int = 1

    @property
    def line_total(self) -> int:
        return self.unit_price * self.qty


class OrderSummary(_Base):
    """금액 분해(요구 결정) — subtotal·배송비·세금·할인·총액."""
    subtotal: int = 0
    shipping_fee: int = 0
    tax: int = 0
    discount: int = 0
    total: int = 0


class Order(_Base):
    id: Id
    user_id: Id
    items: list[OrderItem] = Field(default_factory=list)
    status: OrderStatus = "DRAFT"
    summary: OrderSummary = Field(default_factory=OrderSummary)
    created_at: Optional[datetime] = None


# ── 핸드오프 / 예약 (Handoff) ──────────────────────────────────────────────
class BookingSlot(_Base):
    id: Id
    start: datetime
    end: datetime
    visit_type: str = "REPAIR"


BookingStatus = Literal["REQUESTED", "CONFIRMED", "CANCELLED"]


class Booking(_Base):
    id: Id
    slot_id: Id
    status: BookingStatus = "REQUESTED"
    context_ref: Optional[Id] = None


# ── 사용자 / 동의 (User · Identity) ────────────────────────────────────────
class Address(_Base):
    label: str
    line: str
    default: bool = False


class Preferences(_Base):
    notify_opt_in: bool = False
    notify_min_priority: Severity = "info"
    interest_categories: list[str] = Field(default_factory=list)


class Consent(_Base):
    scopes: list[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class User(_Base):
    id: Id
    display_name: str
    linked_device_ids: list[Id] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)
    addresses: list[Address] = Field(default_factory=list)
    consent: Consent = Field(default_factory=Consent)


# ── Engagement(확인 정보, R29) — 내부 Repository ───────────────────────────
EngagementState = Literal["viewed", "acknowledged", "dismissed", "interested"]


class EngagementRecord(_Base):
    user_id: Id
    ref: Id
    state: EngagementState
    updated_at: Optional[datetime] = None


# ── 오케스트레이션 (의도) ──────────────────────────────────────────────────
Intent = Literal["device_status", "troubleshoot", "order", "recommend", "general"]


class IntentResult(_Base):
    intents: list[Intent] = Field(default_factory=list)
    is_compound: bool = False


# ── 응답 표현 (Template · CTA · Section, response-templates.md) ─────────────
# action: 대화형(chat)·커밋(commit)·이동(navigate) — architecture.md §8 두 경로
CtaAction = Literal["chat", "commit", "navigate"]


class Cta(_Base):
    label: str
    action: CtaAction = "chat"
    kind: Optional[str] = None        # order · reorder · booking · explain ...
    payload: dict = Field(default_factory=dict)


class Template(_Base):
    """kind → FE 컴포넌트 레지스트리로 렌더. data는 kind별 페이로드(response-templates.md)."""
    kind: str
    data: dict = Field(default_factory=dict)


class MessageSection(_Base):
    """복합 응답(R7)의 의도별 섹션. handled=False면 미처리(품절·폴백 등)."""
    label: str
    intent: str
    template: Template
    ctas: list[Cta] = Field(default_factory=list)
    handled: bool = True


class AssistantTurn(_Base):
    """한 번의 어시스턴트 응답 — 단일=섹션 1개, 복합=N개(우선순위 순서)."""
    sections: list[MessageSection] = Field(default_factory=list)
    active_flow: Optional[str] = None
    message_id: Optional[str] = None


class ConversationMemory(_Base):
    """대화 연속성 — 컴팩션 대상(ADR-0040, operations §4-1). user 단위 영속.

    오래된 턴은 `summary`로 접고(롤링 요약), 손실 위험 큰 항목(주문ID·기기모델 등)은
    `facts`로 별도 보존한다. `summarized_through` 이후 메시지는 verbatim으로 유지한다.
    """
    summary: str = ""
    facts: dict = Field(default_factory=dict)
    summarized_through: int = 0  # 요약에 흡수된 메시지 수(이 인덱스 이후는 verbatim)


OpenLoopKind = Literal["issue", "order", "flow"]
OpenLoopStatus = Literal["open", "resolved", "dismissed"]


class OpenLoop(_Base):
    """미해결 스레드 — 진행 중 문제·주문·보류 흐름(컴패니언 spec 요구 2)."""
    id: Id
    kind: OpenLoopKind
    ref: str                            # 참조(주문ID·오류코드·흐름명) — user 내 유일 키
    label: str                          # 사용자 표시 라벨
    status: OpenLoopStatus = "open"
    priority: int = 0                   # 높을수록 먼저(안전/CS 우선, §6.6)
    opened_at: datetime
    last_touch: datetime


class ResumePayload(_Base):
    """이어가기(resume) — 패널 (재)열기 시 복원 맥락(컴패니언 spec 요구 1·4·5)."""
    has_context: bool = False           # 이어갈 맥락이 있는지(없으면 깨끗한 시작)
    summary: str = ""
    facts: dict = Field(default_factory=dict)
    open_loops: list[OpenLoop] = Field(default_factory=list)  # 열린 미해결 스레드(요구 2.2)
    elapsed_label: Optional[str] = None  # "방금"·"어제"·"지난주" 등 상대 시간(요구 5)
    suspended_flow: Optional[str] = None  # 보류 흐름(ADR-0028)이 있으면 이어가기 후보
