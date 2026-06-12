"""대화 컴팩션 — 롤링 요약 + 구조화 사실 추출 (ADR-0040, operations §4-1).

오래된 턴을 요약으로 접고, 손실 위험 큰 항목(주문ID·오류코드 등)은 facts로 별도 보존한다.
`Compactor`는 Port↔Mock 패턴(ADR-0020): 결정적 `RuleBasedCompactor`(테스트·MVP) ↔ `LLMCompactor`(실).

turn 형식: `{"role": "user"|"assistant", "text": str, "facts"?: dict}`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from .domain import ConversationMemory

DEFAULT_KEEP_RECENT = 6  # 최근 N 메시지는 verbatim 유지(압축 안 함)
_SUMMARY_SNIPPET = 60

_ORDER_RE = re.compile(r"\bord_[a-z0-9]+\b", re.IGNORECASE)
_ERRCODE_RE = re.compile(r"\b\d+[A-Z]\b")  # 4C·5C 등 가전 오류코드


def _merge_facts(facts: dict, turn: dict) -> None:
    """명시 사실(turn.facts) + 규칙 추출(주문ID·오류코드)을 facts에 누적(in-place)."""
    for k, v in (turn.get("facts") or {}).items():
        facts[k] = v
    text = turn.get("text") or ""
    for key, rx in (("orders", _ORDER_RE), ("error_codes", _ERRCODE_RE)):
        for m in rx.findall(text):
            bucket = facts.setdefault(key, [])
            if m not in bucket:
                bucket.append(m)


class Compactor(Protocol):
    def fold(self, memory: ConversationMemory, turns: list[dict]) -> ConversationMemory:
        """turns를 memory에 접어 갱신된 (summary, facts)를 반환. summarized_through는 서비스가 설정."""
        ...


class RuleBasedCompactor:
    """LLM 없는 결정적 컴팩션 — 사용자 발화 스니펫 요약 + 규칙 기반 사실 추출."""

    def fold(self, memory: ConversationMemory, turns: list[dict]) -> ConversationMemory:
        summary = memory.summary
        facts = {k: (list(v) if isinstance(v, list) else v) for k, v in memory.facts.items()}
        for t in turns:
            text = (t.get("text") or "").strip()
            if t.get("role") == "user" and text:
                snippet = text[:_SUMMARY_SNIPPET]
                summary = f"{summary} · {snippet}" if summary else snippet
            _merge_facts(facts, t)
        return ConversationMemory(summary=summary, facts=facts,
                                  summarized_through=memory.summarized_through)


class LLMCompactor:
    """실 경로 — LLM으로 롤링 요약을 갱신, 사실은 규칙 추출 재사용(손실 방지).

    facts 구조화 추출 스키마는 구현 단계에서 확정(요약은 LLM, 핵심 식별자는 규칙으로 이중 보존).
    """

    _SYSTEM = ("이전 대화 요약을 갱신한다. 핵심만 간결히. "
               "주문ID·기기모델·미해결 이슈는 빠뜨리지 마라.")

    def fold(self, memory: ConversationMemory, turns: list[dict]) -> ConversationMemory:
        from .llm import MODEL, chat_completion
        convo = "\n".join(f"{t.get('role')}: {t.get('text', '')}" for t in turns)
        resp = chat_completion(model=MODEL, messages=[
            {"role": "system", "content": self._SYSTEM},
            {"role": "user", "content": f"기존 요약:\n{memory.summary}\n\n새 대화:\n{convo}\n\n갱신된 요약:"},
        ])
        summary = (resp.choices[0].message.content or memory.summary).strip()
        facts = {k: (list(v) if isinstance(v, list) else v) for k, v in memory.facts.items()}
        for t in turns:
            _merge_facts(facts, t)  # 핵심 식별자는 규칙으로도 보존
        return ConversationMemory(summary=summary, facts=facts,
                                  summarized_through=memory.summarized_through)


@dataclass
class CompactionService:
    """트리거 판정 + 컴팩션 + 워킹 컨텍스트 조립(rehydrate)."""
    compactor: Compactor
    keep_recent: int = DEFAULT_KEEP_RECENT

    def should_compact(self, memory: ConversationMemory, messages: list[dict]) -> bool:
        """흡수 안 된 메시지가 최근 keep_recent를 넘으면 압축."""
        return (len(messages) - memory.summarized_through) > self.keep_recent

    def compact(self, memory: ConversationMemory, messages: list[dict]) -> ConversationMemory:
        """summarized_through .. (len-keep_recent) 구간을 요약으로 접는다."""
        end = len(messages) - self.keep_recent
        if end <= memory.summarized_through:
            return memory
        folded = self.compactor.fold(memory, messages[memory.summarized_through:end])
        return ConversationMemory(summary=folded.summary, facts=folded.facts, summarized_through=end)

    def maybe_compact(self, memory: ConversationMemory, messages: list[dict]) -> ConversationMemory:
        return self.compact(memory, messages) if self.should_compact(memory, messages) else memory

    def working_context(self, memory: ConversationMemory, messages: list[dict]) -> dict:
        """LLM에 넣을 맥락 = 요약 + 사실 + 흡수 안 된 최근 verbatim(rehydrate)."""
        return {
            "summary": memory.summary,
            "facts": memory.facts,
            "recent": messages[memory.summarized_through:],
        }
