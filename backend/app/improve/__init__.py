"""개선 제안 엔진 — 자기개선(propose-only, 휴먼 인 더 루프, ADR-0067).

신호 수집 → 제안 생성 → 휴먼 리뷰 큐 → S8 실험 검증 → 사람 적용. **자동 적용 경로 없음**:
이 패키지 어디에도 프롬프트·규칙·템플릿·게이트를 직접 수정하는 함수가 존재하지 않는다.
토글 `SELF_IMPROVE` 기본 off = 수집·제안 미발동(회귀 불변).
"""
from .bridge import ExperimentBridge
from .proposals import Proposal, ProposalEngine
from .review import ReviewQueue
from .signals import COLLECTOR, Signal, SignalCollector, self_improve_enabled

__all__ = [
    "Signal", "SignalCollector", "COLLECTOR", "self_improve_enabled",
    "Proposal", "ProposalEngine", "ReviewQueue", "ExperimentBridge",
]
