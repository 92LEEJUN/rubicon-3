"""감사(audit) 훅 — 보안 의미 이벤트 기록 인터페이스(ADR-0061).

GDPR 제30조(처리 활동 기록) 대응. 동의 변경·DSR(접근·삭제·정정)·보존 스윕 등 보안적으로
의미 있는 개인정보 이벤트를 기록한다. 현재 sink는 인메모리(인터페이스)이며, 실 전환 시
구조화 로그/감사 DB 어댑터로 교체한다(S1 관측성·S7 보안 심화와 연계).

비차단 원칙: sink 실패가 주 흐름을 막지 않는다(요구사항 6.3).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class AuditEvent:
    action: str                      # "consent.grant" · "dsr.delete" · "retention.sweep" ...
    subject: str                     # 주체(user_id 또는 "system")
    at: datetime
    detail: Optional[Any] = None     # 보조 정보(scope·요약 등; 민감정보는 넣지 않는다)


class AuditLog:
    """인메모리 감사 sink — record/list. 실 sink는 어댑터로 교체."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, action: str, subject: str, detail: Any = None) -> None:
        """이벤트 기록(요구사항 6.1). sink 실패는 삼킨다(비차단, 6.3)."""
        try:
            self._events.append(
                AuditEvent(action=action, subject=subject,
                           at=datetime.now(timezone.utc), detail=detail)
            )
        except Exception:
            pass

    def list(self) -> list[AuditEvent]:
        """기록된 이벤트(시간순; 추가 순서가 곧 시간순)(요구사항 6.2)."""
        return list(self._events)
