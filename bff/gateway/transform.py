"""응답 정형화 / 폴백 정규화(api-contract §4, R13).

BE/업스트림 실패를 **클라이언트 계약(폴백 응답)**으로 정규화한다. 대화·화면을 중단시키지 않는다.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import httpx
from fastapi.responses import JSONResponse

_FALLBACK_MSG = "일시적인 문제가 발생했어요. 잠시 후 다시 시도해 주세요."


def fallback_body(message: str = _FALLBACK_MSG, code: str = "upstream_unavailable") -> dict:
    return {"code": code, "message": message,
            "fallback": {"kind": "text", "data": {"message": message}}}


async def relay(call: Callable[[], Awaitable[httpx.Response]]) -> JSONResponse:
    """BE 호출을 실행해 상태코드·본문을 그대로 중계. 업스트림 장애는 503 폴백으로 정규화."""
    try:
        r = await call()
    except httpx.HTTPError:
        return JSONResponse(status_code=503, content=fallback_body())
    try:
        content = r.json()
    except ValueError:
        return JSONResponse(status_code=502, content=fallback_body("업스트림 응답을 해석할 수 없습니다."))
    return JSONResponse(status_code=r.status_code, content=content)


def interaction_to_text(msg: dict) -> str:
    """인터랙션 회신(choices·confirmation·booking)을 다음 턴 입력 텍스트로 변환(MVP)."""
    kind = msg.get("kind")
    payload = msg.get("payload") or {}
    if kind == "confirmation":
        return "주문을 확정할게요." if payload.get("confirmed") else "주문을 취소할게요."
    if kind == "choices":
        return str(payload.get("label") or payload.get("value") or "선택했어요.")
    if kind == "booking":
        return f"{payload.get('slot_id', '슬롯')} 시간으로 방문 예약할게요."
    return msg.get("text") or "계속할게요."
