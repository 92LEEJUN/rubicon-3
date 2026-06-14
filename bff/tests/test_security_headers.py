"""BFF 보안 헤더(S7, ADR-0063) — 추가형·토글 off 무동작·기존 헤더 비덮어쓰기."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from gateway.security import SECURITY_HEADERS, install_security_headers


def _app():
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.get("/preset")
    def preset():
        # 이미 X-Frame-Options를 가진 응답(비덮어쓰기 검증용).
        return JSONResponse({"ok": True}, headers={"X-Frame-Options": "SAMEORIGIN"})

    return app


def test_headers_off_by_default_is_noop(monkeypatch):
    monkeypatch.delenv("SECURITY_HEADERS", raising=False)
    app = _app()
    installed = install_security_headers(app)
    assert installed is False
    r = TestClient(app).get("/ping")
    assert r.status_code == 200
    for name in SECURITY_HEADERS:
        assert name not in r.headers  # 회귀 불변


def test_headers_added_when_enabled(monkeypatch):
    monkeypatch.setenv("SECURITY_HEADERS", "1")
    app = _app()
    assert install_security_headers(app) is True
    r = TestClient(app).get("/ping")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"


def test_existing_header_not_overwritten(monkeypatch):
    monkeypatch.setenv("SECURITY_HEADERS", "1")
    app = _app()
    install_security_headers(app)
    r = TestClient(app).get("/preset")
    # 기존 값 보존(추가형, 요구사항 2.3).
    assert r.headers["X-Frame-Options"] == "SAMEORIGIN"
    # 없던 헤더는 추가됨.
    assert r.headers["X-Content-Type-Options"] == "nosniff"
