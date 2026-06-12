"""컴패니언 — 턴 기록·컴팩션 배선(§0.4) + 이어가기(§1). 결정적."""
from datetime import datetime, timedelta, timezone

from app.companion import CompanionService, relative_label
from app.compaction import CompactionService, RuleBasedCompactor
from app.repositories import (
    InMemoryConversationMemoryRepository,
    InMemoryConversationStore,
    InMemoryOpenLoopRepository,
)

NOW = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)


def _svc(keep=2):
    return CompanionService(InMemoryConversationMemoryRepository(),
                            InMemoryConversationStore(),
                            CompactionService(RuleBasedCompactor(), keep_recent=keep),
                            InMemoryOpenLoopRepository())


# ── 턴 루프 배선 ──────────────────────────────────────────────────────────────
def test_record_turn_accumulates_and_compacts():
    svc = _svc(keep=2)
    for i in range(4):
        svc.record_turn("u1", f"질문{i}", f"답변{i}", now=NOW)
    mem = svc.memory.get("u1")
    assert mem.summarized_through > 0          # 임계 초과 → 컴팩션 발생
    assert "질문0" in mem.summary              # 오래된 턴은 요약으로


def test_context_rehydrates_for_next_turn():
    svc = _svc(keep=2)
    svc.record_turn("u1", "세탁기 5C", "확인할게요", now=NOW)
    ctx = svc.context("u1")
    assert "summary" in ctx and "facts" in ctx and "recent" in ctx
    assert "5C" in ctx["facts"].get("error_codes", [])  # 사실 보존(손실 방지)


def test_user_isolation():
    svc = _svc()
    svc.record_turn("u1", "안녕", "네", now=NOW)
    assert svc.store.messages("u2") == []      # 다른 user 격리


# ── 이어가기 ─────────────────────────────────────────────────────────────────
def test_resume_has_context_after_turns():
    svc = _svc(keep=2)
    svc.record_turn("u1", "주문 ord_x1 진행", "완료", now=NOW)
    r = svc.resume("u1", now=NOW + timedelta(days=1))
    assert r.has_context is True
    assert r.elapsed_label == "어제"
    assert "ord_x1" in r.facts.get("orders", [])


def test_resume_fresh_start():
    svc = _svc()
    svc.record_turn("u1", "이전 대화", "응", now=NOW)
    r = svc.resume("u1", fresh=True)
    assert r.has_context is False and r.summary == ""


def test_resume_first_visit_clean():
    r = _svc().resume("new_user")
    assert r.has_context is False and r.elapsed_label is None


def test_forget_clears_all():
    svc = _svc()
    svc.record_turn("u1", "기억해", "응", now=NOW)
    svc.forget("u1")
    assert svc.resume("u1").has_context is False
    assert svc.store.messages("u1") == []


# ── 미해결 스레드(OpenLoop §2) ───────────────────────────────────────────────
def test_open_loops_auto_created_from_facts():
    svc = _svc(keep=1)
    svc.record_turn("u1", "세탁기 5C 떠요", "주문 ord_x1 넣었어요", now=NOW)
    loops = svc.open_loops("u1")
    refs = {l.ref for l in loops}
    assert "5C" in refs and "ord_x1" in refs
    # 안전·CS(오류)가 주문보다 우선순위 높음 → 먼저
    assert loops[0].ref == "5C"


def test_open_loop_resolved_not_revived():
    svc = _svc(keep=1)
    svc.record_turn("u1", "5C 에러", "확인할게요", now=NOW)
    svc.resolve_loop("u1", "5C")
    assert svc.open_loops("u1") == []                  # 해소됨
    svc.record_turn("u1", "또 5C", "다시 볼게요", now=NOW)
    assert svc.open_loops("u1") == []                  # 해소된 건 되살리지 않음


def test_resume_includes_open_loops():
    svc = _svc(keep=1)
    svc.record_turn("u1", "ord_a1 주문함", "네", now=NOW)
    r = svc.resume("u1", now=NOW)
    assert any(l.ref == "ord_a1" for l in r.open_loops)


# ── 상대 시간 라벨 ────────────────────────────────────────────────────────────
def test_relative_label():
    assert relative_label(NOW, NOW + timedelta(seconds=10)) == "방금"
    assert relative_label(NOW, NOW + timedelta(minutes=5)) == "5분 전"
    assert relative_label(NOW, NOW + timedelta(days=1)) == "어제"
    assert relative_label(NOW, NOW + timedelta(days=8)) == "지난주"
