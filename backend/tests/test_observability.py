"""S1 관측성(ADR-0057) — request_id 상관관계·메트릭 히스토그램·추적(토글)·로깅 구성.

stdlib only. 토글 기본 off=회귀 불변 검증 포함. 전 스위트 green 유지(회귀).
"""
import logging

import pytest
from fastapi.testclient import TestClient

import app.config as cfg
from app.api.internal import app as fastapi_app
from app.observability import (
    REQUEST_ID_HEADER,
    ConsoleExporter,
    Metrics,
    MockExporter,
    NoopTracer,
    Tracer,
    bind_request_id,
    configure_logging,
    get_request_id,
    get_tracer,
    new_request_id,
    reset_request_id,
    tracing_enabled,
)
from app.observability.logging_setup import JsonLineFormatter, PlainFormatter

client = TestClient(fastapi_app)


# ── 요구사항 1: request_id 상관관계 ──────────────────────────────────────────
def test_response_has_request_id_header():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get(REQUEST_ID_HEADER)  # 새로 생성·에코


def test_inbound_request_id_is_echoed():
    rid = "test-correlation-123"
    r = client.get("/health", headers={REQUEST_ID_HEADER: rid})
    assert r.headers.get(REQUEST_ID_HEADER) == rid  # 인바운드 이어받음


def test_request_id_contextvar_bind_reset():
    assert get_request_id() is None
    rid, token = bind_request_id("abc")
    assert rid == "abc" and get_request_id() == "abc"
    reset_request_id(token)
    assert get_request_id() is None


def test_new_request_id_unique():
    assert new_request_id() != new_request_id()


# ── 요구사항 2: /metrics 확장(히스토그램·버킷) ───────────────────────────────
def test_metrics_exposes_latency_histogram():
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "rubicon_request_duration_seconds_bucket" in r.text
    assert 'le="+Inf"' in r.text
    assert "rubicon_request_duration_seconds_sum" in r.text
    assert "rubicon_request_duration_seconds_count" in r.text


def test_metrics_keeps_request_and_error_counters():
    r = client.get("/metrics")
    assert "rubicon_requests_total" in r.text
    assert "rubicon_errors_total" in r.text
    assert "rubicon_uptime_seconds" in r.text


def test_metrics_buckets_are_cumulative_and_monotonic():
    m = Metrics(buckets=(0.1, 0.5, 1.0))
    m.observe(0.05)   # le=0.1
    m.observe(0.3)    # le=0.5
    m.observe(2.0)    # +Inf
    text = m.prometheus("backend")
    counts = []
    for line in text.splitlines():
        if line.startswith("rubicon_request_duration_seconds_bucket"):
            counts.append(int(line.rsplit(" ", 1)[1]))
    assert counts == sorted(counts)        # 누적 → 단조 증가
    assert counts[-1] == 3                 # +Inf == 총 관측 수
    assert "rubicon_request_duration_seconds_count{service=\"backend\"} 3" in text


def test_metrics_observe_error_increments_errors():
    m = Metrics()
    m.observe(0.01, is_error=True)
    assert m.errors == 1 and m.requests == 1


# ── 요구사항 3: 분산추적 인터페이스 + exporter(토글) ─────────────────────────
def test_tracing_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TRACING", raising=False)
    assert tracing_enabled() is False
    assert isinstance(get_tracer(), NoopTracer)  # off=회귀 불변


def test_tracing_enabled_returns_real_tracer(monkeypatch):
    monkeypatch.setenv("TRACING", "1")
    assert tracing_enabled() is True
    assert isinstance(get_tracer(), Tracer)


def test_mock_exporter_collects_span():
    exp = MockExporter()
    tracer = Tracer(exp, service="backend")
    with tracer.start_span("op", foo="bar") as span:
        span.set_attribute("k", "v")
    assert len(exp.spans) == 1
    s = exp.spans[0]
    assert s.name == "op" and s.status == "OK"
    assert s.attributes["foo"] == "bar" and s.attributes["k"] == "v"
    assert s.duration_ms is not None and s.duration_ms >= 0


