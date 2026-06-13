"""BFF 관측성(gap 8) — /health·/metrics. stdlib only, 중계/스트림 SHAPE 불변."""
import httpx
from fastapi.testclient import TestClient

from gateway.backend_client import BackendClient
from gateway.main import create_app


def _client() -> TestClient:
    """BE 호출이 없는 헬스/메트릭 경로만 검증 — 더미 BE로 충분."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    return TestClient(create_app(BackendClient(base_url="http://be", transport=transport)))


def test_health_ok():
    r = _client().get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_exposes_counters():
    r = _client().get("/metrics")
    assert r.status_code == 200
    assert "rubicon_requests_total" in r.text
    assert "rubicon_errors_total" in r.text


def test_metrics_request_counter_increases():
    client = _client()
    n_before = _counter(client.get("/metrics").text, "rubicon_requests_total")
    client.get("/health")
    n_after = _counter(client.get("/metrics").text, "rubicon_requests_total")
    assert n_after > n_before


def _counter(text: str, name: str) -> float:
    for line in text.splitlines():
        if line.startswith(name) and not line.startswith("#"):
            return float(line.rsplit(" ", 1)[1])
    raise AssertionError(f"counter {name} not found in metrics")
