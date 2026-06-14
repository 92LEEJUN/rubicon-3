"""관측성 미들웨어 — 요청 상관관계(request_id) + 구조화 요청 로그 + 추적 span(S1).

`wiring.register_middleware`로 등록만 한다(앱 팩토리 비편집, ADR-0056). `apply(app)` 시 부착.
- **request_id**: 인바운드 `X-Request-Id` 헤더를 이어받거나 새로 생성, ContextVar에 바인딩하고
  응답 헤더로 에코. 같은 요청의 로그·span이 이 ID로 상관관계를 가진다.
- **구조화 요청 로그**: settings.log_level/log_json을 따르는 `rubicon` 로거로 요청 1줄(method·path·
  status·지연·request_id). 카운팅/지연 히스토그램은 install 미들웨어가 담당(이중 집계 방지) —
  여기서는 로깅·상관관계만.
- **추적 span**: 토글 `TRACING` on일 때만 요청을 감싸는 server span 생성(off=Noop=회귀 불변).

이 미들웨어는 install 미들웨어보다 **바깥(priority 낮음)** 에 둔다 → request_id가 먼저 바인딩되어
안쪽 로깅/카운팅이 상관관계를 본다. 토글 무관하게 상관관계·로깅은 항상 동작하되 응답은 불변.
"""
from __future__ import annotations

import time

from ..platform import wiring
from .logging_setup import log
from .request_context import REQUEST_ID_HEADER, bind_request_id, reset_request_id
from .tracing import get_tracer


@wiring.register_middleware(priority=10)
def install_obs_middleware(app) -> None:
    """요청 상관관계·구조화 로그·추적 span 미들웨어를 앱에 부착."""

    @app.middleware("http")
    async def _obs(request, call_next):
        inbound = request.headers.get(REQUEST_ID_HEADER)
        rid, token = bind_request_id(inbound)
        start = time.monotonic()
        tracer = get_tracer(service="backend")
        method = request.method
        path = request.url.path
        try:
            with tracer.start_span("http.request", method=method, path=path) as span:
                try:
                    response = await call_next(request)
                except Exception:
                    span.set_attribute("error", True)
                    _log_request(method, path, status=500,
                                 dur=time.monotonic() - start, error=True)
                    raise
                span.set_attribute("http.status_code", response.status_code)
                response.headers[REQUEST_ID_HEADER] = rid
                _log_request(method, path, status=response.status_code,
                             dur=time.monotonic() - start,
                             error=response.status_code >= 500)
                return response
        finally:
            reset_request_id(token)


def _log_request(method: str, path: str, *, status: int, dur: float,
                 error: bool) -> None:
    """요청 1줄 구조화 로그. 에러(5xx/예외)는 WARNING, 그 외 INFO."""
    level = log.warning if error else log.info
    level(
        "http_request",
        extra={
            "ctx_event": "http_request",
            "ctx_method": method,
            "ctx_path": path,
            "ctx_status": status,
            "ctx_duration_ms": round(dur * 1000, 3),
        },
    )
