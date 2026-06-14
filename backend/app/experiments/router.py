"""실험 할당 엔드포인트(신규 라우터) — `/internal/experiments/*`(ADR-0064).

`wiring.register_router`로 등록한다(앱 팩토리 `api/internal.py` 미편집, ADR-0056).
신원은 기존 패턴과 동일하게 헤더(X-User-Id/X-Guest-Token) → Principal → unit_id로 해석한다.
토글 `EXPERIMENTS` off면 항상 control(회귀 불변).
"""
from __future__ import annotations

from fastapi import APIRouter, Header

from ..platform import wiring
from .assignment import variant_for
from .registry import REGISTRY, default_registry

router = APIRouter(prefix="/internal/experiments", tags=["experiments"])

# 예시 실험 시드(레지스트리 비어 있으면). 토글 off면 동작 영향 없음.
if not REGISTRY:
    default_registry()


def _unit(x_user_id: str | None, x_guest_token: str | None) -> str:
    """헤더 신원 → 안정적 unit_id(Principal 해석, 기존 패턴 재사용)."""
    from ..principal import resolve_principal
    return resolve_principal(x_user_id, x_guest_token).id


@router.get("/assign")
def assign_experiments(
    keys: str | None = None,
    expose: bool = True,
    x_user_id: str | None = Header(default=None),
    x_guest_token: str | None = Header(default=None),
):
    """키별 variant 할당 맵 반환(+노출 기록).

    - `keys`: 콤마 구분 실험 키. 생략 시 레지스트리 전체.
    - `expose`: True면 노출(experiment_exposed) 기록(control은 미노출).
    """
    unit = _unit(x_user_id, x_guest_token)
    principal = x_user_id or x_guest_token
    if keys:
        wanted = [k.strip() for k in keys.split(",") if k.strip()]
    else:
        wanted = list(REGISTRY.keys())
    assignments = {
        k: variant_for(k, unit, expose=expose, principal=principal)
        for k in wanted
    }
    return {"unit": unit, "assignments": assignments}


# 앱에 부착(priority 기본). registry.py가 본 모듈을 import하면 1회 실행.
wiring.register_router(router)
