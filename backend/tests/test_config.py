"""환경 계층 & 구성 토대(ADR-0056) — 결정적 검증."""
import app.config as cfg
from app.platform import wiring


def _reload(monkeypatch, **env):
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    return cfg.reload_settings()


# ── 환경별 기본값(요구사항 1-1) ──────────────────────────────────────────────
def test_env_defaults_dev(monkeypatch):
    s = _reload(monkeypatch, APP_ENV="dev", LOG_LEVEL=None, LOG_JSON=None, DEBUG=None)
    assert s.app_env == "dev" and s.is_dev and not s.is_prod
    assert s.log_level == "DEBUG" and s.log_json is False and s.debug is True


def test_env_defaults_prd(monkeypatch):
    s = _reload(monkeypatch, APP_ENV="prd", LOG_LEVEL=None, LOG_JSON=None, DEBUG=None)
    assert s.is_prod and s.log_level == "INFO" and s.log_json is True and s.debug is False


# ── 명시 env 우선(요구사항 1-2) ──────────────────────────────────────────────
def test_explicit_env_overrides_default(monkeypatch):
    s = _reload(monkeypatch, APP_ENV="prd", LOG_LEVEL="warning", LOG_JSON="0")
    assert s.log_level == "WARNING"           # 명시 우선(대문자 정규화)
    assert s.log_json is False                # prd 기본(True)을 덮음


# ── 폴백(요구사항 1-3) ───────────────────────────────────────────────────────
def test_unknown_env_falls_back_to_dev(monkeypatch):
    s = _reload(monkeypatch, APP_ENV="qa")    # 미지값
    assert s.app_env == "dev"


def test_missing_env_falls_back_to_dev(monkeypatch):
    s = _reload(monkeypatch, APP_ENV=None)
    assert s.app_env == "dev"


# ── reload/캐시(요구사항 4-1) ────────────────────────────────────────────────
def test_get_settings_cached_until_reload(monkeypatch):
    _reload(monkeypatch, APP_ENV="dev")
    assert cfg.get_settings().app_env == "dev"
    monkeypatch.setenv("APP_ENV", "stg")
    assert cfg.get_settings().app_env == "dev"     # 캐시(미reload)
    assert cfg.reload_settings().app_env == "stg"  # reload로 갱신


# ── 배선 시임(요구사항 3) ────────────────────────────────────────────────────
class _FakeApp:
    def __init__(self):
        self.mw = []
        self.handlers = []

    def add_event_handler(self, ev, fn):
        self.handlers.append((ev, fn))


def test_wiring_apply_noop_when_empty():
    wiring._reset()
    app = _FakeApp()
    wiring.apply(app)                               # 등록 없음 → 무동작(요구사항 3-2)
    assert app.mw == [] and app.handlers == []


def test_wiring_registers_and_applies_in_priority_order():
    wiring._reset()
    order = []

    @wiring.register_middleware(priority=20)
    def _mw_b(app):
        order.append("b")

    @wiring.register_middleware(priority=10)
    def _mw_a(app):
        order.append("a")

    @wiring.register_startup
    def _start():
        pass

    app = _FakeApp()
    wiring.apply(app)
    assert order == ["a", "b"]                       # priority 순(요구사항 3-1)
    assert any(ev == "startup" for ev, _ in app.handlers)
    wiring._reset()
