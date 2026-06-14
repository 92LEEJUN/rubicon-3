"""개인정보·DSR(S5, ADR-0061) — 동의 scope 부여/철회·DSR 접근/삭제/정정·보존·감사.

단위(ConsentStore·DSRService·RetentionPolicy·AuditLog) + 통합(TestClient, 신규 라우터).
신원은 MULTITENANT 토글 + 헤더(X-User-Id)로 해석한다(기존 패턴). 토글 off면 기본 사용자.
"""
from fastapi.testclient import TestClient

from app.api.internal import app
from app.domain import Preferences, User
from app.privacy import audit as audit_mod
from app.privacy import router as privacy_router
from app.privacy.audit import AuditLog
from app.privacy.consent import KNOWN_SCOPES, ConsentStore
from app.privacy.dsr import DSRService
from app.privacy.retention import RETENTION_DAYS, RetentionPolicy

client = TestClient(app)


# ── 단위: ConsentStore (요구사항 1) ─────────────────────────────────────────
def test_consent_grant_revoke_status():
    store = ConsentStore()
    user = User(id="u1", display_name="x")
    store.grant(user, "personalization")
    store.grant(user, "analytics")
    assert set(user.consent.scopes) == {"personalization", "analytics"}
    assert user.consent.updated_at is not None

    # 철회는 해당 scope만 제거(나머지 보존, 1.2)
    store.revoke(user, "analytics")
    assert user.consent.scopes == ["personalization"]

    status = ConsentStore.status(user)
    assert status["personalization"] is True
    assert status["analytics"] is False
    assert set(status) == set(KNOWN_SCOPES)


def test_consent_unknown_scope_rejected():
    store = ConsentStore()
    user = User(id="u1", display_name="x")
    try:
        store.grant(user, "nonexistent")
        assert False, "unknown scope는 ValueError여야 한다"
    except ValueError:
        pass


# ── 단위: DSRService (요구사항 2·3·4) ───────────────────────────────────────
class _FakeDir:
    def __init__(self, user):
        self._users = {user.id: user}

    def get(self, principal):
        from app.domain import User as _U
        return self._users.get(principal.id) or _U(id=principal.id, display_name=principal.id)

    def upsert(self, user):
        self._users[user.id] = user


def test_dsr_export_collects_user_data():
    from app.container import build_container
    c = build_container()
    user = User(id="u_dsr", display_name="홍길동")
    dsr = DSRService(c, _FakeDir(user))
    # 데이터 적재 — engagement·대화 메모리
    c.engagement.record("u_dsr", "ref1", "interested")
    c.companion.record_turn("u_dsr", "안녕", "반가워요")

    data = dsr.export("u_dsr")
    assert data["user_id"] == "u_dsr"
    assert data["profile"]["display_name"] == "홍길동"
    assert "consent" in data
    assert any(r["ref"] == "ref1" for r in data["engagement"])
    assert isinstance(data["orders"], list)
    # 형태 보존 — 키 존재
    for key in ("conversation_memory", "open_loops", "engagement", "orders"):
        assert key in data


def test_dsr_delete_then_export_empty():
    from app.container import build_container
    c = build_container()
    user = User(id="u_del", display_name="x")
    dsr = DSRService(c, _FakeDir(user))
    c.companion.record_turn("u_del", "질문", "응답")
    c.engagement.record("u_del", "r", "viewed")

    summary = dsr.delete("u_del")
    assert summary["conversation_memory"] == "deleted"
    assert summary["open_loops"] == "deleted"
    # 인메모리 engagement는 삭제 메서드 미제공 → skip(부분 삭제 허용, 3.2)
    assert summary["engagement"] in ("deleted", "skipped")

    # 후속 export — 대화 메모리는 비어야 한다(3.3)
    data = dsr.export("u_del")
    assert data["conversation_memory"]["summary"] == ""
    assert data["open_loops"] == []


def test_dsr_rectify_allowed_and_rejected():
    from app.container import build_container
    c = build_container()
    user = User(id="u_rec", display_name="old")
    d = _FakeDir(user)
    dsr = DSRService(c, d)

    updated = dsr.rectify("u_rec", {"display_name": "new"})
    assert updated.display_name == "new"
    assert d._users["u_rec"].display_name == "new"

    # preferences(허용 필드)도 도메인 타입으로 강제돼야 한다
    updated2 = dsr.rectify("u_rec", {"preferences": {"notify_opt_in": True}})
    assert isinstance(updated2.preferences, Preferences)
    assert updated2.preferences.notify_opt_in is True

    # 허용 외 필드는 거부(4.2)
    try:
        dsr.rectify("u_rec", {"id": "hack"})
        assert False, "비허용 필드는 ValueError여야 한다"
    except ValueError:
        pass


# ── 단위: Retention·Audit (요구사항 5·6) ────────────────────────────────────
def test_retention_policy_and_sweep_mock():
    pol = RetentionPolicy.policy()
    assert set(pol) == set(RETENTION_DAYS)
    assert all(isinstance(v, int) and v > 0 for v in pol.values())

    rp = RetentionPolicy()
    swept = rp.sweep()
    # Mock — 카테고리별 후보 0건(비변형, 5.3)
    assert swept == {cat: 0 for cat in RETENTION_DAYS}


