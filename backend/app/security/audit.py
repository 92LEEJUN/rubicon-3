"""보안 감사 헬퍼 — S5 AuditLog 재사용·확장(S7, ADR-0063, 요구사항 4).

중복 구현 금지: S5 `backend/app/privacy/audit.py`의 `AuditLog`를 그대로 재사용하고, 보안 의미
이벤트(레이트리밋 차단·인증 실패·커밋 게이트)를 `security.*` 네임스페이스로 기록하는 **추가형 헬퍼**다.
기존 `AuditEvent`/`AuditLog` 시그니처는 변경하지 않는다(요구사항 4.4).

비차단: `AuditLog.record`가 sink 실패를 삼키므로(ADR-0061) 주 흐름을 막지 않는다(요구사항 4.3).
"""
from __future__ import annotations

from typing import Any, Optional

from app.privacy.audit import AuditLog  # S5 재사용(중복 구현 금지)

# 보안 의미 action 상수(`security.*` 네임스페이스, 요구사항 4.2).
RATELIMIT_BLOCK = "security.ratelimit_block"
AUTH_FAILURE = "security.auth_failure"
COMMIT_GATE = "security.commit_gate"


def _normalize(event: str) -> str:
    """action 명을 `security.*` 네임스페이스로 정규화한다."""
    return event if event.startswith("security.") else f"security.{event}"


def security_audit(
    log: Optional[AuditLog],
    event: str,
    subject: str,
    detail: Any = None,
) -> None:
    """보안 이벤트를 S5 AuditLog에 기록한다(요구사항 4.1).

    - `log`가 None이면 무동작(감사 sink가 배선되지 않은 경로에서도 안전).
    - `event`는 `security.*`로 정규화. detail에는 민감정보(토큰 원문 등)를 넣지 않는다.
    - 기록 실패는 `AuditLog.record`가 삼킨다(비차단, 요구사항 4.3).
    """
    if log is None:
        return
    log.record(_normalize(event), subject=subject, detail=detail)
