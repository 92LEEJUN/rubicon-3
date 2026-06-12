"""선제 재관여 — 엄격 게이트(동의·빈도·중복·묶음) (컴패니언 §3, ADR-0042)."""
from datetime import datetime, timedelta, timezone

from app.companion import CompanionService
from app.compaction import CompactionService, RuleBasedCompactor
from app.domain import Consent, Preferences, User
from app.reengagement import ReEngagementService
from app.repositories import (
    InMemoryConversationMemoryRepository,
    InMemoryConversationStore,
    InMemoryEngagementRepository,
    InMemoryOpenLoopRepository,
)

NOW = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)


def _user(opt_in=True, scopes=("device_data",)):
    return User(id="u1", display_name="준희",
                preferences=Preferences(notify_opt_in=opt_in),
                consent=Consent(scopes=list(scopes)))


def _setup(cooldown=3600):
    eng = InMemoryEngagementRepository()
    comp = CompanionService(InMemoryConversationMemoryRepository(), InMemoryConversationStore(),
                            CompactionService(RuleBasedCompactor(), keep_recent=1),
                            InMemoryOpenLoopRepository())
    return comp, ReEngagementService(comp, eng, cooldown_sec=cooldown)


def _seed_loops(comp, user):
    comp.record_turn(user.id, "세탁기 5C, ord_x1 주문", "확인할게요", now=NOW)


# ── 통과 + 묶음(R27) ─────────────────────────────────────────────────────────
def test_candidate_bundles_by_priority():
    comp, svc = _setup()
    u = _user()
    _seed_loops(comp, u)                       # open-loops: 5C(issue,우선) + ord_x1(order)
    cand = svc.candidate(u, now=NOW)
    assert cand is not None
    assert cand.primary_ref == "5C"            # 안전/CS 우선이 대표
    assert cand.also_count == 1                # 나머지 1건 묶음
    assert "외 1건" in cand.message


# ── 게이트 1: 동의/opt-in ─────────────────────────────────────────────────────
def test_gate_consent_blocks():
    comp, svc = _setup()
    _seed_loops(comp, _user())
    assert svc.candidate(_user(opt_in=False), now=NOW) is None      # opt-in off
    assert svc.candidate(_user(scopes=()), now=NOW) is None         # 관련 scope 없음


# ── 게이트 2: 빈도(cooldown) ──────────────────────────────────────────────────
def test_gate_frequency_cooldown():
    comp, svc = _setup(cooldown=3600)
    u = _user()
    _seed_loops(comp, u)
    assert svc.candidate(u, now=NOW) is not None
    svc.mark_sent(u, now=NOW)
    assert svc.candidate(u, now=NOW + timedelta(minutes=30)) is None  # 쿨다운 내 차단


# ── 게이트 3: 중복(이미 재관여한 loop 억제) ───────────────────────────────────
def test_gate_dedup_after_sent():
    comp, svc = _setup(cooldown=0)             # 빈도 게이트 제외
    u = _user()
    _seed_loops(comp, u)
    assert svc.candidate(u, now=NOW) is not None
    svc.mark_sent(u, now=NOW)
    assert svc.candidate(u, now=NOW) is None    # 보낸 loop는 중복 억제(피로 방지)


def test_no_loops_no_candidate():
    _, svc = _setup()
    assert svc.candidate(_user(), now=NOW) is None
