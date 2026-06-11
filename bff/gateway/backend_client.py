"""BE 도메인 내부 API 클라이언트(api-contract §2.4) — 비동기(httpx.AsyncClient).

기본은 HTTP(BE_BASE_URL). 테스트는 httpx ASGITransport로 BE 앱을 인프로세스 연결해
**실 계약(HTTP 경계)**을 그대로 검증한다(api-contract §5). ASGITransport는 async 전용이라
클라이언트도 async로 둔다(WS 중계에서도 이벤트 루프 비차단).
"""
from __future__ import annotations

import json
from typing import Optional

import httpx

from .config import BE_BASE_URL, UPSTREAM_TIMEOUT


class BackendClient:
    def __init__(self, base_url: Optional[str] = None,
                 transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._client = httpx.AsyncClient(base_url=base_url or BE_BASE_URL,
                                         transport=transport, timeout=UPSTREAM_TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── 결정적 조회/커밋 (응답 그대로 중계 — 상태코드 보존) ──────────────────
    async def list_devices(self) -> httpx.Response:
        return await self._client.get("/internal/devices")

    async def get_device(self, device_id: str) -> httpx.Response:
        return await self._client.get(f"/internal/devices/{device_id}")

    async def home(self) -> httpx.Response:
        return await self._client.get("/internal/home")

    async def recommend(self) -> httpx.Response:
        return await self._client.get("/internal/catalog/recommend")

    async def place_order(self, payload: dict) -> httpx.Response:
        return await self._client.post("/internal/orders", json=payload)

    async def booking_slots(self, visit_type: str = "REPAIR") -> httpx.Response:
        return await self._client.get("/internal/bookings/slots", params={"visit_type": visit_type})

    async def create_booking(self, payload: dict) -> httpx.Response:
        return await self._client.post("/internal/bookings", json=payload)

    async def surface(self, payload: dict) -> httpx.Response:
        return await self._client.post("/internal/surface", json=payload)

    # ── 대화 스트림(NDJSON) — 청크 리스트로 수집 ────────────────────────────
    async def turn_chunks(self, payload: dict) -> list[dict]:
        out: list[dict] = []
        async with self._client.stream("POST", "/internal/turn", json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if line.strip():
                    out.append(json.loads(line))
        return out
