"""관측성 설치 진입점 — `/health`·`/metrics` + 요청/에러/지연 집계(S1, stdlib only).

기존 `install_observability(app, service)` 시그니처를 그대로 유지한다(회귀 불변, internal.py가
직접 호출). 내부적으로는 S1에서 분리한 모듈을 조립한다:
- 구조화 로깅 구성은 `logging_setup`(settings의 log_level/log_json을 따름).
- 메트릭은 `metrics.Metrics`(요청/에러 카운터 + 지연 히스토그램). 이 인스턴스를 프로세스 공유
  슬롯에 등록 → wiring 미들웨어(상관관계·로깅)가 같은 인스턴스를 본다(이중 집계 방지).
- 카운팅·지연 측정은 **여기 설치하는 미들웨어**가 담당. wiring 미들웨어는 상관관계·로깅만.

새 의존성 없음(stdlib only) — prometheus_client 등 미사용.
"""
from __future__ import annotations

import time

from .logging_setup import log  # 모듈 로드 시 로깅 구성(기존 `log` 심볼 호환 재노출)
from .metrics import Metrics, set_shared

__all__ = ["install_observability", "log"]


def install_observability(app, service: str = "backend") -> Metrics:
    """`/health`·`/metrics` 엔드포인트 + 요청/에러/지연 집계 미들웨어를 앱에 설치.

    미들웨어는 응답을 변형하지 않고(스트리밍/봉투 불변) 메트릭만 기록한다.
    예외가 위로 전파되면 에러로 집계 후 재던진다(기존 에러 처리 불변).
    """
    from fastapi import Response

    metrics = Metrics()
    set_shared(metrics)  # wiring 미들웨어가 같은 인스턴스를 공유

    @app.middleware("http")
    async def _observe(request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            metrics.observe(time.monotonic() - start, is_error=True)
            raise
        metrics.observe(time.monotonic() - start,
                        is_error=response.status_code >= 500)
        return response

    @app.get("/health")
    def _health():
        return {"status": "ok", "uptime_seconds": round(metrics.uptime(), 3)}

    @app.get("/metrics")
    def _metrics():
        return Response(content=metrics.prometheus(service),
                        media_type="text/plain; version=0.0.4")

    return metrics
