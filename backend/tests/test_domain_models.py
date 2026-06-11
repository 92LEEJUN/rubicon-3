"""도메인 모델 — fixtures 로딩·불변식·계산 속성 검증."""
from app import fixtures as fx
from app.domain import Consumable, Device, Order, OrderItem, User


def test_device_loads_from_fixture():
    dev = Device.model_validate(fx.DEVICES[0])
    assert dev.id == "dev_washer_01"
    assert dev.status == "UNHEALTHY"
    assert dev.consumables[0].name == "drain_filter"


def test_consumable_needs_replacement_threshold():
    # 임계치 이하 → 교체 필요
    assert Consumable(name="x", life_remaining=0.15, threshold=0.20).needs_replacement
    assert Consumable(name="x", life_remaining=0.20, threshold=0.20).needs_replacement
    assert not Consumable(name="x", life_remaining=0.40, threshold=0.20).needs_replacement


def test_order_item_line_total():
    item = OrderItem(part_id="p", name="필터", unit_price=12000, qty=2)
    assert item.line_total == 24000


def test_user_loads_consent_and_prefs():
    user = User.model_validate(fx.USER)
    assert "device_data" in user.consent.scopes
    assert user.preferences.notify_opt_in is True
    assert user.preferences.interest_categories == ["air_purifier"]


def test_models_ignore_unknown_fields():
    # ACL 관용(R13): 외부 raw의 모르는 필드는 무시
    dev = Device.model_validate({"id": "d", "type": "washer", "model": "M", "unknown_x": 1})
    assert not hasattr(dev, "unknown_x")
