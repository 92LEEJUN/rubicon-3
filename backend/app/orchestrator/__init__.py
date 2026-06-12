"""오케스트레이터 패키지.

- `Orchestrator`(core) — 내부 API가 쓰는 결정적 섹션 생성 경로(테스트 가능).
- `run`(legacy) — CLI용 LLM tool-loop 데모(OpenAI 필요).
"""
from .capability import CapabilityOrchestrator  # noqa: F401
from .classify import OpenAIClassifier, RuleBasedClassifier  # noqa: F401
from .core import Orchestrator  # noqa: F401
from .legacy import run  # noqa: F401
