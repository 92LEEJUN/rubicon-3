"""BFF 분석 싱크(gap: FE emit만 있고 수신 없음) — 인프로세스 수집기.

docs/analytics.md 택소노미(§4)의 이벤트를 FE에서 POST로 받아 **느슨히 검증**하고
경계 있는 리스트에 적재 + 구조화 로그 한 줄을 남긴다. stdlib only, 새 의존성 없음.

비범위(후속, analytics.md §7·§9): 웨어하우스/ETL·대시보드·BE-side emit·샘플링 적용.
이건 "싱크 배선"이지 풀 파이프라인이 아니다. 검증용 read-back(GET)만 더한다.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Deque, Optional

# observability.py가 모듈 로드 시 1회 설정한 동일 로거(JSON 한 줄)를 재사용.
_log = logging.getLogger("rubicon.bff")

# docs/analytics.md §4 카탈로그의 알려진 이벤트명(느슨한 검증 — 미상도 거부하지 않고 태깅만).
KNOWN_EVENTS = frozenset({
    "screen_viewed", "screen_exited", "chat_opened", "card_tapped",
    "bridge_viewed", "bridge_cta_clicked", "bridge_escalated", "bridge_dismissed",
    "message_sent", "template_shown", "cta_shown", "cta_clicked",
    "flow_started", "flow_advanced", "flow_completed", "flow_abandoned",
    "cart_item_added", "checkout_shown", "order_confirmed", "order_cancelled",
    "notification_delivered", "notification_opened", "notification_dismissed",
    "handoff_started", "resolution_confirmed", "fallback_shown", "error_shown",
})

# 경계 있는 버퍼 — 인프로세스 read-back(검증·로컬 가시성)용. 영속 아님.
_MAX_EVENTS = 1000


class AnalyticsSink:
    """경계 있는 인메모리 이벤트 싱크 + 구조화 로그. 비차단·관용적."""

    def __init__(self, maxlen: int = _MAX_EVENTS) -> None:
        self._events: Deque[dict[str, Any]] = deque(maxlen=maxlen)
        self.received = 0
        self.unknown = 0

    def record(self, name: str, props: Optional[dict] = None,
               ts: Optional[float] = None, principal: Optional[str] = None) -> dict[str, Any]:
        """이벤트 1건 적재 + 로그. 검증은 느슨함(미상 이벤트명도 받되 unknown 카운트)."""
        known = name in KNOWN_EVENTS
        if not known:
            self.unknown += 1
        event = {
            "name": str(name),
            "props": props if isinstance(props, dict) else {},
            "ts": ts if isinstance(ts, (int, float)) else time.time(),
            "principal": principal,
            "known": known,
        }
        self._events.append(event)
        self.received += 1
        # 구조화 로그 한 줄(ctx_* 는 _JsonLineFormatter가 top-level 키로 승격).
        _log.info("analytics_event", extra={
            "ctx_event": event["name"],
            "ctx_principal": principal,
            "ctx_known": known,
        })
        return event

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """최근 이벤트 read-back(검증용). 가장 최근이 마지막."""
        items = list(self._events)
        return items[-limit:] if limit and limit > 0 else items

    def snapshot(self) -> dict[str, Any]:
        return {"received": self.received, "unknown": self.unknown, "buffered": len(self._events)}
