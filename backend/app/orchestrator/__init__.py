"""오케스트레이터 패키지.

- `CapabilityOrchestrator` — 결정적/LLM-플래너 단일 백본(ADR-0046·0048). 내부 API의
  결정적 경로(플래너 없음)와 LLM 라우팅 경로 모두 이것으로 수렴(옛 core 제거, §12.3).
- `run`(legacy) — CLI용 LLM tool-loop 데모(OpenAI 필요). LLM prose 경로는 §8~11까지 유지.
"""
from .capability import CapabilityOrchestrator  # noqa: F401
from .classify import OpenAIClassifier, RuleBasedClassifier  # noqa: F401
from .legacy import run  # noqa: F401
