"""개선 제안 엔드포인트(신규 라우터) — `/internal/improve/*`(ADR-0067).

운영 **내부 전용** 백오피스(요구사항 5-2) — 사용자 대면 계약 무변경. `wiring.register_router`로
등록한다(앱 팩토리 미편집, ADR-0056). 토글 `SELF_IMPROVE` off면 모든 엔드포인트가 inert(404) —
수집·제안·리뷰가 발동하지 않는다(회귀 불변, 요구사항 5-1).

**적용(apply)은 사람의 명시적 호출**이며, 코드/설정 변경(PR)을 반영했다는 수동 표기다.
시스템이 자동으로 적용하는 경로는 없다(ADR-0067 불변 원칙).
"""
from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..platform import wiring
from ..privacy.audit import AuditLog
from .bridge import ExperimentBridge
from .proposals import ProposalEngine
from .review import ReviewQueue, TransitionError
from .signals import COLLECTOR, self_improve_enabled

router = APIRouter(prefix="/internal/improve", tags=["improve"])

# 모듈 단일 상태(프로세스 수명). 신호 sink는 컴패니언(만족도)과 공유(COLLECTOR).
_audit = AuditLog()
_engine = ProposalEngine()
_queue = ReviewQueue(audit=_audit)
_bridge = ExperimentBridge(_queue)


def _gate() -> JSONResponse | None:
    """토글 off면 404(엔드포인트 inert). 운영자 신원은 헤더로(내부망 전제)."""
    if not self_improve_enabled():
        return JSONResponse(status_code=404, content={
            "code": "not_found", "message": "self-improve disabled"})
    return None


def _actor(x_actor: str | None) -> str:
    return x_actor or "operator"


class DecisionRequest(BaseModel):
    note: str | None = None


class ResultRequest(BaseModel):
    result: dict


@router.get("/signals")
def list_signals(kind: str | None = None):
    """수집 신호 조회(가시성). 토글 off면 404."""
    if (g := _gate()) is not None:
        return g
    return {"signals": [
        {"kind": s.kind, "ref": s.ref, "value": s.value, "at": s.at.isoformat()}
        for s in COLLECTOR.window(kind)
    ]}


@router.post("/analyze")
def analyze():
    """수집 신호 → 제안 생성 → 리뷰 큐 제출(기각 지문 중복 억제). 생성·제출분 반환."""
    if (g := _gate()) is not None:
        return g
    proposals = _engine.analyze(COLLECTOR.window())
    submitted = _queue.submit_all(proposals)
    return {"generated": len(proposals), "submitted": [p.to_dict() for p in submitted]}


@router.get("/proposals")
def list_proposals(status: str | None = None):
    if (g := _gate()) is not None:
        return g
    return {"proposals": [p.to_dict() for p in _queue.list(status)]}


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str):
    if (g := _gate()) is not None:
        return g
    p = _queue.get(proposal_id)
    if p is None:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "제안 없음"})
    return p.to_dict()


def _act(proposal_id: str, fn, **kw):
    """전이 액션 공통 처리 — 없음 404·잘못된 전이 409."""
    try:
        return fn(proposal_id, **kw).to_dict()
    except KeyError:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "제안 없음"})
    except TransitionError as err:
        return JSONResponse(status_code=409, content={"code": "InvalidTransition", "message": str(err)})


@router.post("/proposals/{proposal_id}/review")
def review_proposal(proposal_id: str, x_actor: str | None = Header(default=None)):
    if (g := _gate()) is not None:
        return g
    return _act(proposal_id, _queue.review, actor=_actor(x_actor))


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, req: DecisionRequest | None = None,
                     x_actor: str | None = Header(default=None)):
    if (g := _gate()) is not None:
        return g
    return _act(proposal_id, _queue.approve, actor=_actor(x_actor),
               note=(req.note if req else None))


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, req: DecisionRequest | None = None,
                    x_actor: str | None = Header(default=None)):
    if (g := _gate()) is not None:
        return g
    return _act(proposal_id, _queue.reject, actor=_actor(x_actor),
               note=(req.note if req else None))


@router.post("/proposals/{proposal_id}/validate")
def validate_proposal(proposal_id: str, x_actor: str | None = Header(default=None)):
    """승인 제안 → S8 실험 생성(검증중). 채택·적용은 사람(ADR-0064 연계)."""
    if (g := _gate()) is not None:
        return g
    try:
        exp = _bridge.to_experiment(proposal_id, actor=_actor(x_actor))
    except KeyError:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "제안 없음"})
    except ValueError as err:
        return JSONResponse(status_code=409, content={"code": "InvalidState", "message": str(err)})
    return {"experiment_key": exp.key, "proposal": _queue.get(proposal_id).to_dict()}


@router.post("/proposals/{proposal_id}/experiment-result")
def attach_experiment_result(proposal_id: str, req: ResultRequest):
    """S8 실험 결과 첨부 — 사람이 보고 채택·적용을 판단."""
    if (g := _gate()) is not None:
        return g
    try:
        return _bridge.attach_result(proposal_id, req.result).to_dict()
    except KeyError:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "제안 없음"})


@router.post("/proposals/{proposal_id}/apply")
def apply_proposal(proposal_id: str, req: DecisionRequest | None = None,
                   x_actor: str | None = Header(default=None)):
    """**사람의 적용 표기** — 코드/설정 변경(PR)을 반영했음을 수동 기록(자동 경로 없음)."""
    if (g := _gate()) is not None:
        return g
    return _act(proposal_id, _queue.mark_applied, actor=_actor(x_actor),
               note=(req.note if req else None))


wiring.register_router(router)
