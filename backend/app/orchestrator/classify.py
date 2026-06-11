"""의도 분류기 — 주입 가능한 추상(IntentClassifier).

- RuleBasedClassifier: 키워드 규칙(네트워크 불필요) — 테스트·오프라인 기본값.
- OpenAIClassifier: 구조화 출력 LLM(legacy.classify) — 실 경로.
오케스트레이터는 Protocol에만 의존하므로 둘을 교체할 수 있다(architecture.md §5).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain import Intent, IntentResult

# 의도별 키워드(데모용 규칙)
_ORDER = ("주문", "주문해", "재주문", "사줘", "사고", "구매", "장바구니")
_RECOMMEND = ("추천", "뭐가 좋", "어떤 게 좋", "바꿀", "신제품")
_TROUBLE = ("안 빠", "안빠", "안 돼", "안돼", "고장", "오류", "에러", "문제", "해결", "수리", "왜")
_STATUS = ("상태", "어때", "괜찮", "정상", "확인해")
# 복합 연결 표지
_CONJ = ("그리고", "또", "랑 ", "하고", "和", ", ", "， ")


def _has(text: str, kws) -> bool:
    return any(k in text for k in kws)


@runtime_checkable
class IntentClassifier(Protocol):
    def classify(self, message: str) -> IntentResult: ...


class RuleBasedClassifier:
    """키워드 규칙 분류(네트워크 불필요). 순서를 보존해 우선순위 판단에 넘긴다."""

    def classify(self, message: str) -> IntentResult:
        t = message or ""
        intents: list[Intent] = []
        if _has(t, _TROUBLE):
            intents.append("troubleshoot")
        if _has(t, _RECOMMEND):
            intents.append("recommend")
        if _has(t, _ORDER):
            intents.append("order")
        if _has(t, _STATUS) and "troubleshoot" not in intents:
            intents.append("device_status")
        if not intents:
            intents.append("general")
        is_compound = len(intents) > 1 or _has(t, _CONJ) and len(intents) >= 1
        # 중복 제거(순서 보존)
        seen, uniq = set(), []
        for i in intents:
            if i not in seen:
                seen.add(i)
                uniq.append(i)
        return IntentResult(intents=uniq, is_compound=bool(is_compound) and len(uniq) > 1)


class OpenAIClassifier:
    """LLM 구조화 출력 분류(실 경로). 네트워크 필요."""

    def classify(self, message: str) -> IntentResult:
        from .legacy import classify as _llm_classify  # 지연 import(키 없이도 모듈 로드)
        return IntentResult.model_validate(_llm_classify(message))
