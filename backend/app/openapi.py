"""API 성숙(S4 · ADR-0060) — 계약 버전 + OpenAPI export 헬퍼 + 버전 헤더 미들웨어.

추가형·하위호환만 — 기존 라우트/계약 형태·동작 불변(api-contract §7).
- `API_VERSION` : 날짜 기반 계약 버전 단일 소스(OpenAPI `info.x-api-version`·응답 헤더에 노출).
- `build_openapi(app)` : FastAPI 기본 schema에 `x-api-version`만 주입해 반환(기존 schema 불변).
- 버전 헤더 미들웨어 : `platform.wiring.register_middleware`로 등록(import 부수효과).
  `platform/registry.py`에 import 한 줄을 더해 이 모듈이 로드되게 한다(스트림 단일 append 지점).
  앱 팩토리(`api/internal.py`)는 `wiring.apply(app)`로만 적용 → 공유 라인 미편집(ADR-0056).

새 무거운 pip 의존성 없음(stdlib + 기존 FastAPI만).
"""
from __future__ import annotations

# 계약 버전(날짜 기반) — 파괴적 변경 시 올린다(api-contract §7.1·§7.2). 단일 소스.
API_VERSION = "2025-06-01"

# 응답 헤더명(추가형) — 본문/상태코드 불변, 진단·로깅용(api-contract §7.1).
API_VERSION_HEADER = "X-API-Version"


def build_openapi(app) -> dict:
    """FastAPI 기본 OpenAPI schema에 `info.x-api-version`만 주입해 반환(추가형).

    `app.openapi()`는 첫 호출에 schema를 생성·캐시한다. 우리는 그 위에 메타 한 키만 더한다 —
    기존 paths/components(라우트·모델)는 그대로다(계약 형태 불변).
    """
    schema = app.openapi()
    info = schema.setdefault("info", {})
    info["x-api-version"] = API_VERSION
    return schema


def _install_version_header(app) -> None:
    """응답에 `X-API-Version` 헤더를 부착하는 미들웨어 설치(본문/상태 불변).

    예외는 그대로 전파(기존 에러 처리 불변). 스트리밍/봉투는 만지지 않고 헤더만 더한다.
    """
    @app.middleware("http")
    async def _version_header(request, call_next):
        response = await call_next(request)
        response.headers[API_VERSION_HEADER] = API_VERSION
        return response


def register() -> None:
    """배선 시임에 버전 헤더 미들웨어를 등록(ADR-0056). 모듈 import 시 1회 호출된다.

    무등록 시 무동작(회귀 불변) — 등록되면 `wiring.apply(app)`가 일괄 설치한다.
    """
    from .platform import wiring
    wiring.register_middleware(_install_version_header, priority=50)


# import 부수효과로 등록(wiring.py가 이 모듈을 import하면 활성). 중복 import는 모듈 캐시로 1회.
register()
