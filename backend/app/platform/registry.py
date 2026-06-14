"""스트림 모듈 임포트 진입점(ADR-0056) — append-only 단일 지점.

각 작업 스트림(관측성·회복력·보안·개인정보·실험 등)은 자기 모듈에서 `wiring.register_*`로 등록하고,
그 모듈이 **로드되도록** 아래에 import 한 줄을 추가한다. `api/internal.py`는 `registry`를 import한 뒤
`wiring.apply(app)`를 호출하므로, 스트림은 **이 파일에 한 줄 append**만 하면 앱 팩토리를 직접 편집하지
않는다(병렬 충돌 회피).

규칙: 한 스트림 = 한 import 줄. 추가 순. 부수효과(등록) 목적의 import이므로 noqa.
"""
from .. import openapi as _api_maturity  # noqa: F401  (S4: X-API-Version 헤더 등록)
from .. import resilience as _resilience  # noqa: F401  (S2 회복력 — RESILIENCE_ENABLED 시 shutdown 훅)
from ..cost import router as _cost_router  # noqa: F401  (S6 비용·캐싱: /metrics/llm 라우터)
from ..experiments import router as _experiments_router  # noqa: F401  (S8 실험 A/B 라우터)
from ..observability import middleware_obs as _obs_mw  # noqa: F401  (S1 관측성: 미들웨어 등록)
from ..privacy import router as _privacy_router  # noqa: F401  (S5 DSR 라우터)
