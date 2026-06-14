"""만족도 수집 테스트(ADR-0066) — CSAT/NPS·미해결 힌트·신호 emit·동의·토글 회귀."""
from __future__ import annotations

import pytest

from app.domain import Consent, User
from app.improve.signals import SignalCollector
from app.repositories import InMemoryEngagementRepository
from app.satisfaction import SatisfactionService


def _user(scopes=("engagement",)):
    return User(id="usr_1", display_name="준희", consent=Consent(scopes=list(scopes)))


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setenv("SELF_IMPROVE", "1")


def test_collect_records_and_marks_engagement():
    eng = InMemoryEngagementRepository()
    svc = SatisfactionService(eng)
    rec = svc.collect(_user(), "washer", 5, kind="csat")
    assert rec.score == 5 and rec.resolved is True
    assert eng.has_seen("usr_1", "sat:washer")        # Engagement 기록(중복·개인화)
    assert svc.records("usr_1")[0].topic == "washer"


def test_unresolved_returns_rediagnose_hint():
    svc = SatisfactionService(InMemoryEngagementRepository())
    rec = svc.collect(_user(), "dryer", 2, resolved=False)
    assert rec.to_dict()["next_action"] == "rediagnose"


def test_emits_satisfaction_signal_to_sink():
    sink = SignalCollector()
    svc = SatisfactionService(InMemoryEngagementRepository(), signal_sink=sink.collect)
    svc.collect(_user(), "washer", 4)
    sats = sink.window("satisfaction")
    assert len(sats) == 1 and sats[0].ref == "washer" and sats[0].value == 4


def test_unresolved_also_emits_handoff_signal():
    sink = SignalCollector()
    svc = SatisfactionService(InMemoryEngagementRepository(), signal_sink=sink.collect)
    svc.collect(_user(), "dryer", 1, resolved=False)
    assert len(sink.window("handoff")) == 1


def test_signal_dropped_without_consent_scope():
    sink = SignalCollector()
    svc = SatisfactionService(InMemoryEngagementRepository(), signal_sink=sink.collect)
    # 관련 동의 scope 없음 → 신호 emit은 consent_ok=False로 드롭(R28)
    svc.collect(_user(scopes=()), "washer", 5)
    assert sink.window("satisfaction") == []


def test_toggle_off_drops_signals(monkeypatch):
    monkeypatch.setenv("SELF_IMPROVE", "0")
    sink = SignalCollector()
    svc = SatisfactionService(InMemoryEngagementRepository(), signal_sink=sink.collect)
    rec = svc.collect(_user(), "washer", 5)           # 수집(기록)은 동작 — 추가형
    assert rec.score == 5
    assert sink.window() == []                         # 신호는 토글 off면 미적재(회귀 불변)
