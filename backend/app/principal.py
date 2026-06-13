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


def merge_principal_state(container, guest_id: str, user_id: str) -> dict:
    """게스트(`guest:<token>`) 상태를 로그인 사용자(`user_id`)로 이관(요구사항 2-4, design §3).

    상태 리포는 user_id로 키잉돼 있으므로 머지 = **re-keying**(guest_id → user_id)이다.
    이관 후 게스트 행은 비운다(중복/누수 방지). 옮긴 항목 수를 요약으로 반환한다.

    엣지 케이스:
    - **conversation 충돌**: 로그인 사용자에게 이미 메모리가 있으면 게스트 요약/사실로
      **덮어쓰지 않는다**(로그인 상태가 진실의 출처). 게스트 메모리는 버려지고 conversation=0.
      사용자가 비어 있을 때만 이관(가장 흔한 케이스 — 게스트로 담다가 로그인).
    - **open-loop ref 충돌**: 같은 ref가 양쪽에 있으면 upsert로 게스트 값이 사용자 값을 덮는다
      (멱등 upsert 동작과 동일 — 게스트가 더 최근 작업 맥락이라는 가정).
    - **engagement 키 충돌**: 같은 ref면 게스트 기록으로 덮어쓴다(record는 upsert).
    - 게스트 비우기는 **best-effort** — 리포가 삭제 메서드(`delete`/`clear`/`delete_user`)를
      제공하지 않으면(인메모리 engagement) 게스트 행이 남을 수 있다(재키잉은 이미 완료).
    """
    summary = {"orders": 0, "conversation": 0, "open_loops": 0, "engagement": 0}

    # ── 주문 — OrderPort.reassign_user(re-key) ───────────────────────────────
    port = getattr(container.order, "_port", None)
    if port is not None and hasattr(port, "reassign_user"):
        summary["orders"] = port.reassign_user(guest_id, user_id)

    # ── 대화 메모리 — 사용자가 비어 있을 때만 이관(충돌 시 로그인 우선) ──────────
    conv = container.conversation_memory
    guest_mem = conv.get(guest_id)
    existing = conv.get(user_id)
    has_guest = bool(guest_mem.summary or guest_mem.facts or guest_mem.summarized_through)
    has_user = bool(existing.summary or existing.facts or existing.summarized_through)
    if has_guest and not has_user:
        conv.save(user_id, guest_mem)
        summary["conversation"] = 1
    if hasattr(conv, "delete"):
        conv.delete(guest_id)

    # ── 미해결 스레드(open-loop) — list_open → upsert(user) → clear(guest) ──────
    loops_repo = container.companion.open_loops_repo
    moved_loops = loops_repo.list_open(guest_id)
    for loop in moved_loops:
        loops_repo.upsert(user_id, loop)
    summary["open_loops"] = len(moved_loops)
    if hasattr(loops_repo, "clear"):
        loops_repo.clear(guest_id)

    # ── Engagement — record(user) 재키잉, 게스트 비우기는 best-effort ───────────
    eng = container.engagement
    guest_recs = eng.list(guest_id)
    for rec in guest_recs:
        eng.record(user_id, rec.ref, rec.state)
    summary["engagement"] = len(guest_recs)
    if hasattr(eng, "delete_user"):
        eng.delete_user(guest_id)

    return summary


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
