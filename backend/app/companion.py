"""컴패니언 서비스 — 턴 기록·컴팩션 배선 + 이어가기(resume).

"언제든 곁에 있는" 경험의 토대(`specs/always-present-companion/`):
- **턴 루프 배선(tasks §0.4)** — 턴마다 메시지 적재 → `maybe_compact` → 메모리 영속.
- **이어가기(tasks §1)** — 다시 열면 영속 메모리(요약+사실)·보류 흐름·상대 시간을 복원.

메모리·메시지는 **user 단위**(교차기기 연속, ADR-0040). 동의·삭제는 Consent/clear로 처리(R19).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .compaction import CompactionService, extract_facts
from .domain import ConversationMemory, OpenLoop, ResumePayload
from .repositories import (
    InMemoryConversationMemoryRepository,
    InMemoryConversationStore,
    InMemoryOpenLoopRepository,
)

# 자동 open-loop: 사실 종류 → (kind, 우선순위, 라벨 접두)
_LOOP_RULES = {
    "error_codes": ("issue", 2, "오류"),   # 안전·CS 우선
    "orders": ("order", 1, "주문"),
}


def relative_label(then: datetime, now: datetime) -> str:
    """경과 시간 → 상대 라벨(요구 5). 결정적(now 주입)."""
    delta = now - then
    secs = delta.total_seconds()
    if secs < 60:
        return "방금"
    if secs < 3600:
        return f"{int(secs // 60)}분 전"
    if secs < 86400:
        return f"{int(secs // 3600)}시간 전"
    days = int(secs // 86400)
    if days == 1:
        return "어제"
    if days < 7:
        return f"{days}일 전"
    if days < 14:
        return "지난주"
    return f"{days // 7}주 전"


@dataclass
class CompanionService:
    memory: InMemoryConversationMemoryRepository
    store: InMemoryConversationStore
    compaction: CompactionService
    open_loops_repo: InMemoryOpenLoopRepository

    # ── 턴 루프 배선 (§0.4) ──────────────────────────────────────────────────
    def context(self, user_id: str) -> dict:
        """다음 턴에 주입할 워킹 컨텍스트(요약+사실+최근 verbatim, rehydrate)."""
        return self.compaction.working_context(self.memory.get(user_id), self.store.messages(user_id))

    def record_turn(self, user_id: str, user_text: str, assistant_text: str,
                    *, facts: Optional[dict] = None, now: Optional[datetime] = None) -> None:
        """턴 적재 → 임계 초과 시 컴팩션 → 메모리 영속."""
        now = now or datetime.now(timezone.utc)
        user_turn = {"role": "user", "text": user_text}
        if facts:
            user_turn["facts"] = facts
        asst_turn = {"role": "assistant", "text": assistant_text}
        self.store.append(user_id, user_turn, now=now)
        self.store.append(user_id, asst_turn, now=now)
        mem = self.memory.get(user_id)
        # 사실은 매 턴 즉시 추출(요약 컴팩션과 무관하게 최신 유지 — 최근 턴 사실 누락 방지).
        mem = ConversationMemory(summary=mem.summary,
                                 facts=extract_facts(mem.facts, [user_turn, asst_turn]),
                                 summarized_through=mem.summarized_through)
        mem = self.compaction.maybe_compact(mem, self.store.messages(user_id))
        self.memory.save(user_id, mem)
        self._sync_open_loops(user_id, mem.facts, now)

    def _sync_open_loops(self, user_id: str, facts: dict, now: datetime) -> None:
        """사실(주문ID·오류코드)에서 미해결 스레드를 멱등 생성/갱신(요구 2.1)."""
        for fact_key, (kind, priority, prefix) in _LOOP_RULES.items():
            for ref in facts.get(fact_key, []):
                existing = self.open_loops_repo.get(user_id, ref)
                if existing and existing.status != "open":
                    continue  # 이미 해소된 건 되살리지 않음
                self.open_loops_repo.upsert(user_id, OpenLoop(
                    id=f"loop_{ref}", kind=kind, ref=ref, label=f"{prefix} {ref}",
                    priority=priority,
                    opened_at=existing.opened_at if existing else now, last_touch=now))

    # ── 미해결 스레드 (§2) ───────────────────────────────────────────────────
    def open_loops(self, user_id: str) -> list[OpenLoop]:
        return self.open_loops_repo.list_open(user_id)

    def resolve_loop(self, user_id: str, ref: str) -> Optional[OpenLoop]:
        """해소(R25 해결확인·주문 배송완료 등)."""
        return self.open_loops_repo.set_status(user_id, ref, "resolved")

    def dismiss_loop(self, user_id: str, ref: str) -> Optional[OpenLoop]:
        return self.open_loops_repo.set_status(user_id, ref, "dismissed")

    # ── 이어가기 (§1) ────────────────────────────────────────────────────────
    def resume(self, user_id: str, *, fresh: bool = False,
               suspended_flow: Optional[str] = None, now: Optional[datetime] = None) -> ResumePayload:
        """다시 열기 시 복원 맥락. fresh=True면 '새로 시작'(맥락 비주입)."""
        if fresh:
            return ResumePayload(has_context=False)
        mem = self.memory.get(user_id)
        loops = self.open_loops_repo.list_open(user_id)
        last = self.store.last_active(user_id)
        elapsed = relative_label(last, now or datetime.now(timezone.utc)) if last else None
        has_context = bool(mem.summary or mem.facts or loops or self.store.messages(user_id) or suspended_flow)
        return ResumePayload(has_context=has_context, summary=mem.summary, facts=mem.facts,
                             open_loops=loops, elapsed_label=elapsed, suspended_flow=suspended_flow)

    def forget(self, user_id: str) -> None:
        """삭제 요청 cascade(R19) — 메모리 + 워킹 메시지 + 미해결 스레드."""
        self.memory.delete(user_id)
        self.store.clear(user_id)
        self.open_loops_repo.clear(user_id)
