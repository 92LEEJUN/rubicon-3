"""앱 배선 레지스트리 — 미들웨어·라이프사이클 훅을 append-only로 모은다(ADR-0056).

각 스트림(관측성·회복력·보안 등)은 자기 모듈에서 등록만 하고, 앱은 `apply(app)`로 일괄 적용한다.
등록 순서는 추가 순서를 따른다(미들웨어는 후입선출이 아니라 추가 순서대로 적용; 스트림 간 순서
의존이 있으면 priority로 정렬할 수 있게 (prio, fn) 보관).
"""
from __future__ import annotations

from typing import Callable

# (priority, fn) — 낮은 priority 먼저. fn(app) -> None
_MIDDLEWARES: list[tuple[int, Callable]] = []
_STARTUP: list[tuple[int, Callable]] = []
_SHUTDOWN: list[tuple[int, Callable]] = []
_ROUTERS: list[tuple[int, object]] = []   # (priority, APIRouter) — app.include_router로 부착


def register_middleware(fn: Callable | None = None, *, priority: int = 100):
    """미들웨어 설치 함수 등록 — `fn(app)`이 `app`에 미들웨어를 붙인다."""
    def _wrap(f: Callable) -> Callable:
        _MIDDLEWARES.append((priority, f))
        return f
    return _wrap(fn) if fn is not None else _wrap


def register_startup(fn: Callable | None = None, *, priority: int = 100):
    def _wrap(f: Callable) -> Callable:
        _STARTUP.append((priority, f))
        return f
    return _wrap(fn) if fn is not None else _wrap


def register_shutdown(fn: Callable | None = None, *, priority: int = 100):
    def _wrap(f: Callable) -> Callable:
        _SHUTDOWN.append((priority, f))
        return f
    return _wrap(fn) if fn is not None else _wrap


def register_router(router: object, *, priority: int = 100) -> object:
    """APIRouter 등록 — `apply`가 `app.include_router(router)`로 부착(스트림 엔드포인트용)."""
    _ROUTERS.append((priority, router))
    return router


def apply(app) -> None:
    """등록된 미들웨어·라우터·라이프사이클 훅을 앱에 적용(priority 순)."""
    for _, fn in sorted(_MIDDLEWARES, key=lambda x: x[0]):
        fn(app)
    for _, router in sorted(_ROUTERS, key=lambda x: x[0]):
        app.include_router(router)
    for _, fn in sorted(_STARTUP, key=lambda x: x[0]):
        app.add_event_handler("startup", fn)
    for _, fn in sorted(_SHUTDOWN, key=lambda x: x[0]):
        app.add_event_handler("shutdown", fn)


def _reset() -> None:
    """테스트용 — 레지스트리 초기화."""
    _MIDDLEWARES.clear()
    _STARTUP.clear()
    _SHUTDOWN.clear()
    _ROUTERS.clear()
