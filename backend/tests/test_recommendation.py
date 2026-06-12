"""선제 제품 추천 — 추천 코어(제외·동의 차등)·트리거·선제 등록 (specs/product-recommendation)."""
from app.companion import CompanionService
from app.compaction import CompactionService, RuleBasedCompactor
from app.domain import Consent, Consumable, Device, Preferences, Product, User
from app.recommendation import RecommendationService
from app.repositories import (
    InMemoryConversationMemoryRepository,
    InMemoryConversationStore,
    InMemoryEngagementRepository,
    InMemoryOpenLoopRepository,
)


class _Cat:
    def __init__(self, products):
        self._p = products

    def recommend(self, cats):
        return list(self._p)


class _Dev:
    def __init__(self, devices):
        self._d = devices

    def list_devices(self):
        return self._d


_PRODUCTS = [
    Product(id="p_washer", category="washer", name="세탁기 신형", model="WF99", price=900000),
    Product(id="p_air", category="air_purifier", name="공기청정기", model="AX60", price=300000),
]
_OWNED = [Device(id="dev1", type="washer", model="WF45",
                 consumables=[Consumable(name="필터", life_remaining=0.1, threshold=0.2)])]


def _user(scopes=("personalization", "device_data"), interests=("air_purifier",)):
    return User(id="u1", display_name="준희", linked_device_ids=["dev1"],
                preferences=Preferences(interest_categories=list(interests)),
                consent=Consent(scopes=list(scopes)))


def _svc(eng=None):
    return RecommendationService(_Cat(_PRODUCTS), eng or InMemoryEngagementRepository(), _Dev(_OWNED))


# ── 추천 코어 제외 ───────────────────────────────────────────────────────────
def test_excludes_owned_category_when_device_data():
    items = _svc().recommend(_user())
    cats = {it.product.category for it in items}
    assert "washer" not in cats          # 보유 세탁기 카테고리 제외(요구 3-1)
    assert "air_purifier" in cats


def test_excludes_seen_via_engagement():
    eng = InMemoryEngagementRepository()
    eng.record("u1", "p_air", "dismissed")
    items = _svc(eng).recommend(_user())
    assert all(it.product.id != "p_air" for it in items)  # 무시한 추천 억제(R29)


# ── 동의 차등 (가장 중요) ─────────────────────────────────────────────────────
def test_no_personalization_general_fallback():
    items = _svc().recommend(_user(scopes=()))   # 동의 없음
    assert items and all(it.personalized is False for it in items)
    assert "개인화 제한" in items[0].reason       # 일반 추천 고지(요구 4-2)
    # device_data 없음 → 보유 제외 미적용 → washer도 후보
    assert any(it.product.category == "washer" for it in items)


def test_device_data_only_owned_exclusion_but_not_personalized():
    items = _svc().recommend(_user(scopes=("device_data",)))
    assert all(it.personalized is False for it in items)          # personalization 없음
    assert all(it.product.category != "washer" for it in items)   # 보유 제외는 적용(요구 4-3)


# ── 트리거 ───────────────────────────────────────────────────────────────────
def test_trigger_consumable_due_and_interest():
    hits = _svc().triggers(_user())
    kinds = {h.kind for h in hits}
    assert "consumable_due" in kinds                  # 필터 수명 임계 이하(요구 1)
    assert "interest_signal" in kinds                 # personalization 동의 → 관심 신호
    assert any("수명 10%" in h.reason_seed for h in hits)


def test_trigger_no_signal_empty():
    user = User(id="u2", display_name="x", linked_device_ids=[], consent=Consent(scopes=[]))
    assert _svc().triggers(user) == []                # 무신호 → 생성 안 함(요구 1-4)


# ── 선제 등록(컴패니언 게이트 재사용) ─────────────────────────────────────────
def test_enqueue_preemptive_creates_open_loops():
    companion = CompanionService(InMemoryConversationMemoryRepository(), InMemoryConversationStore(),
                                 CompactionService(RuleBasedCompactor()), InMemoryOpenLoopRepository())
    user = _user()
    n = _svc().enqueue_preemptive(user, companion)
    assert n >= 1
    refs = {l.ref for l in companion.open_loops(user.id)}
    assert any(r.startswith("rec:") for r in refs)    # 추천이 open-loop로 등록(요구 7)
