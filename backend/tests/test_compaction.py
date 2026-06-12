"""대화 컴팩션 — 트리거·요약·사실 추출·rehydrate (ADR-0040, 결정적 RuleBasedCompactor)."""
from app.compaction import CompactionService, RuleBasedCompactor
from app.domain import ConversationMemory
from app.repositories import InMemoryConversationMemoryRepository


def _svc(keep=2):
    return CompactionService(RuleBasedCompactor(), keep_recent=keep)


def _msgs(n, role="user"):
    return [{"role": role, "text": f"메시지{i}"} for i in range(n)]


# ── 트리거 ───────────────────────────────────────────────────────────────────
def test_should_compact_only_when_exceeds_keep_recent():
    svc = _svc(keep=2)
    mem = ConversationMemory()
    assert svc.should_compact(mem, _msgs(2)) is False   # 최근 2 이하 → 안 함
    assert svc.should_compact(mem, _msgs(5)) is True


def test_compact_folds_older_keeps_recent_verbatim():
    svc = _svc(keep=2)
    mem = svc.compact(ConversationMemory(), _msgs(5))
    assert mem.summarized_through == 3                  # 5 - keep(2)
    assert "메시지0" in mem.summary and "메시지2" in mem.summary
    assert "메시지4" not in mem.summary                 # 최근 2는 verbatim(요약 제외)


def test_compact_is_incremental_no_double_fold():
    svc = _svc(keep=2)
    msgs = _msgs(5)
    mem = svc.compact(ConversationMemory(), msgs)       # through=3
    msgs += _msgs(3)                                    # 총 8
    mem2 = svc.compact(mem, msgs)                       # through=6, 3..6만 새로 접음
    assert mem2.summarized_through == 6
    assert mem.summary in mem2.summary                  # 기존 요약 보존(중복 접기 없음)


# ── 사실 추출(손실 방지) ──────────────────────────────────────────────────────
def test_facts_extract_order_and_error_codes():
    svc = _svc(keep=1)
    msgs = [
        {"role": "user", "text": "세탁기 5C 떠요"},
        {"role": "assistant", "text": "주문 ord_abc123 생성했어요"},
        {"role": "user", "text": "고마워요"},
    ]
    mem = svc.compact(ConversationMemory(), msgs)
    assert "5C" in mem.facts.get("error_codes", [])
    assert "ord_abc123" in mem.facts.get("orders", [])


def test_explicit_facts_merge():
    svc = _svc(keep=0)
    msgs = [{"role": "user", "text": "내 세탁기", "facts": {"device": "WF45"}}]
    mem = svc.compact(ConversationMemory(), msgs)
    assert mem.facts["device"] == "WF45"


# ── rehydrate ────────────────────────────────────────────────────────────────
def test_working_context_rehydrates_summary_facts_recent():
    svc = _svc(keep=2)
    msgs = _msgs(5)
    mem = svc.compact(ConversationMemory(), msgs)
    ctx = svc.working_context(mem, msgs)
    assert ctx["summary"] == mem.summary
    assert len(ctx["recent"]) == 2                      # 흡수 안 된 최근만 verbatim


# ── user 단위 repository(교차기기) ────────────────────────────────────────────
def test_repository_user_keyed_and_delete():
    repo = InMemoryConversationMemoryRepository()
    assert repo.get("u1").summary == ""                 # 첫 방문 = 빈 메모리
    repo.save("u1", ConversationMemory(summary="기억함"))
    assert repo.get("u1").summary == "기억함"            # 다른 세션/기기에서도 같은 user면 복원
    assert repo.get("u2").summary == ""                 # 다른 user는 격리
    repo.delete("u1")
    assert repo.get("u1").summary == ""                 # 삭제 cascade(R19)
