"""요청 신원(Principal) — 로그인 사용자 / 비로그인 게스트(멀티테넌트, specs/multi-tenant-state).

내부 API는 BFF가 인증한 신원을 신뢰한다(api-contract §2.4). 상태 리포는 이미 user_id로 키잉돼
있으므로(멀티테넌트 준비됨), 본 모듈은 **요청 → Principal → User 프로필** 해석만 담당한다.

토글 `MULTITENANT`(기본 off)면 항상 기본 사용자로 폴백 → 오늘 동작과 동일(회귀 보존, 요구사항 7).
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Optional

from . import fixtures as fx
from .domain import User

DEFAULT_USER_ID = "usr_01"


@dataclass(frozen=True)
class Principal:
    kind: str   # "user" | "guest"
    id: str

    @property
    def is_guest(self) -> bool:
        return self.kind == "guest"


def default_principal() -> Principal:
    """기본 사용자(회귀·토글 off)."""
    return Principal("user", DEFAULT_USER_ID)


def guest_principal(token: Optional[str] = None) -> Principal:
    """비로그인 게스트 — 안정적 식별자(`guest:<token>`). 토큰 없으면 발급."""
    tok = (token or uuid.uuid4().hex[:12]).removeprefix("guest:")
    return Principal("guest", f"guest:{tok}")


def multitenant_enabled() -> bool:
    """멀티테넌트 신원 해석 토글(기본 off → 기본 사용자)."""
    return os.getenv("MULTITENANT", "").strip().lower() in ("1", "true", "yes", "on")


def resolve_principal(user_id: Optional[str] = None,
                      guest_token: Optional[str] = None) -> Principal:
    """요청 신원 → Principal. 토글 off거나 신원 없으면 폴백(요구사항 2·7).

    - user_id 있음 → 로그인 사용자
    - 없음 + 게스트 토큰 → 해당 게스트
    - 둘 다 없음 → 새 게스트(토큰 발급)
    """
    if not multitenant_enabled():
        return default_principal()
    if user_id:
        return Principal("user", user_id)
    return guest_principal(guest_token)


class UserDirectory:
    """principal_id → User 프로필. 기본 사용자는 fixture, 게스트/미지의 id는 최소 프로필 합성."""

    def __init__(self) -> None:
        u = User.model_validate(fx.USER)
        self._users: dict[str, User] = {u.id: u}

    def get(self, principal: Principal) -> User:
        if principal.id in self._users:
            return self._users[principal.id]
        name = "게스트" if principal.is_guest else principal.id
        return User(id=principal.id, display_name=name)

    def upsert(self, user: User) -> None:
        self._users[user.id] = user
