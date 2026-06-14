"""BFF 레이트리밋(S7, ADR-0063) — 토큰버킷·키 식별·429·토글 off 회귀 불변."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.ratelimit import RateLimiter, TokenBucket, client_key, install_ratelimit


class _FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class _Req:
    """client_key 테스트용 최소 request 더블."""
    def __init__(self, headers=None, host=None):
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.client = type("C", (), {"host": host})() if host else None


# ── 토큰버킷 ──────────────────────────────────────────────────────────────────
def test_token_bucket_allows_burst_then_blocks():
    clock = _FakeClock()
    b = TokenBucket(rate=1.0, capacity=3, clock=clock)
    assert b.allow()[0] is True
    assert b.allow()[0] is True
    assert b.allow()[0] is True
    ok, retry_after = b.allow()  # 4번째는 토큰 소진
    assert ok is False
    assert retry_after > 0


def test_token_bucket_refills_over_time():
    clock = _FakeClock()
    b = TokenBucket(rate=2.0, capacity=2, clock=clock)
    assert b.allow()[0] is True
    assert b.allow()[0] is True
    assert b.allow()[0] is False  # 소진
    clock.t += 1.0                 # 1초 → 2토큰 보충
    assert b.allow()[0] is True    # 다시 허용(요구사항 1.5)


# ── 키 식별(신원 우선 → IP) ───────────────────────────────────────────────────
def test_client_key_prefers_user_then_guest_then_ip():
    assert client_key(_Req({"X-User-Id": "u1"})) == "user:u1"
    assert client_key(_Req({"X-Guest-Token": "g1"})) == "guest:g1"
    assert client_key(_Req(host="1.2.3.4")) == "ip:1.2.3.4"
    # 신원이 IP보다 우선
    assert client_key(_Req({"X-User-Id": "u1"}, host="1.2.3.4")) == "user:u1"


def test_rate_limiter_per_key_isolation():
    clock = _FakeClock()
    lim = RateLimiter(rate=1.0, capacity=1, clock=clock)
    assert lim.check("a")[0] is True
    assert lim.check("a")[0] is False   # a 소진
    assert lim.check("b")[0] is True    # b는 독립 버킷


# ── 미들웨어 통합: 토글 게이트 ────────────────────────────────────────────────
def _app_with_limiter(limiter=None):
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    install_ratelimit(app, limiter=limiter)
    return app


def test_middleware_off_by_default_is_noop(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT", raising=False)
    app = _app_with_limiter(RateLimiter(rate=1.0, capacity=1))
    client = TestClient(app)
    # 토글 off → 미들웨어 미등록, 반복 호출 모두 200(회귀 불변).
    for _ in range(5):
        assert client.get("/ping").status_code == 200


def test_middleware_on_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    clock = _FakeClock()
    app = _app_with_limiter(RateLimiter(rate=1.0, capacity=1, clock=clock))
    client = TestClient(app)
    assert client.get("/ping").status_code == 200
    r = client.get("/ping")  # 두 번째는 차단
    assert r.status_code == 429
    body = r.json()
    assert body["code"] == "RateLimited"
    assert body["retry_after"] >= 1
    assert "retry-after" in {k.lower() for k in r.headers.keys()}


def test_middleware_on_records_security_audit(monkeypatch):
    """차단 시 보안 감사에 기록(S5 AuditLog 재사용)."""
    monkeypatch.setenv("RATE_LIMIT", "1")
    from app.privacy.audit import AuditLog  # backend on pytest pythonpath

    audit = AuditLog()
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    install_ratelimit(app, limiter=RateLimiter(rate=1.0, capacity=1), audit=audit)
    client = TestClient(app)
    client.get("/ping")
    client.get("/ping")  # 차단 발생
    actions = [e.action for e in audit.list()]
    assert "security.ratelimit_block" in actions
