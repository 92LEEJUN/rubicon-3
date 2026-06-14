"""휴먼 리뷰 큐(요구사항 3, ADR-0067) — 상태기계 + 감사. **적용은 사람만.**

상태 전이: `제안됨 → 검토중 → (승인|기각) → 검증중 → 적용`. 시스템이 자동으로 `applied`로
보내는 경로는 **없다** — `mark_applied`는 사람(actor)이 명시적으로 호출해야 하며, 큐 내부의 어떤
메서드도 이를 자동 호출하지 않는다. 결정(승인·기각·적용)은 감사 로그(ADR-0061)에 남는다.
기각된 지문(kind,target)은 재제출을 억제한다(요구사항 3.3).
"""
from __future__ import annotations

from typing import Optional

from .proposals import Proposal

# 허용 전이(이 외 전이는 거부). rejected/applied는 종착.
_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"in_review"},
    "in_review": {"approved", "rejected"},
    "approved": {"validating"},
    "validating": {"applied", "rejected"},   # 검증 실패 시 기각 가능
    "rejected": set(),
    "applied": set(),
}


class TransitionError(Exception):
    """허용되지 않은 상태 전이."""


class ReviewQueue:
    """제안 백로그 — 상태기계·감사·기각 중복 억제. 적용은 사람 호출만."""

    def __init__(self, audit=None) -> None:
        self._items: dict[str, Proposal] = {}
        self._rejected: set[tuple[str, str]] = set()  # 기각 지문(재제출 억제)
        self._audit = audit

    # ── 제출 ────────────────────────────────────────────────────────────────
    def submit(self, proposal: Proposal) -> Optional[Proposal]:
        """제안 등록. 기각된 지문이면 None(중복 억제, 요구사항 3.3)."""
        if proposal.fingerprint() in self._rejected:
            return None
        self._items[proposal.id] = proposal
        return proposal

    def submit_all(self, proposals: list[Proposal]) -> list[Proposal]:
        return [p for p in (self.submit(p) for p in proposals) if p is not None]

    # ── 조회 ────────────────────────────────────────────────────────────────
    def get(self, proposal_id: str) -> Optional[Proposal]:
        return self._items.get(proposal_id)

    def list(self, status: Optional[str] = None) -> list[Proposal]:
        items = list(self._items.values())
        if status:
            items = [p for p in items if p.status == status]
        return items

    # ── 전이(내부) ─────────────────────────────────────────────────────────
    def _transition(self, proposal_id: str, to: str, *, actor: str,
                    note: Optional[str] = None, audit_action: Optional[str] = None) -> Proposal:
        p = self._items.get(proposal_id)
        if p is None:
            raise KeyError(proposal_id)
        if to not in _TRANSITIONS.get(p.status, set()):
            raise TransitionError(f"{p.status} → {to} 불가")
        p.status = to
        if to == "rejected":
            self._rejected.add(p.fingerprint())
        if audit_action and self._audit is not None:
            self._audit.record(audit_action, actor,
                               {"proposal": p.id, "target": p.target, "note": note})
        return p

    # ── 휴먼 액션 ──────────────────────────────────────────────────────────
    def review(self, proposal_id: str, *, actor: str) -> Proposal:
        return self._transition(proposal_id, "in_review", actor=actor)

    def approve(self, proposal_id: str, *, actor: str, note: Optional[str] = None) -> Proposal:
        return self._transition(proposal_id, "approved", actor=actor, note=note,
                                audit_action="improve.approve")

    def reject(self, proposal_id: str, *, actor: str, note: Optional[str] = None) -> Proposal:
        return self._transition(proposal_id, "rejected", actor=actor, note=note,
                                audit_action="improve.reject")

    def mark_validating(self, proposal_id: str, *, actor: str = "system") -> Proposal:
        """검증 단계로 — ExperimentBridge가 S8 실험 생성 후 호출."""
        return self._transition(proposal_id, "validating", actor=actor)

    def mark_applied(self, proposal_id: str, *, actor: str, note: Optional[str] = None) -> Proposal:
        """**사람만** 호출 — 코드/설정 변경(PR)으로 반영했음을 수동 표기. 자동 경로 없음."""
        return self._transition(proposal_id, "applied", actor=actor, note=note,
                                audit_action="improve.apply")
