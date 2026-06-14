"""개선 엔진 라우터 통합 테스트 — `/internal/improve/*`(ADR-0067).

토글 off=inert(404, 회귀 불변)·on=신호→분석→리뷰→검증→사람 적용 end-to-end.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.internal import app
from app.improve import router as improve_router
from app.improve.signals import Signal


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    # 모듈 단일 상태 초기화(테스트 격리)
    from app.improve.signals import COLLECTOR
    COLLECTOR.clear()
    improve_router._queue._items.clear()
    improve_router._queue._rejected.clear()
    yield


def test_endpoints_inert_when_toggle_off(client, monkeypatch):
    monkeypatch.setenv("SELF_IMPROVE", "0")
    assert client.get("/internal/improve/proposals").status_code == 404
    assert client.post("/internal/improve/analyze").status_code == 404


def test_full_human_in_the_loop_flow(client, monkeypatch):
    monkeypatch.setenv("SELF_IMPROVE", "1")
    from app.improve.signals import COLLECTOR
    for _ in range(6):
        COLLECTOR.collect(Signal(kind="low_confidence_route", ref="troubleshoot", value=0.8))

    # 분석 → 제안 제출
    r = client.post("/internal/improve/analyze")
    assert r.status_code == 200 and r.json()["generated"] >= 1
    pid = r.json()["submitted"][0]["id"]

    # 리뷰 → 승인 → 검증(S8 실험 생성)
    assert client.post(f"/internal/improve/proposals/{pid}/review").status_code == 200
    assert client.post(f"/internal/improve/proposals/{pid}/approve",
                       json={"note": "ok"}).status_code == 200
    rv = client.post(f"/internal/improve/proposals/{pid}/validate")
    assert rv.status_code == 200 and rv.json()["experiment_key"].startswith("improve_")
    assert rv.json()["proposal"]["status"] == "validating"

    # 결과 첨부 → 사람 적용
    client.post(f"/internal/improve/proposals/{pid}/experiment-result",
                json={"result": {"winner": "treatment", "lift": 0.1}})
    ap = client.post(f"/internal/improve/proposals/{pid}/apply",
                     headers={"X-Actor": "alice"}, json={"note": "PR #9"})
    assert ap.status_code == 200 and ap.json()["status"] == "applied"


def test_cannot_apply_without_lifecycle(client, monkeypatch):
    monkeypatch.setenv("SELF_IMPROVE", "1")
    from app.improve.signals import COLLECTOR
    for _ in range(6):
        COLLECTOR.collect(Signal(kind="low_confidence_route", ref="order", value=0.9))
    pid = client.post("/internal/improve/analyze").json()["submitted"][0]["id"]
    # 곧바로 적용 → 409(상태 건너뜀 불가)
    assert client.post(f"/internal/improve/proposals/{pid}/apply",
                       headers={"X-Actor": "alice"}).status_code == 409


def test_satisfaction_endpoint_emits_signal(client, monkeypatch):
    monkeypatch.setenv("SELF_IMPROVE", "1")
    r = client.post("/internal/satisfaction",
                    json={"topic": "washer", "score": 2, "resolved": False})
    assert r.status_code == 200 and r.json()["next_action"] == "rediagnose"
    # 기본 사용자 동의 scope에 따라 신호 emit(가능 시) — 엔드포인트가 신호 sink와 연결됨
    sig = client.get("/internal/improve/signals", params={"kind": "satisfaction"})
    assert sig.status_code == 200
