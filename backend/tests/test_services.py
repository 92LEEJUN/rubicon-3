"""도메인 서비스 — Port 위 비즈니스 로직(임계치·게이트·개인화·중복 억제)."""
import pytest

from app.errors import ConfirmationRequired


# ── DeviceService ────────────────────────────────────────────────────────────
def test_get_status_attaches_anomalies(container):
    res = container.device.get_status("세탁기")
    assert res.found and res.anomalies


def test_consumable_alerts_threshold(container):
    fridge = next(d for d in container.device.list_devices() if d.type == "refrigerator")
    alerts = container.device.consumable_alerts(fridge)
    assert any("water_filter" in a.detail or "정수" in a.detail or "filter" in a.id for a in alerts)
    # 세탁기 배수필터(0.40 > 0.20)는 알림 없음
    washer = next(d for d in container.device.list_devices() if d.type == "washer")
    assert container.device.consumable_alerts(washer) == []


# ── KnowledgeService ─────────────────────────────────────────────────────────
def test_best_solution_for_5c(container):
    sol = container.knowledge.best_solution("물이 안 빠져요", error_code="5C")
    assert sol is not None
    assert sol.required_parts == ["part_drain_filter"]


# ── CatalogService (개인화 + R29 억제) ──────────────────────────────────────
def test_recommend_uses_interest(container):
    recs = container.catalog.recommend(container.user)
    assert any(p.id == "prod_purifier_cube" for p in recs)


def test_recommend_suppresses_seen(container):
    # 이미 본 추천은 재노출 억제(R29)
    container.engagement.record(container.user.id, "prod_purifier_cube", "viewed")
    recs = container.catalog.recommend(container.user)
    assert all(p.id != "prod_purifier_cube" for p in recs)


# ── OrderService (커밋 게이트 R17) ──────────────────────────────────────────
def test_checkout_without_confirmation_raises_gate(container):
    with pytest.raises(ConfirmationRequired) as exc:
        container.order.checkout("usr_01", ["part_drain_filter"], confirmed=False)
    # 게이트는 확인용 DRAFT(금액 분해 포함)를 동봉
    assert exc.value.draft.status == "DRAFT"
    assert exc.value.draft.summary.total == 12000 + exc.value.draft.summary.shipping_fee


def test_checkout_with_confirmation_succeeds(container):
    order = container.order.checkout("usr_01", ["part_drain_filter"], confirmed=True)
    assert order.status == "CONFIRMED"


# ── HandoffService (R18) ─────────────────────────────────────────────────────
def test_handoff_book(container):
    slots = container.handoff.list_slots("REPAIR")
    booking = container.handoff.book(slots[0].id, context_ref="conv_1")
    assert booking.status == "CONFIRMED"


# ── NotificationService (선제 + 동의/중복 게이트) ───────────────────────────
def test_pending_alerts_pass_opt_in(container):
    alerts = container.notification.pending_alerts(container.user)
    # 냉장고 정수필터(0.15<0.20)·공기청정기 HEPA(0.12<0.15) 임박 → 알림
    assert len(alerts) >= 2


def test_pending_alerts_suppressed_when_acknowledged(container):
    first = container.notification.pending_alerts(container.user)
    container.engagement.record(container.user.id, first[0].id, "acknowledged")
    second = container.notification.pending_alerts(container.user)
    assert len(second) == len(first) - 1  # 확인한 알림은 중복 억제(R29)


def test_pending_alerts_gated_by_opt_out(container):
    container.user.preferences.notify_opt_in = False
    assert container.notification.pending_alerts(container.user) == []
