"""멀티테넌트 상태 + 게스트(비로그인) — specs/multi-tenant-state 슬라이스 1·2.

토글 off(기본) = 회귀(기본 사용자), on = Principal 해석·게스트 격리·커밋 게이트.
"""
import json

from fastapi.testclient import TestClient

from app.api.internal import _container, app
from app.principal import (
    DEFAULT_USER_ID,
    Principal,
    UserDirectory,
    resolve_principal,
)

client = TestClient(app)


# ── Principal 해석 (요구사항 2·7) ───────────────────────────────────────────
def test_resolve_default_when_toggle_off(monkeypatch):
    monkeypatch.delenv("MULTITENANT", raising=False)
    p = resolve_principal("anyone")           # 토글 off → 기본 사용자(회귀)
    assert p.kind == "user" and p.id == DEFAULT_USER_ID


def test_resolve_user_and_guest_when_on(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    assert resolve_principal("usr_42") == Principal("user", "usr_42")
    g = resolve_principal(None, None)          # 비로그인 → 게스트(토큰 발급)
    assert g.is_guest and g.id.startswith("guest:")
    # 토큰 제공 시 안정적(같은 게스트)
    g2 = resolve_principal(None, "tok_abc")
    assert g2.id == "guest:tok_abc"


def test_user_directory_default_and_guest():
    d = UserDirectory()
    assert d.get(Principal("user", DEFAULT_USER_ID)).id == DEFAULT_USER_ID   # fixture 프로필
    guest_user = d.get(Principal("guest", "guest:x"))                        # 합성 최소 프로필
    assert guest_user.id == "guest:x" and guest_user.display_name == "게스트"


# ── 상태 격리(리포 레벨, 요구사항 1) ────────────────────────────────────────
def test_companion_state_isolated_per_user():
    _container.companion.record_turn("u_iso_A", "질문A", "답A")
    _container.companion.record_turn("u_iso_B", "질문B", "답B")
    assert _container.companion.context("u_iso_A") != _container.companion.context("u_iso_B")


# ── 게스트(비로그인) 정책 (요구사항 2-2·2-3) ───────────────────────────────
def test_guest_can_chat(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.post("/internal/turn", json={"text": "세탁기 물이 안 빠져요"})   # user_id 없음 → 게스트
    assert r.status_code == 200
    lines = [json.loads(line) for line in r.text.strip().split("\n")]
    assert any(c["type"] == "section" for c in lines) and lines[-1]["type"] == "done"


def test_guest_blocked_from_order(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.post("/internal/orders",
                    json={"part_ids": ["part_drain_filter"], "confirmed": True})   # 헤더 없음 → 게스트
    assert r.status_code == 401 and r.json()["code"] == "LoginRequired"


def test_login_user_can_order(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.post("/internal/orders",
                    json={"user_id": "usr_01", "part_ids": ["part_drain_filter"], "confirmed": True},
                    headers={"X-User-Id": "usr_01"})
    assert r.status_code == 200 and r.json()["user_id"] == "usr_01"


def test_order_ungated_when_toggle_off(monkeypatch):
    # 회귀 — 토글 off면 게스트 게이트 없음(기존 동작)
    monkeypatch.delenv("MULTITENANT", raising=False)
    r = client.post("/internal/orders",
                    json={"part_ids": ["part_drain_filter"], "confirmed": True})
    assert r.status_code == 200


# ── gap ② — 헤더 우선·본문 폴백 신원 해석(BFF 중계) ──────────────────────────
def test_order_with_body_user_id_succeeds_when_on(monkeypatch):
    """(a) BFF 중계 케이스 — 헤더 없이 본문 user_id로 신원을 보내면 통과해야 한다(401 아님)."""
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.post("/internal/orders",
                    json={"user_id": "usr_01", "part_ids": ["part_drain_filter"], "confirmed": True})
    assert r.status_code == 200 and r.json()["user_id"] == "usr_01"


def test_order_with_header_user_id_succeeds_when_on(monkeypatch):
    """(b) 헤더 X-User-Id만으로도 신원이 인정돼 통과한다."""
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.post("/internal/orders",
                    json={"part_ids": ["part_drain_filter"], "confirmed": True},
                    headers={"X-User-Id": "usr_77"})
    assert r.status_code == 200


def test_order_true_guest_blocked_when_on(monkeypatch):
    """(c) 진짜 게스트 — 본문에 user_id를 빼고 게스트 토큰만(헤더) 보내면 401."""
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.post("/internal/orders",
                    json={"part_ids": ["part_drain_filter"], "confirmed": True},
                    headers={"X-Guest-Token": "tok_guest_1"})
    assert r.status_code == 401 and r.json()["code"] == "LoginRequired"


def test_order_with_body_user_id_ungated_when_off(monkeypatch):
    """(d) 토글 off — 본문 신원과 무관하게 게이트 없음(회귀 보존)."""
    monkeypatch.delenv("MULTITENANT", raising=False)
    r = client.post("/internal/orders",
                    json={"part_ids": ["part_drain_filter"], "confirmed": True},
                    headers={"X-Guest-Token": "tok_guest_1"})
    assert r.status_code == 200
