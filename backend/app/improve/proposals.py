"""제안 생성(요구사항 2, ADR-0067) — **propose-only**.

신호 집계에서 패턴(임계 초과)을 찾아 **구조화 제안**(증거·영향 추정·변경 후보)을 만든다.
결정론 규칙으로 단위 검증 가능(실 LLM 분석은 후속·선택).

> **불변 원칙(ADR-0067):** 이 엔진은 프롬프트·분류 규칙·템플릿·게이트를 **수정하지 않는다**.
> `analyze`만 존재하고, 적용/수정/쓰기 메서드는 **존재하지 않는다**(부재를 테스트로 고정).
> 산출물은 사람이 검토할 `Proposal`뿐이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .signals import Signal

# 제안 상태기계(리뷰 큐가 전이를 규율). 적용(applied)은 사람만.
ProposalStatus = (
    "proposed", "in_review", "approved", "rejected", "validating", "applied",
)


@dataclass
class Proposal:
    """개선 제안 — 증거·영향 추정·변경 후보(적용은 사람). status는 ReviewQueue가 전이."""

    id: str
    kind: str                       # "routing_fix" · "template_cta" · "clarify_reduction" · "satisfaction_dip"
    target: str                     # 대상 집계 차원(의도·template kind 등)
    evidence: list[str]
    impact_estimate: float          # [0,1] 영향 추정(정렬·우선순위용)
    change_candidate: str           # 사람이 읽을 변경 후보(적용 아님 — 제안 텍스트)
    status: str = "proposed"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    experiment_key: Optional[str] = None     # 검증 연계 시 S8 키(ExperimentBridge)
    experiment_result: Optional[dict] = None  # 검증 결과(사람이 최종 판단)

    def fingerprint(self) -> tuple[str, str]:
        """중복 억제용 지문 — (kind, target). 기각된 지문 재제출을 막는다(요구사항 3.3)."""
        return (self.kind, self.target)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "target": self.target,
            "evidence": list(self.evidence), "impact_estimate": self.impact_estimate,
            "change_candidate": self.change_candidate, "status": self.status,
            "created_at": self.created_at.isoformat(),
            "experiment_key": self.experiment_key, "experiment_result": self.experiment_result,
        }


def _rate(signals: list[Signal], kind: str) -> dict[str, tuple[float, int]]:
    """ref별 평균 value·건수 집계(예: 의도별 저신뢰 비율)."""
    acc: dict[str, list[float]] = {}
    for s in signals:
        if s.kind == kind:
            acc.setdefault(s.ref, []).append(s.value)
    return {ref: (sum(v) / len(v), len(v)) for ref, v in acc.items()}


@dataclass
class ProposalEngine:
    """신호 → 제안(결정론). **수정 API 없음** — analyze만."""

    min_samples: int = 5            # 잡음 방지 최소 표본
    low_conf_threshold: float = 0.3  # 저신뢰 라우팅 비율 임계
    clarify_threshold: int = 3      # clarify 반복 임계(건수)
    conversion_floor: float = 0.2   # 템플릿 전환 하한
    csat_floor: float = 3.5         # CSAT 평균 하한(5점)
    _seq: int = 0

    def _next_id(self) -> str:
        self._seq += 1
        return f"prop_{self._seq:04d}"

    def analyze(self, signals: list[Signal]) -> list[Proposal]:
        """신호 집계 → 임계 초과 패턴마다 구조화 제안. 부작용 없음(순수 산출)."""
        out: list[Proposal] = []

        # ① 저신뢰 라우팅 — 의도별 저신뢰 비율↑ → 분류/프롬프트 후보
        for ref, (avg, n) in _rate(signals, "low_confidence_route").items():
            if n >= self.min_samples and avg >= self.low_conf_threshold:
                out.append(Proposal(
                    id=self._next_id(), kind="routing_fix", target=ref,
                    evidence=[f"의도 '{ref}' 저신뢰 라우팅 비율 {avg:.0%} (n={n})"],
                    impact_estimate=round(min(avg, 1.0), 3),
                    change_candidate=f"의도 '{ref}' 분류 규칙/프롬프트 예시 보강 검토"))

        # ② clarify 반복 — 의도별 반복 빈발 → clarify 질문/슬롯 보강
        for ref, (_, n) in _rate(signals, "clarify_repeat").items():
            if n >= self.clarify_threshold:
                out.append(Proposal(
                    id=self._next_id(), kind="clarify_reduction", target=ref,
                    evidence=[f"의도 '{ref}' clarify 반복 {n}회"],
                    impact_estimate=round(min(n / 10, 1.0), 3),
                    change_candidate=f"의도 '{ref}' 슬롯/예시 보강해 clarify 횟수 절감 검토"))

        # ③ 템플릿 전환 저조 — kind별 전환율↓ → CTA 카피/배치 후보
        for ref, (avg, n) in _rate(signals, "template_conversion").items():
            if n >= self.min_samples and avg <= self.conversion_floor:
                out.append(Proposal(
                    id=self._next_id(), kind="template_cta", target=ref,
                    evidence=[f"템플릿 '{ref}' 전환율 {avg:.0%} (n={n})"],
                    impact_estimate=round(1.0 - avg, 3),
                    change_candidate=f"템플릿 '{ref}' CTA 카피/배치 A/B 후보"))

        # ④ 만족도 저하 — 주제별 CSAT 평균↓ → 응답/플로우 점검(ADR-0066 신호)
        for ref, (avg, n) in _rate(signals, "satisfaction").items():
            if n >= self.min_samples and avg <= self.csat_floor:
                out.append(Proposal(
                    id=self._next_id(), kind="satisfaction_dip", target=ref,
                    evidence=[f"'{ref}' CSAT 평균 {avg:.2f}/5 (n={n})"],
                    impact_estimate=round((5 - avg) / 5, 3),
                    change_candidate=f"'{ref}' 응답 품질/플로우 점검 — 핸드오프 임계 조정 검토"))

        out.sort(key=lambda p: p.impact_estimate, reverse=True)
        return out
