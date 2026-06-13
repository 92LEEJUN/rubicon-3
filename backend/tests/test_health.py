"""관측성(gap 8) — /health·/internal/health·/metrics. stdlib only, 응답 SHAPE 불변."""
from fastapi.testclient import TestClient

from app.api.internal import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_internal_health_ok():
    r = client.get("/internal/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_exposes_counters():
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "rubicon_requests_total" in r.text
    assert "rubicon_errors_total" in r.text


def test_metrics_request_counter_increases():
    before = client.get("/metrics").text
    n_before = _counter(before, "rubicon_requests_total")
    client.get("/internal/devices")  # 임의 요청 1+
    after = client.get("/metrics").text
    n_after = _counter(after, "rubicon_requests_total")
    assert n_after > n_before


def _counter(text: str, name: str) -> float:
    for line in text.splitlines():
        if line.startswith(name) and not line.startswith("#"):
            return float(line.rsplit(" ", 1)[1])
    raise AssertionError(f"counter {name} not found in metrics")