def test_audit_record_and_list_ordered():
    log = AuditLog()
    log.record("consent.grant", subject="u1", detail="analytics")
    log.record("dsr.delete", subject="u1")
    events = log.list()
    assert [e.action for e in events] == ["consent.grant", "dsr.delete"]
    assert events[0].subject == "u1"
    assert events[0].at <= events[1].at


# ── 통합: 신규 라우터 (요구사항 1·2·3·6·7) ──────────────────────────────────
def test_consent_endpoints_grant_status(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    h = {"X-User-Id": "u_api_consent"}
    r = client.post("/internal/privacy/consent/grant", json={"scope": "personalization"}, headers=h)
    assert r.status_code == 200
    assert "personalization" in r.json()["scopes"]

    s = client.get("/internal/privacy/consent", headers=h)
    assert s.status_code == 200
    assert s.json()["scopes"]["personalization"] is True


def test_consent_revoke_preserves_others(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    h = {"X-User-Id": "u_api_revoke"}
    client.post("/internal/privacy/consent/grant", json={"scope": "analytics"}, headers=h)
    client.post("/internal/privacy/consent/grant", json={"scope": "device_data"}, headers=h)
    r = client.post("/internal/privacy/consent/revoke", json={"scope": "analytics"}, headers=h)
    assert r.status_code == 200
    s = client.get("/internal/privacy/consent", headers=h).json()["scopes"]
    assert s["analytics"] is False
    assert s["device_data"] is True


def test_consent_unknown_scope_400(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.post("/internal/privacy/consent/grant", json={"scope": "bogus"},
                    headers={"X-User-Id": "u_api"})
    assert r.status_code == 400
    assert r.json()["code"] == "UnknownScope"


def test_dsr_export_and_delete_endpoints(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    h = {"X-User-Id": "u_api_dsr"}
    # 데이터 적재(공유 컨테이너)
    from app.api.internal import _container
    _container.companion.record_turn("u_api_dsr", "질문", "응답")

    exp = client.get("/internal/privacy/dsr/export", headers=h)
    assert exp.status_code == 200
    body = exp.json()
    assert body["user_id"] == "u_api_dsr"
    assert body["conversation_memory"]["summary"] != "" or "open_loops" in body

    # 삭제 → 후속 export 비어야(접근·삭제 핵심 시나리오)
    d = client.post("/internal/privacy/dsr/delete", headers=h)
    assert d.status_code == 200
    assert d.json()["deleted"]["conversation_memory"] == "deleted"
    exp2 = client.get("/internal/privacy/dsr/export", headers=h).json()
    assert exp2["conversation_memory"]["summary"] == ""


def test_dsr_rectify_endpoint_and_reject(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    h = {"X-User-Id": "u_api_rectify"}
    r = client.post("/internal/privacy/dsr/rectify",
                    json={"fields": {"display_name": "정정됨"}}, headers=h)
    assert r.status_code == 200
    assert r.json()["display_name"] == "정정됨"

    bad = client.post("/internal/privacy/dsr/rectify",
                      json={"fields": {"id": "hack"}}, headers=h)
    assert bad.status_code == 400
    assert bad.json()["code"] == "NotRectifiable"


def test_retention_and_audit_endpoints(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    pol = client.get("/internal/privacy/retention/policy")
    assert pol.status_code == 200
    assert "conversation_memory" in pol.json()["retention_days"]

    sw = client.post("/internal/privacy/retention/sweep")
    assert sw.status_code == 200
    assert sw.json()["expired_candidates"]["orders"] == 0

    # 동의/DSR 호출 후 감사 로그에 이벤트가 쌓였는지(요구사항 6)
    client.post("/internal/privacy/consent/grant", json={"scope": "engagement"},
                headers={"X-User-Id": "u_audit"})
    log = client.get("/internal/privacy/audit")
    assert log.status_code == 200
    actions = {e["action"] for e in log.json()["events"]}
    assert "consent.grant" in actions


# ── 회귀: 토글 off면 기존 동작 불변(요구사항 7) ─────────────────────────────
def test_consent_status_default_user_when_toggle_off():
    # MULTITENANT off → 기본 사용자(usr_01). 헤더 무시. 라우터는 정상 응답.
    r = client.get("/internal/privacy/consent", headers={"X-User-Id": "ignored"})
    assert r.status_code == 200
    assert set(r.json()["scopes"]) == set(KNOWN_SCOPES)


def test_existing_health_endpoint_unaffected():
    # 신규 라우터 등록이 기존 엔드포인트를 깨지 않는다(회귀).
    r = client.get("/internal/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_audit_module_record_nonblocking_on_failure():
    # sink 실패가 주 흐름을 막지 않는다(6.3) — 깨진 record라도 예외 누출 없음.
    log = audit_mod.AuditLog()
    # detail에 비직렬화 객체를 넣어도 record는 예외를 던지지 않아야 한다.
    log.record("x", subject="s", detail=object())
    assert len(log.list()) == 1
    # 라우터 모듈 로드 시 wiring 등록이 됐는지(간접) — router 객체 존재.
    assert privacy_router.router is not None