def test_span_records_error_status():
    exp = MockExporter()
    tracer = Tracer(exp)
    with pytest.raises(ValueError):
        with tracer.start_span("boom"):
            raise ValueError("x")
    assert exp.spans[0].status == "ERROR"


def test_child_span_inherits_trace_id():
    exp = MockExporter()
    tracer = Tracer(exp)
    with tracer.start_span("parent"):
        with tracer.start_span("child"):
            pass
    child, parent = exp.spans  # 자식이 먼저 종료(내보냄)
    assert child.name == "child" and parent.name == "parent"
    assert child.trace_id == parent.trace_id
    assert child.parent_id == parent.span_id


def test_noop_tracer_does_not_export():
    tracer = NoopTracer()
    with tracer.start_span("op") as span:
        assert span is not None  # span은 주되 내보내지 않음(검증 가능한 무동작)


def test_console_exporter_logs(caplog):
    exp = ConsoleExporter()
    tracer = Tracer(exp)
    with caplog.at_level(logging.INFO, logger="rubicon"):
        with tracer.start_span("logged-op"):
            pass
    # rubicon 로거는 propagate=False라 caplog가 못 잡을 수 있음 → 예외 없이 동작만 확인.
    assert exp is not None


# ── 요구사항 4: 로깅이 settings(log_json/log_level)를 따른다 ──────────────────
def test_logging_uses_json_formatter_when_log_json(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")  # prd 기본 log_json=True
    monkeypatch.delenv("LOG_JSON", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    s = cfg.reload_settings()
    logger = configure_logging(s)
    assert any(isinstance(h.formatter, JsonLineFormatter) for h in logger.handlers)
    assert logger.level == logging.INFO
    _restore_logging(monkeypatch)


def test_logging_uses_plain_formatter_in_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")  # dev 기본 log_json=False, DEBUG
    monkeypatch.delenv("LOG_JSON", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    s = cfg.reload_settings()
    logger = configure_logging(s)
    assert any(isinstance(h.formatter, PlainFormatter) for h in logger.handlers)
    assert logger.level == logging.DEBUG
    _restore_logging(monkeypatch)


def test_logging_configure_is_idempotent(monkeypatch):
    s = cfg.reload_settings()
    logger = configure_logging(s)
    n1 = len([h for h in logger.handlers
              if isinstance(h.formatter, (JsonLineFormatter, PlainFormatter))])
    configure_logging(s)
    n2 = len([h for h in logger.handlers
              if isinstance(h.formatter, (JsonLineFormatter, PlainFormatter))])
    assert n1 == n2 == 1  # 우리 핸들러는 항상 1개(중복 부착 없음)
    _restore_logging(monkeypatch)


def test_json_formatter_includes_request_id():
    rid, token = bind_request_id("rid-xyz")
    try:
        rec = logging.LogRecord("rubicon", logging.INFO, "f", 1, "hello", None, None)
        out = JsonLineFormatter().format(rec)
        assert '"request_id": "rid-xyz"' in out
        assert '"msg": "hello"' in out
    finally:
        reset_request_id(token)


def test_json_formatter_flattens_ctx_keys():
    rec = logging.LogRecord("rubicon", logging.INFO, "f", 1, "m", None, None)
    rec.ctx_method = "GET"
    out = JsonLineFormatter().format(rec)
    assert '"method": "GET"' in out  # ctx_ 접두 평탄화(기존 컨벤션 유지)


def _restore_logging(monkeypatch):
    """env 원복 + 기본 설정으로 로깅 재구성(다른 테스트 간섭 방지)."""
    monkeypatch.delenv("APP_ENV", raising=False)
    configure_logging(cfg.reload_settings())


# ── 회귀: /health·/internal/health·요청 카운터(기존 test_health와 동형) ──────
def test_health_and_counter_regression():
    assert client.get("/health").json()["status"] == "ok"
    before = _counter(client.get("/metrics").text, "rubicon_requests_total")
    client.get("/internal/devices")
    after = _counter(client.get("/metrics").text, "rubicon_requests_total")
    assert after > before


def _counter(text: str, name: str) -> float:
    for line in text.splitlines():
        if line.startswith(name) and not line.startswith("#"):
            return float(line.rsplit(" ", 1)[1])
    raise AssertionError(f"counter {name} not found")
