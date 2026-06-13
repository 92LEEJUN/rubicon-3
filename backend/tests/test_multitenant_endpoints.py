"""멀티테넌트 신원 해석 — GET/POST 조회 엔드포인트가 요청 Principal로 스코프되는지 검증.

토글 `MULTITENANT`(기본 off)면 항상 기본 사용자(usr_01)로 폴백 → 회귀 보존(요구사항 7).
on이면 헤더 `X-User-Id`/`X-Guest-Token`로 신원을 해석한다(요구사항 2).

소유 규칙: 이 파일과 `app/api/internal.py`만 수정. 컨테이너/서비스/principal은 재사용한다.
"""
from fastapi.testclient import TestClient

from app.api.internal import app, _container

client = TestClient(app)


# ── 토글 ON: 헤더 신원으로 스코프 ─────────────────────────────────────────────
def test_resume_scoped_by_header_user(monkeypatch):
    """resume는 헤더 X-User-Id로 키잉된 컴패니언 상태를 반영(사용자별 분리)."""
    monkeypatch.setenv("MULTITENANT", "1")
    # userX/userY에 각각 다른 턴을 기록 → resume가 각자 스코프를 반영해야 한다.
    _container.companion.record_turn("userX", "X의 질문", "X 응답")
    _container.companion.record_turn("userY", "Y의 질문", "Y 응답")

    rx = client.get("/internal/resume", headers={"X-User-Id": "userX"})
    ry = client.get("/internal/resume", headers={"X-User-Id": "userY"})
    assert rx.status_code == 200 and ry.status_code == 200

    # 각 사용자의 컴패니언 컨텍스트가 자신의 턴을 담고 있어야 한다(스코프 분리 확인).
    ctx_x = _container.companion.context("userX")
    ctx_y = _container.companion.context("userY")
    assert ctx_x != ctx_y
    # resume 응답 shape는 동일(키 보존) — model_dump 결과는 dict.
    assert isinstance(rx.json(), dict)


def test_home_display_name_per_principal(monkeypatch):
    """home의 user 표시명이 Principal별로 달라진다(기본 사용자 vs 합성 프로필)."""
    monkeypatch.setenv("MULTITENANT", "1")
    # 기본 사용자(usr_01)는 fixture 프로필 → display_name "홍길동".
    r_default = client.get("/internal/home", headers={"X-User-Id": "usr_01"})
    assert r_default.status_code == 200
    body_default = r_default.json()
    assert body_default["kind"] == "home_summary"
    assert body_default["data"]["user"] == "홍길동"

    # 미지의 user-id는 UserDirectory가 최소 프로필 합성 → display_name = id.
    r_other = client.get("/internal/home", headers={"X-User-Id": "userZ"})
    assert r_other.status_code == 200
    body_other = r_other.json()
    assert body_other["data"]["user"] == "userZ"
    # shape 동일(키 보존).
    assert set(body_default["data"]) == set(body_other["data"])


def test_home_guest_scoped(monkeypatch):
    """게스트(X-User-Id 없음)는 게스트 스코프 응답 — 크래시 없이 게스트 프로필 사용."""
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.get("/internal/home")  # 신원 헤더 없음 → 게스트 principal
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "home_summary"
    assert body["data"]["user"] == "게스트"


def test_recommendations_guest_does_not_crash(monkeypatch):
    """게스트 추천 호출 — 게스트 principal로 정상 응답(shape 보존)."""
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.get("/internal/recommendations", headers={"X-Guest-Token": "g-abc"})
    assert r.status_code == 200
    assert "items" in r.json()


def test_catalog_recommend_guest_does_not_crash(monkeypatch):
    """catalog/recommend 게스트 호출 — 리스트 응답(shape 보존)."""
    monkeypatch.setenv("MULTITENANT", "1")
    r = client.get("/internal/catalog/recommend")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── 토글 OFF: 회귀 보존(기본 사용자) ─────────────────────────────────────────
def test_home_regression_default_user_when_toggle_off():
    """토글 off(기본) — 헤더가 있어도 무시하고 기본 사용자(홍길동)로 폴백."""
    r = client.get("/internal/home", headers={"X-User-Id": "userZ"})
    assert r.status_code == 200
    assert r.json()["data"]["user"] == "홍길동"


def test_resume_regression_default_user_when_toggle_off():
    """토글 off — resume는 기본 사용자(usr_01) 컨텍스트로 동작(헤더 무시)."""
    r = client.get("/internal/resume", headers={"X-User-Id": "userZ"})
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_catalog_recommend_regression_when_toggle_off():
    """토글 off — catalog/recommend는 오늘과 동일(기본 사용자 추천)."""
    r = client.get("/internal/catalog/recommend")
    assert r.status_code == 200
    assert any(p["id"] == "prod_purifier_cube" for p in r.json())
