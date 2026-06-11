"""오케스트레이터 core — 의도 분류 → 우선순위 → 핸들러 → 섹션 묶음/스트림.

orchestration.md / architecture.md §8 의 reactive 경로. 분류기는 주입(테스트=규칙기반).
근거는 서비스에서만 — 환각 억제. 복합(R7)은 의도별 섹션을 우선순위로 묶고 handled/unhandled 구분.
"""
from __future__ import annotations

import uuid
from typing import Iterator, Optional

from ..container import Container, build_container
from ..domain import AssistantTurn, MessageSection
from . import handlers
from .classify import IntentClassifier, RuleBasedClassifier

# 우선순위(design §6.6) — 안전/CS 먼저, 주문은 뒤
_PRIORITY = {"device_status": 0, "troubleshoot": 1, "general": 2, "recommend": 3, "order": 4}


class Orchestrator:
    def __init__(self, container: Optional[Container] = None,
                 classifier: Optional[IntentClassifier] = None) -> None:
        self.c = container or build_container()
        self.classifier = classifier or RuleBasedClassifier()

    def _ordered_intents(self, message: str) -> list[str]:
        result = self.classifier.classify(message)
        return sorted(result.intents, key=lambda i: _PRIORITY.get(i, 9))

    def build_turn(self, message: str, screen_context: Optional[dict] = None) -> AssistantTurn:
        """전체 응답을 한 번에 구성(복합이면 섹션 N개).

        의도 간 맥락 전달: troubleshoot의 required_parts를, 명시 부품이 없는 order가 이어받는다
        (J1 "해결하고 부품도 주문" → 해결책의 배수필터를 주문 섹션으로).
        """
        sections: list[MessageSection] = []
        carried_parts: list[str] = []
        for intent in self._ordered_intents(message):
            if intent == "order":
                ids = handlers.resolve_part_ids(message) or carried_parts
                new = handlers.handle_order(self.c, self.c.user, message, part_ids=ids)
            else:
                new = handlers.DISPATCH.get(intent, handlers.handle_general)(
                    self.c, self.c.user, message)
                if intent == "troubleshoot":
                    for s in new:
                        carried_parts += s.template.data.get("required_parts", []) or []
            sections.extend(new)
        active_flow = "troubleshoot" if any(s.intent == "troubleshoot" for s in sections) else None
        return AssistantTurn(sections=sections, active_flow=active_flow,
                             message_id=f"msg_{uuid.uuid4().hex[:8]}")

    def stream_turn(self, message: str, screen_context: Optional[dict] = None) -> Iterator[dict]:
        """api-contract §2.1 봉투로 청크 스트림 — section* → flow → done(실패 시 error)."""
        try:
            turn = self.build_turn(message, screen_context)
        except Exception as exc:  # 전체 폴백(R13) — 대화 중단 금지
            yield {"type": "error", "code": "orchestrator_error",
                   "fallback": {"kind": "text",
                                "data": {"message": "일시적인 문제가 발생했어요. 잠시 후 다시 시도해 주세요."}},
                   "detail": str(exc)}
            return
        for section in turn.sections:
            yield {"type": "section", "section": section.model_dump(mode="json")}
        yield {"type": "flow", "active_flow": turn.active_flow}
        yield {"type": "done", "message_id": turn.message_id}
