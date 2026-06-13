"""BFF 관측성 — 의존성 없이 stdlib만 사용(gap 8).

BE의 backend/app/observability.py와 동형(별도 서브시스템이라 코드 공유 대신 미러).
- 구조화 로깅: stdlib `logging` JSON 한 줄 포맷, 모듈 로드 시 1회 설정(print 불변).
- 요청/에러 카운터: `@app.middleware("http")`로 집계, Prometheus 텍스트 노출.
- `/metrics`(+옵션 `/health`)를 `install_observability(app)`로 배선.
  BFF는 이미 `/health`가 있으므로 기본은 `/metrics`만 추가하고 카운터 미들웨어를 건다.

새 의존성 없음(stdlib only).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

_LOGGER_NAME = "rubicon.bff"


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, val in getattr(record, "__dict__", {}).items():
            if key.startswith("ctx_"):
                payload[key[4:]] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if not any(isinstance(h.formatter, _JsonLineFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonLineFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


log = _configure_logging()


class _Metrics:
    def __init__(self) -> None:
        self.requests = 0
        self.errors = 0
        self.started = time.monotonic()

    def uptime(self) -> float:
        return time.monotonic() - self.started

    def prometheus(self, service: str) -> str:
        lines = [
            "# HELP rubicon_requests_total Total HTTP requests handled.",
            "# TYPE rubicon_requests_total counter",
            f'rubicon_requests_total{{service="{service}"}} {self.requests}',
            "# HELP rubicon_errors_total Total HTTP responses with status >= 500 or unhandled errors.",
            "# TYPE rubicon_errors_total counter",
            f'rubicon_errors_total{{service="{service}"}} {self.errors}',
            "# HELP rubicon_uptime_seconds Process uptime in seconds.",
            "# TYPE rubicon_uptime_seconds gauge",
            f'rubicon_uptime_seconds{{service="{service}"}} {self.uptime():.3f}',
        ]
        return "\n".join(lines) + "\n"


def install_observability(app, service: str = "bff", add_health: bool = False) -> _Metrics:
    """`/metrics`(+옵션 `/health`) + 요청/에러 카운트 미들웨어를 앱에 설치.

    미들웨어는 응답을 변형하지 않는다(WS·스트리밍·봉투 중계 불변).
    BFF는 기존 `/health`가 있으므로 add_health 기본 False.
    """
    from fastapi import Response

    metrics = _Metrics()

    @app.middleware("http")
    async def _count(request, call_next):
        metrics.requests += 1
        try:
            response = await call_next(request)
        except Exception:
            metrics.errors += 1
            raise
        if response.status_code >= 500:
            metrics.errors += 1
        return response

    if add_health:
        @app.get("/health")
        def _health():
            return {"status": "ok", "uptime_seconds": round(metrics.uptime(), 3)}

    @app.get("/metrics")
    def _metrics():
        return Response(content=metrics.prometheus(service),
                        media_type="text/plain; version=0.0.4")

    return metrics
