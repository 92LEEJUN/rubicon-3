"""인증/세션 게이트(api-contract §3) — MVP는 Mock 토큰 검증 + 게스트(비로그인) 지원.

토큰은 도메인 모델에 저장하지 않는다(architecture NFR). 검증 통과 시 고정 사용자 컨텍스트를 반환.
실 전환: 삼성 계정 SSO·세션 TTL·조용한 재인증.

신원(Identity) 해석:
- 토큰 있음  → 로그인 사용자 ("user", MOCK_USER_ID)
- 토큰 없음  → 게스트 ("guest", <guest_token: 쿼리/쿠키에서 받거나 새로 발급>)

게스트도 자문(advisory)·대화 턴은 허용한다. 커밋(주문/예약)은 BFF에서 막지 않고,
BE가 게스트에게 401 {code:"LoginRequired"} 를 반환하면 그대로 중계한다(공유 계약).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, Request

MOCK_USER_ID = "usr_01"


@dataclass(frozen=True)
class Identity:
    """해석된 신원. BE로 포워딩할 헤더/페이로드 필드를 만든다."""
    kind: str           # "user" | "guest"
    id: str             # user_id(로그인) | guest_token(게스트)

    @property
    def is_guest(self) -> bool:
        return self.kind == "guest"

    @property
    def user_id(self) -> Optional[str]:
        return self.id if self.kind == "user" else None

    @property
    def guest_token(self) -> Optional[str]:
        return self.id if self.kind == "guest" else None

    def headers(self) -> dict:
        """BE HTTP 호출에 실을 신원 헤더(X-User-Id | X-Guest-Token)."""
        if self.kind == "user":
            return {"X-User-Id": self.id}
        return {"X-Guest-Token": self.id}

    def ws_fields(self) -> dict:
        """BE /internal/turn WS 페이로드에 주입할 신원 필드."""
        return {"user_id": self.user_id, "guest_token": self.guest_token}


def _new_guest_token() -> str:
    return "g-" + uuid.uuid4().hex[:16]


def resolve_identity(authorization: Optional[str],
                     guest_token: Optional[str] = None) -> Identity:
    """토큰 유무로 신원을 해석한다(로그인 사용자 또는 게스트).

    - authorization 있음 → 로그인 사용자(MOCK_USER_ID)
    - authorization 없음 → 게스트. 전달받은 guest_token이 있으면 재사용, 없으면 새로 발급.
    """
    if authorization:
        return Identity("user", MOCK_USER_ID)
    return Identity("guest", guest_token or _new_guest_token())


# ── FastAPI 의존성 ───────────────────────────────────────────────────────────
def require_login(authorization: Optional[str] = Header(default=None)) -> Identity:
    """로그인 사용자만 허용(진짜 로그인이 필요한 엔드포인트용). 게스트/무토큰 → 401."""
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    return Identity("user", MOCK_USER_ID)


def identity_dep(request: Request,
                 authorization: Optional[str] = Header(default=None)) -> Identity:
    """사용자 또는 게스트 신원을 해석한다(자문·커밋 중계 경로 공용).

    게스트 토큰은 쿼리(?guest_token=) 또는 쿠키(guest_token)에서 받는다. 없으면 새로 발급.
    커밋 경로도 이 의존성을 쓴다 — BFF는 커밋을 막지 않고, 게스트면 BE가 401(LoginRequired)을
    돌려주고 BFF는 그대로 중계한다(공유 계약).
    """
    gt = request.query_params.get("guest_token") or request.cookies.get("guest_token")
    return resolve_identity(authorization, gt)


# ── 하위호환: 기존 호출부가 쓰던 이름 ────────────────────────────────────────
def require_auth(authorization: Optional[str] = Header(default=None)) -> str:
    """(레거시) 로그인 사용자 id 문자열을 반환. 무토큰 → 401."""
    return require_login(authorization).id


def ws_user(authorization: Optional[str]) -> Optional[str]:
    """(레거시) WS 토큰 검증(Mock). 통과 시 사용자 id, 실패 시 None."""
    return MOCK_USER_ID if authorization else None
