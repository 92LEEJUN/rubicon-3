"""BFF 보안 응답 헤더 + 통합 설치 시임(S7, ADR-0063, 요구사항 2).

표준 보안 헤더를 응답에 **추가**(추가형 — 이미 있으면 비덮어쓰기, 본문 불변). OWASP 권고
(클릭재킹·MIME 스니핑·레퍼러 누출) 공격면을 줄인다. 새 의존성 없음(stdlib + FastAPI만).

`install_security(app, audit=None)`는 관측성(`install_observability`)과 동형의 앱 팩토리 시임으로,
레이트리밋(`install_ratelimit`)과 보안 헤더(`install_security_headers`)를 한 번에 배선한다.

**토글 `SECURITY_HEADERS` 기본 off → 미들웨어 미등록 = 회귀 불변**(요구사항 6).
"""
from __future__ import annotations

import os

from .ratelimit import install_ratelimit

# 표준 보안 응답 헤더(추가형). 값은 보수적 기본.
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",  # 현대 브라우저는 비활성 권고(CSP로 대체)
    "Cross-Origin-Opener-Policy": "same-origin",
}


def _headers_enabled() -> bool:
    return (os.getenv("SECURITY_HEADERS", "").strip().lower() in ("1", "true", "yes", "on"))


def install_security_headers(app) -> bool:
    """토글 on일 때만 보안 헤더 미들웨어를 설치한다(요구사항 2·6).

    추가형: 응답에 이미 같은 헤더가 있으면 덮어쓰지 않는다(요구사항 2.3). off면 미등록(회귀 불변).
    반환값: 설치되었는지 여부.
    """
    if not _headers_enabled():
        return False

    @app.middleware("http")
    async def _add_security_headers(request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            if name not in response.headers:
                response.headers[name] = value
        return response

    return True


def install_security(app, audit=None) -> None:
    """앱 팩토리 시임 — 레이트리밋 + 보안 헤더를 토글에 따라 배선(요구사항 1·2·6).

    두 토글이 모두 off(기본)면 어떤 미들웨어도 등록되지 않아 오늘과 동일하게 동작한다(회귀 불변).
    """
    install_ratelimit(app, audit=audit)
    install_security_headers(app)
