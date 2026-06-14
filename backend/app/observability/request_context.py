"""요청 상관관계(request_id) 컨텍스트 — stdlib `contextvars`만 사용(S1 관측성).

요청 단위로 고유 `request_id`를 만들어 ContextVar에 보관한다. 같은 요청을 처리하는 동안
로그·트레이스가 이 값을 읽어 상관관계를 부여한다. 미들웨어가 요청 시작 시 `bind_request_id`로
설정하고 끝에 `reset_request_id`로 되돌린다(누수 방지). 미들웨어 밖(배치·테스트)에서는 None.

새 의존성 없음(stdlib only).
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar, Token

# 인바운드 헤더로 들어온 상관관계 ID를 이어받을 때 쓰는 표준 헤더 이름(분산 추적 호환).
REQUEST_ID_HEADER = "x-request-id"

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    """짧고 충돌 가능성 낮은 요청 ID 생성(uuid4 hex 32자)."""
    return uuid.uuid4().hex


def get_request_id() -> str | None:
    """현재 컨텍스트의 요청 ID(없으면 None)."""
    return _request_id.get()


def bind_request_id(request_id: str | None = None) -> tuple[str, Token]:
    """요청 ID를 컨텍스트에 설정. 인자가 없거나 비면 새로 생성한다.

    반환: (설정된 request_id, reset 토큰). 토큰은 `reset_request_id`에 넘긴다.
    """
    rid = request_id or new_request_id()
    token = _request_id.set(rid)
    return rid, token


def reset_request_id(token: Token) -> None:
    """`bind_request_id`가 돌려준 토큰으로 이전 값을 복원(컨텍스트 누수 방지)."""
    _request_id.reset(token)
