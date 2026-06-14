"""플랫폼 횡단 배선(wiring) — 앱 팩토리에 미들웨어·라이프사이클을 등록하는 시임(ADR-0056).

병렬 작업 스트림이 `internal.py`의 같은 라인을 동시에 편집하지 않도록, 각 스트림은 자기 모듈에서
`@register_middleware`/`@register_startup`/`@register_shutdown`로 등록만 하고, 앱 팩토리는
`wiring.apply(app)` 한 번으로 적용한다(공유 파일 충돌 회피).
"""
from .wiring import (
    apply,
    register_middleware,
    register_shutdown,
    register_startup,
)

__all__ = ["apply", "register_middleware", "register_startup", "register_shutdown"]
