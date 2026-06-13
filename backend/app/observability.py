"""관측성(observability) — 의존성 없이 stdlib만 사용(gap 8).

- 구조화 로깅: stdlib `logging`을 JSON 한 줄 포맷으로 모듈 로드 시 1회 설정.
  기존 `print`는 건드리지 않는다. 과하지 않게(요청 단위 로깅은 미들웨어가 담당하지 않고,
  여기서는 포맷 설정 + 헬스/메트릭 카운터만 제공).
- 요청/에러 카운터: FastAPI `@app.middleware("http")`로 집계. Prometheus 텍스트 노출.
- `/health`·`/metrics` 엔드포인트는 각 앱에서 `install_observability(app)`로 배선한다.

새 의존성 없음(stdlib only) — prometheus_client 등 미사용.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

# ── 구조화 로깅(JSON 한 줄) — 모듈 로드 시 1회 설정 ───────────────────────────
_LOGGER_NAME = "rubicon"


class _JsonLineFormatter(logging.Formatter):
    """로그 레코드를 JSON 한 줄로 직렬화(stdlib only)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # 추가 컨텍스트(extra=...)가 있으면 합친다.
        for key, val in getattr(record, "__dict__", {}).items():
            if key.startswith("ctx_"):
                payload[key[4:]] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> logging.Logger:
    """JSON 한 줄 포맷 핸들러를 rubicon 로거에 1회 부착(중복 부착 방지)."""
    logger = logging.getLogger(_LOGGER_NAME)
    if not any(isinstance(h.formatter, _JsonLineFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonLineFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # 루트로 중복 전파 방지(print/uvicorn 로그와 섞이지 않게)
    return logger


log = _configure_logging()


# ── 메트릭 카운터(인메모리, stdlib) ──────────────────────────────────────────
class _Metrics:
    """프로세스 단위 요청/에러 카운터 + 가동시간."""

    def __init__(self) -> None:
        self.requests = 0
        self.errors = 0
        self.started = time.monotonic()

    def uptime(self) -> float:
        return time.monotonic() - self.started

    def prometheus(self, service: str) -> str:
        """Prometheus 텍스트 노출 포맷."""
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


def install_observability(app, service: str = "backend") -> _Metrics:
    """`/health`·`/metrics` 엔드포인트 + 요청/에러 카운트 미들웨어를 앱에 설치.

    미들웨어는 응답을 변형하지 않고(스트리밍/봉투 불변) 카운터만 증가시킨다.
    예외가 위로 전파되면 에러로 집계 후 재던진다(기존 에러 처리 불변).
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

    @app.get("/health")
    def _health():
        return {"status": "ok", "uptime_seconds": round(metrics.uptime(), 3)}

    @app.get("/metrics")
    def _metrics():
        return Response(content=metrics.prometheus(service),
                        media_type="text/plain; version=0.0.4")

    return metrics
