"""선제적 제품 추천 — 추천 코어 + 트리거 (specs/product-recommendation).

선제/반응형 두 진입이 **같은 추천 코어**를 공유한다(후보→랭킹→제외→근거).
선제는 컴패니언 `ReEngagementService` 게이트(ADR-0042)를 재사용한다(신규 선제 인프라 없음).
새 영속 엔티티 0 — `TriggerHit`·`RecommendationItem`은 서비스 내부 비영속 타입.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .domain import Product, User

TriggerKind = Literal["consumable_due", "repurchase_cycle", "interest_signal", "complement"]
# 트리거 우선순위 → open-loop priority(안전/CS 우선과 정합)
_PRIORITY = {"consumable_due": 2, "complement": 1, "repurchase_cycle": 1, "interest_signal": 0}


class TriggerHit(BaseModel):
    kind: TriggerKind
    subject_ref: str
    reason_seed: str
    priority: int = 0


class RecommendationItem(BaseModel):
    product: Product
    reason: str
    trigger: Optional[TriggerKind] = None
    personalized: bool = True


class RecommendationService:
    """추천 코어 — CatalogPort·Engagement·개인화 컨텍스트만 의존(요구 8). 랭킹/제외/근거는 도메인 규칙."""

    def __init__(self, catalog_port, engagement, device_service) -> None:
        self._port = catalog_port
        self._engagement = engagement
        self._device = device_service

    # ── 추천 코어 (선제·반응형 공유) ──────────────────────────────────────────
    def recommend(self, user: User) -> list[RecommendationItem]:
        scopes = set(user.consent.scopes)
        personalized = "personalization" in scopes
        cats = user.preferences.interest_categories if personalized else []
        products: list[Product] = self._port.recommend(cats)

        if self._engagement:  # 이미 본/무시한 추천 억제(R29, 요구 3-3)
            products = [p for p in products if not self._engagement.has_seen(user.id, p.id)]

        if "device_data" in scopes:  # 보유 기기 중복 제외(요구 3-1·4-3)
            owned_models, owned_types = self._owned(user)
            products = [p for p in products
                        if p.model not in owned_models and p.category not in owned_types]

        return [RecommendationItem(product=p, personalized=personalized,
                                   reason=self._reason(p, personalized)) for p in products]

    def _owned(self, user: User) -> tuple[set, set]:
        models, types = set(), set()
        for d in self._device.list_devices():
            if d.id in user.linked_device_ids:
                models.add(d.model); types.add(d.type)
        return models, types

    @staticmethod
    def _reason(p: Product, personalized: bool) -> str:
        # 무근거 사양·가격 날조 금지(llm-policy §4) — 카테고리 기반 최소 근거
        return f"{p.category} 관심에 맞춘 추천" if personalized else "인기 제품 추천(개인화 제한)"

    # ── 선제 트리거 (요구 1) ──────────────────────────────────────────────────
    def triggers(self, user: User) -> list[TriggerHit]:
        """소모품 수명·관심 신호 → 트리거 후보. 신호 없으면 빈 결과(무근거 추천 방지, 요구 1-4)."""
        hits: list[TriggerHit] = []
        for d in self._device.list_devices():
            if d.id not in user.linked_device_ids:
                continue
            for c in d.consumables:
                if c.needs_replacement:
                    hits.append(TriggerHit(kind="consumable_due", subject_ref=d.id,
                                           reason_seed=f"{c.name} 수명 {int(c.life_remaining * 100)}%",
                                           priority=_PRIORITY["consumable_due"]))
        if "personalization" in set(user.consent.scopes):
            for cat in user.preferences.interest_categories:
                hits.append(TriggerHit(kind="interest_signal", subject_ref=cat,
                                       reason_seed=f"{cat} 관심", priority=_PRIORITY["interest_signal"]))
        return hits

    # ── 선제 진입 — 컴패니언 open-loop로 등록(게이트는 ReEngagement 재사용, 요구 2·7) ──
    def enqueue_preemptive(self, user: User, companion, *, now=None) -> int:
        """트리거를 open-loop(kind=flow, ref=rec:*)로 등록 → 선제 전달은 컴패니언 게이트가 규율."""
        hits = self.triggers(user)
        for h in hits:
            companion.track_loop(user.id, "flow", f"rec:{h.subject_ref}",
                                 f"추천: {h.reason_seed}", priority=h.priority, now=now)
        return len(hits)
