"""개인정보·DSR 엔드포인트(신규 라우터) — `/internal/privacy/*`(ADR-0061).

`wiring.register_router`로 등록한다(앱 팩토리 `api/internal.py` 미편집, ADR-0056).
공유 상태(`_container`·`_users`)는 `api.internal`에서 **lazy import**해 동일 상태를 쓴다
(별도 컨테이너를 만들면 상태가 갈라져 접근/삭제가 무의미해짐).

신원은 기존 패턴과 동일하게 헤더(X-User-Id/X-Guest-Token) → Principal → user_id로 해석한다.
"""
from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..platform import wiring
from .audit import AuditLog
from .consent import ConsentStore
from .dsr import DSRService
from .retention import RetentionPolicy

router = APIRouter(prefix="/internal/privacy", tags=["privacy"])

# 공유 sink/서비스(모듈 1회 구성). 컨테이너/디렉터리는 첫 요청 시 lazy 바인딩.
_audit = AuditLog()
_consent = ConsentStore()       # directory는 lazy 바인딩(_bind에서 주입)
_dsr: DSRService | None = None
_retention = RetentionPolicy(audit=_audit)


def _bind():
    """api.internal의 공유 _container·_users에 lazy 바인딩(상태 일관)."""
    global _dsr
    from ..api import internal as _internal
    if _consent._directory is None:
        _consent._directory = _internal._users
    if _dsr is None:
        _dsr = DSRService(_internal._container, _internal._users)
    return _internal._container, _internal._users


def _user_id(x_user_id: str | None, x_guest_token: str | None) -> str:
    """헤더 신원 → user_id(Principal 해석, 기존 패턴 재사용)."""
    from ..principal import resolve_principal
    return resolve_principal(x_user_id, x_guest_token).id


def _profile(user_id: str):
    _, users = _bind()
    from ..principal import Principal
    return users.get(Principal("user", user_id))


class ScopeRequest(BaseModel):
    scope: str


class RectifyRequest(BaseModel):
    fields: dict


# ── 동의(consent) — scope별 부여/철회/조회(요구사항 1) ──────────────────────
@router.get("/consent")
def consent_status(x_user_id: str | None = Header(None),
                   x_guest_token: str | None = Header(None)):
    _bind()
    user = _profile(_user_id(x_user_id, x_guest_token))
    return {"scopes": ConsentStore.status(user)}


@router.post("/consent/grant")
def consent_grant(req: ScopeRequest, x_user_id: str | None = Header(None),
                  x_guest_token: str | None = Header(None)):
    _bind()
    uid = _user_id(x_user_id, x_guest_token)
    user = _profile(uid)
    try:
        consent = _consent.grant(user, req.scope)
    except ValueError as err:
        return JSONResponse(status_code=400, content={"code": "UnknownScope", "message": str(err)})
    _audit.record("consent.grant", subject=uid, detail=req.scope)
    return consent.model_dump(mode="json")


@router.post("/consent/revoke")
def consent_revoke(req: ScopeRequest, x_user_id: str | None = Header(None),
                   x_guest_token: str | None = Header(None)):
    _bind()
    uid = _user_id(x_user_id, x_guest_token)
    user = _profile(uid)
    try:
        consent = _consent.revoke(user, req.scope)
    except ValueError as err:
        return JSONResponse(status_code=400, content={"code": "UnknownScope", "message": str(err)})
    _audit.record("consent.revoke", subject=uid, detail=req.scope)
    return consent.model_dump(mode="json")


# ── DSR — 접근/내보내기·삭제·정정(요구사항 2·3·4) ──────────────────────────
@router.get("/dsr/export")
def dsr_export(x_user_id: str | None = Header(None),
               x_guest_token: str | None = Header(None)):
    _bind()
    uid = _user_id(x_user_id, x_guest_token)
    assert _dsr is not None
    data = _dsr.export(uid)
    _audit.record("dsr.export", subject=uid)
    return data


@router.post("/dsr/delete")
def dsr_delete(x_user_id: str | None = Header(None),
               x_guest_token: str | None = Header(None)):
    _bind()
    uid = _user_id(x_user_id, x_guest_token)
    assert _dsr is not None
    summary = _dsr.delete(uid)
    _audit.record("dsr.delete", subject=uid, detail=summary)
    return {"deleted": summary}


@router.post("/dsr/rectify")
def dsr_rectify(req: RectifyRequest, x_user_id: str | None = Header(None),
                x_guest_token: str | None = Header(None)):
    _bind()
    uid = _user_id(x_user_id, x_guest_token)
    assert _dsr is not None
    try:
        user = _dsr.rectify(uid, req.fields)
    except ValueError as err:
        return JSONResponse(status_code=400, content={"code": "NotRectifiable", "message": str(err)})
    _audit.record("dsr.rectify", subject=uid, detail=list(req.fields))
    return user.model_dump(mode="json")


# ── 보존(retention) — 정책·Mock 스윕(요구사항 5) ───────────────────────────
@router.get("/retention/policy")
def retention_policy():
    return {"retention_days": RetentionPolicy.policy()}


@router.post("/retention/sweep")
def retention_sweep():
    return {"expired_candidates": _retention.sweep()}


# ── 감사(audit) 로그 조회(요구사항 6) ──────────────────────────────────────
@router.get("/audit")
def audit_log():
    return {"events": [
        {"action": e.action, "subject": e.subject, "at": e.at.isoformat(), "detail": e.detail}
        for e in _audit.list()
    ]}


# 모듈 로드 = 라우터 등록(부수효과). registry가 본 모듈을 import하면 등록된다(ADR-0056).
wiring.register_router(router)
