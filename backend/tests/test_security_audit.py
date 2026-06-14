"""보안 감사 헬퍼(S7, ADR-0063, 요구사항 4) — S5 AuditLog 재사용·시그니처 불변."""
from app.privacy.audit import AuditLog
from app.security.audit import (
    AUTH_FAILURE,
    COMMIT_GATE,
    RATELIMIT_BLOCK,
    security_audit,
)


def test_security_audit_records_to_s5_auditlog():
    log = AuditLog()
    security_audit(log, RATELIMIT_BLOCK, subject="user:u1", detail={"path": "/orders"})
    events = log.list()
    assert len(events) == 1
    assert events[0].action == "security.ratelimit_block"
    assert events[0].subject == "user:u1"


def test_security_audit_normalizes_namespace():
    log = AuditLog()
    security_audit(log, "auth_failure", subject="ip:1.2.3.4")
    assert log.list()[0].action == "security.auth_failure"
    # 이미 security.* 이면 그대로.
    security_audit(log, AUTH_FAILURE, subject="ip:1.2.3.4")
    assert log.list()[1].action == "security.auth_failure"


def test_action_constants():
    assert RATELIMIT_BLOCK == "security.ratelimit_block"
    assert AUTH_FAILURE == "security.auth_failure"
    assert COMMIT_GATE == "security.commit_gate"


def test_security_audit_none_log_is_noop():
    # log가 None이면 예외 없이 무동작(배선 안 된 경로 안전).
    security_audit(None, RATELIMIT_BLOCK, subject="x")


def test_reuses_existing_auditlog_signature():
    """S5 AuditLog의 기존 record/list 시그니처를 그대로 사용(중복 구현 아님)."""
    log = AuditLog()
    # S5가 기록한 일반 이벤트와 보안 이벤트가 같은 sink에 공존.
    log.record("consent.grant", subject="u1", detail="analytics")
    security_audit(log, COMMIT_GATE, subject="u1", detail={"status": 401})
    actions = [e.action for e in log.list()]
    assert actions == ["consent.grant", "security.commit_gate"]
