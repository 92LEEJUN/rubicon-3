"""관측성(observability) 패키지 — stdlib only, S1 스트림(12-Factor #14, ADR-0057).

기존 단일 모듈(`observability.py`)을 패키지로 분리하면서 **공개 API는 그대로** 유지한다:
`from ..observability import install_observability, log` 가 계속 동작한다(회귀 불변).

구성:
- `install.py` — `install_observability(app)` 엔드포인트(/health·/metrics) + 카운팅/지연 미들웨어.
- `logging_setup.py` — settings(log_level/log_json) 기반 구조화 로깅.
- `metrics.py` — 요청/에러 카운터 + 지연 히스토그램(Prometheus 텍스트).
- `request_context.py` — request_id 상관관계(ContextVar).
- `tracing.py` — OTel 스타일 tracer 인터페이스 + 콘솔/Mock exporter(토글 `TRACING` 뒤).
- `middleware_obs.py` — wiring 등록 미들웨어(상관관계·로깅·span). registry가 로드해 배선.
"""
from __future__ import annotations

from .install import install_observability
from .logging_setup import configure_logging, log
from .metrics import DEFAULT_BUCKETS, Metrics, get_shared
from .request_context import (
    REQUEST_ID_HEADER,
    bind_request_id,
    get_request_id,
    new_request_id,
    reset_request_id,
)
from .tracing import (
    ConsoleExporter,
    MockExporter,
    NoopTracer,
    Span,
    Tracer,
    get_tracer,
    tracing_enabled,
)

__all__ = [
    "install_observability",
    "log",
    "configure_logging",
    "Metrics",
    "DEFAULT_BUCKETS",
    "get_shared",
    "REQUEST_ID_HEADER",
    "bind_request_id",
    "get_request_id",
    "new_request_id",
    "reset_request_id",
    "Span",
    "Tracer",
    "NoopTracer",
    "ConsoleExporter",
    "MockExporter",
    "get_tracer",
    "tracing_enabled",
]
