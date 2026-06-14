"""실험 검증 연계(요구사항 4, ADR-0067 ↔ ADR-0064/S8).

승인된 제안을 S8 실험(control vs treatment)으로 만들어 **A/B 검증**한다. 검증은 자동(실험 등록),
**채택·적용은 사람**: 결과는 제안에 첨부되고, 사람이 보고 `mark_applied`(PR 반영)를 결정한다.
이 다리는 프롬프트·규칙을 바꾸지 않는다 — 실험을 등록하고 결과를 제안에 붙일 뿐이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..experiments.registry import Experiment, Variant, register
from .proposals import Proposal
from .review import ReviewQueue


@dataclass
class ExperimentBridge:
    """승인 제안 → S8 실험 생성 + 결과 첨부. 적용은 사람."""

    queue: ReviewQueue
    rollout: float = 0.5            # canary 기본(절반 노출)

    def to_experiment(self, proposal_id: str, *, actor: str = "system",
                      rollout: Optional[float] = None) -> Experiment:
        """승인된 제안을 control/treatment 실험으로 등록하고 검증중으로 전이."""
        p = self.queue.get(proposal_id)
        if p is None:
            raise KeyError(proposal_id)
        if p.status != "approved":
            raise ValueError(f"승인된 제안만 검증 가능(현재 {p.status})")
        key = f"improve_{p.id}"
        exp = register(Experiment(
            key=key,
            variants=(Variant("control", 1.0), Variant("treatment", 1.0)),
            control="control",
            rollout=self.rollout if rollout is None else rollout,
            holdout=0.0,
            salt=key,
        ))
        p.experiment_key = key
        self.queue.mark_validating(proposal_id, actor=actor)
        return exp

    def attach_result(self, proposal_id: str, result: dict) -> Proposal:
        """S8 실험 결과(지표·승자)를 제안에 첨부 — 사람이 최종 판단(채택·적용)한다."""
        p = self.queue.get(proposal_id)
        if p is None:
            raise KeyError(proposal_id)
        p.experiment_result = dict(result)
        return p
