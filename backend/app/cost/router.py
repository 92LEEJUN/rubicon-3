"""LLM 비용 메트릭 노출 라우터 — `/metrics/llm`(ADR-0062, S6).

ADR-0057 `/metrics`(S1 소유)를 편집하지 않고, 비용/토큰 시리즈를 **별도 엔드포인트**로 Prometheus
텍스트 노출한다(같은 규약·신규 시리즈 이름). `wiring.register_router`로 배선해 앱 팩토리
(`api/internal.py`)를 건드리지 않는다(ADR-0056). `COST_TRACKING` off면 누적이 0이라 무해(회귀 불변).
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from ..platform import wiring
from .accounting import get_cost_metrics

router = APIRouter(tags=["cost"])


@router.get("/metrics/llm")
def llm_metrics() -> Response:
    return Response(
        content=get_cost_metrics().prometheus("backend"),
        media_type="text/plain; version=0.0.4",
    )


wiring.register_router(router)
