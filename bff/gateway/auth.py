"""인증/세션 게이트(api-contract §3) — MVP는 Mock 토큰 검증.

토큰은 도메인 모델에 저장하지 않는다(architecture NFR). 검증 통과 시 고정 사용자 컨텍스트를 반환.
실 전환: 삼성 계정 SSO·세션 TTL·조용한 재인증.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

MOCK_USER_ID = "usr_01"


def require_auth(authorization: Optional[str] = Header(default=None)) -> str:
    """Authorization 헤더가 있으면 통과(Mock). 없으면 401."""
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    return MOCK_USER_ID


def ws_user(authorization: Optional[str]) -> Optional[str]:
    """WS 연결의 토큰 검증(Mock). 통과 시 사용자, 실패 시 None."""
    return MOCK_USER_ID if authorization else None
