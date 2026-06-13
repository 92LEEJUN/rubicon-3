"""BE 도메인 내부 API 클라이언트(api-contract §2.4) — 비동기(httpx.AsyncClient).

기본은 HTTP(BE_BASE_URL). 테스트는 httpx ASGITransport로 BE 앱을 인프로세스 연결해
**실 계약(HTTP 경계)**을 그대로 검증한다(api-contract §5). ASGITransport는 async 전용이라
클라이언트도 async로 둔다(WS 중계에서도 이벤트 루프 비차단).

신원 포워딩(멀티테넌트): 모든 호출은 선택적 `headers`(X-User-Id | X-Guest-Token)를 받아
BE로 전달한다. BE는 MULTITENANT off면 신원을 무시하므로(기본 사용자 폴백) headers 유무와
무관하게 동작한다(공유 계약).
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
    async def list_devices(self, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get("/internal/devices", headers=headers)

    async def get_device(self, device_id: str, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get(f"/internal/devices/{device_id}", headers=headers)

    async def home(self, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get("/internal/home", headers=headers)

    async def recommend(self, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get("/internal/catalog/recommend", headers=headers)

    async def place_order(self, payload: dict, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.post("/internal/orders", json=payload, headers=headers)

    async def list_orders(self, user_id: Optional[str] = None,
                          headers: Optional[dict] = None) -> httpx.Response:
        params = {"user_id": user_id} if user_id else None
        return await self._client.get("/internal/orders", params=params, headers=headers)

    async def get_order(self, order_id: str, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get(f"/internal/orders/{order_id}", headers=headers)

    async def advance_pickup(self, order_id: str, payload: dict,
                             headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.post(f"/internal/orders/{order_id}/pickup",
                                       json=payload, headers=headers)

    # ── O2O 거점·재고·견적(§2.2) ────────────────────────────────────────────
    async def list_stores(self, params: Optional[dict] = None,
                          headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get("/internal/stores", params=params, headers=headers)

    async def check_stock(self, store_id: str, part_id: str,
                          headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get(f"/internal/stores/{store_id}/stock/{part_id}",
                                      headers=headers)

    async def get_quote(self, quote_ref: str, user_id: Optional[str] = None,
                        headers: Optional[dict] = None) -> httpx.Response:
        params = {"user_id": user_id} if user_id else None
        return await self._client.get(f"/internal/quotes/{quote_ref}",
                                      params=params, headers=headers)

    async def convert_quote(self, quote_ref: str, payload: dict,
                            headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.post(f"/internal/quotes/{quote_ref}/convert",
                                       json=payload, headers=headers)

    async def list_bookings(self, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get("/internal/bookings", headers=headers)

    async def booking_slots(self, visit_type: str = "REPAIR",
                            headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get("/internal/bookings/slots",
                                      params={"visit_type": visit_type}, headers=headers)

    async def create_booking(self, payload: dict, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.post("/internal/bookings", json=payload, headers=headers)

    async def surface(self, payload: dict, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.post("/internal/surface", json=payload, headers=headers)

    async def resume(self, fresh: bool = False, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get("/internal/resume",
                                      params={"fresh": str(fresh).lower()}, headers=headers)

    async def reengagement(self, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get("/internal/reengagement", headers=headers)

    async def recommendations(self, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.get("/internal/recommendations", headers=headers)

    async def reengagement_deliver(self, headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.post("/internal/reengagement/deliver", headers=headers)

    async def resolve_open_loop(self, ref: str, action: str = "resolve",
                                headers: Optional[dict] = None) -> httpx.Response:
        return await self._client.post(f"/internal/open-loops/{ref}/{action}", headers=headers)

    # ── 대화 스트림(NDJSON) ─────────────────────────────────────────────────
    async def turn_stream(self, payload: dict, headers: Optional[dict] = None):
        """청크를 **도착 즉시 yield**(증분 포워딩, operations §9). 버퍼링하지 않는다.

        신원은 payload(user_id·guest_token)로도, 헤더로도 전달한다 — BE HTTP turn은 body를
        읽고, 헤더는 무해(MULTITENANT off면 양쪽 다 무시).
        """
        async with self._client.stream("POST", "/internal/turn",
                                        json=payload, headers=headers) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if line.strip():
                    yield json.loads(line)

    async def turn_chunks(self, payload: dict, headers: Optional[dict] = None) -> list[dict]:
        """전체 청크 수집(비스트리밍 호출용). 스트림 위에 구현."""
        return [chunk async for chunk in self.turn_stream(payload, headers=headers)]
