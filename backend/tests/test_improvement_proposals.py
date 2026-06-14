"""개선 제안 엔진 테스트(ADR-0067) — propose-only·휴먼게이트·S8 검증·토글 회귀.

핵심 안전 단언: **수정 API 부재**(엔진/큐/브릿지 어디에도 프롬프트·규칙을 자동 적용하는 경로가
없음)와 **적용은 사람만**·**토글 off 회귀 불변**.
"""
from __future__ import annotations

import pytest

from app.improve.bridge import ExperimentBridge
from app.improve.proposals import ProposalEngine
from app.improve.review import ReviewQueue, TransitionError
from app.improve.signals import Signal, SignalCollector


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setenv("SELF_IMPROVE", "1")


def _signals(kind: str, ref: str, n: int, value: float = 1.0) -> list[Signal]:
    return [Signal(kind=kind, ref=ref, value=value) for _ in range(n)]


# ── 요구사항 1: 신호 수집·토글·동의 ─────────────────────────────────────────
def test_collect_gated_by_toggle(monkeypatch):
    c = SignalCollector()
    monkeypatch.setenv("SELF_IMPROVE", "0")
    assert c.collect(Signal(kind="resolution", ref="order")) is False
    assert c.window() == []                      # off면 적재 안 됨(회귀 불변)
    monkeypatch.setenv("SELF_IMPROVE", "1")
    assert c.collect(Signal(kind="resolution", ref="order")) is True
    assert len(c.window()) == 1


def test_collect_drops_non_consented():
    c = SignalCollector()
    assert c.collect(Signal(kind="satisfaction", ref="washer", consent_ok=False)) is False
    assert c.window("satisfaction") == []


# ── 요구사항 2: 제안 생성 + 수정 API 부재 ───────────────────────────────────
def test_engine_generates_structured_proposals():
    eng = ProposalEngine(min_samples=5, low_conf_threshold=0.3)
    proposals = eng.analyze(_signals("low_confidence_route", "troubleshoot", 6, value=0.8))
    assert len(proposals) == 1
    p = proposals[0]
    assert p.kind == "routing_fix" and p.target == "troubleshoot"
    assert p.evidence and p.change_candidate          # 증거·변경 후보 포함
    assert 0 <= p.impact_estimate <= 1
    assert p.status == "proposed"


def test_engine_respects_min_samples():
    eng = ProposalEngine(min_samples=5)
    # 표본 부족 → 제안 없음(잡음 방지)
    assert eng.analyze(_signals("low_confidence_route", "order", 3, value=0.9)) == []


def test_no_mutation_api_exists():
    """ADR-0067 불변 원칙 — 자동 적용/수정 경로가 코드에 존재하지 않음을 고정."""
    forbidden = ("apply", "mutate", "write", "patch", "update_prompt", "edit", "commit")
    for obj in (ProposalEngine(), ExperimentBridge(ReviewQueue())):
        for name in forbidden:
            assert not hasattr(obj, name), f"{type(obj).__name__}.{name} 가 있으면 안 됨(propose-only)"
    # 엔진의 공개 메서드는 analyze뿐(산출 전용)
    public = [m for m in dir(ProposalEngine()) if not m.startswith("_")]
    assert "analyze" in public


# ── 요구사항 3: 리뷰 큐 상태기계·적용은 사람·기각 중복 억제 ──────────────────
def test_review_lifecycle_and_human_apply():
    q = ReviewQueue()
    p = ProposalEngine().analyze(_signals("low_confidence_route", "order", 6, 0.9))[0]
    q.submit(p)
    q.review(p.id, actor="op")
    assert q.get(p.id).status == "in_review"
    q.approve(p.id, actor="op")
    assert q.get(p.id).status == "approved"
    q.mark_validating(p.id)
    # 적용은 사람(actor 명시) — 검증중에서만 가능
    applied = q.mark_applied(p.id, actor="alice", note="PR #123")
    assert applied.status == "applied"


def test_cannot_skip_states():
    q = ReviewQueue()
    p = ProposalEngine().analyze(_signals("low_confidence_route", "order", 6, 0.9))[0]
    q.submit(p)
    with pytest.raises(TransitionError):     # 제안됨 → 적용(검토·승인·검증 건너뜀) 불가
        q.mark_applied(p.id, actor="alice")


def test_rejected_fingerprint_suppresses_resubmit():
    q = ReviewQueue()
    eng = ProposalEngine()
    p1 = eng.analyze(_signals("low_confidence_route", "order", 6, 0.9))[0]
    q.submit(p1)
    q.review(p1.id, actor="op")
    q.reject(p1.id, actor="op", note="중복")
    # 같은 (kind,target) 제안 재제출 → 억제(None)
    p2 = ProposalEngine().analyze(_signals("low_confidence_route", "order", 6, 0.9))[0]
    assert q.submit(p2) is None


def test_apply_audited():
    from app.privacy.audit import AuditLog
    audit = AuditLog()
    q = ReviewQueue(audit=audit)
    p = ProposalEngine().analyze(_signals("low_confidence_route", "order", 6, 0.9))[0]
    q.submit(p)
    q.review(p.id, actor="op")
    q.approve(p.id, actor="op")
    q.mark_validating(p.id)
    q.mark_applied(p.id, actor="alice", note="PR")
    actions = [e.action for e in audit.list()]
    assert "improve.approve" in actions and "improve.apply" in actions


# ── 요구사항 4: S8 실험 검증 연계 ───────────────────────────────────────────
def test_bridge_creates_experiment_and_attaches_result():
    from app.experiments.registry import get
    q = ReviewQueue()
    bridge = ExperimentBridge(q)
    p = ProposalEngine().analyze(_signals("template_conversion", "bridge", 6, 0.1))[0]
    q.submit(p)
    q.review(p.id, actor="op")
    q.approve(p.id, actor="op")
    exp = bridge.to_experiment(p.id)
    assert get(exp.key) is not None                 # S8 레지스트리에 등록됨
    assert q.get(p.id).status == "validating"
    assert set(exp.variant_names()) == {"control", "treatment"}
    bridge.attach_result(p.id, {"winner": "treatment", "lift": 0.12})
    assert q.get(p.id).experiment_result["winner"] == "treatment"
    # 검증만으로 적용되지 않음 — 사람이 별도로 mark_applied 해야 함
    assert q.get(p.id).status == "validating"


def test_bridge_requires_approval():
    q = ReviewQueue()
    bridge = ExperimentBridge(q)
    p = ProposalEngine().analyze(_signals("template_conversion", "bridge", 6, 0.1))[0]
    q.submit(p)                                      # 승인 안 함
    with pytest.raises(ValueError):
        bridge.to_experiment(p.id)
