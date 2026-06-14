"""실험·롤아웃(S8, ADR-0064) — 결정성·분포·토글·canary/홀드아웃·노출·통합.

단위(registry·assignment·exposure) + 통합(TestClient, 신규 라우터).
토글 `EXPERIMENTS`(기본 off)면 항상 control(회귀 불변).
"""
import pytest
from fastapi.testclient import TestClient

from app.api.internal import app
from app.experiments import assignment, exposure
from app.experiments.registry import Experiment, Variant, get, register


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    """대부분 테스트는 토글 on에서 검증(off 회귀는 별도). de-dup 셋 초기화."""
    monkeypatch.setenv("EXPERIMENTS", "1")
    exposure.reset_dedup()
    yield


def _exp(**kw):
    base = dict(
        key="exp_a",
        variants=(Variant("control", 1.0), Variant("treatment", 1.0)),
        control="control",
        rollout=1.0,
        holdout=0.0,
        salt="exp_a",
    )
    base.update(kw)
    return Experiment(**base)


# ── 토글(요구사항 3) ────────────────────────────────────────────────────────
def test_toggle_off_always_control(monkeypatch):
    monkeypatch.setenv("EXPERIMENTS", "0")
    exp = _exp()
    assert assignment.assign(exp, "user-123") == "control"
    # off면 노출도 미발행(요구사항 3.2)
    assert exposure.record_exposure("exp_a", "treatment", "user-123") is None


# ── 결정성·sticky(요구사항 1.1) ─────────────────────────────────────────────
def test_assignment_is_deterministic():
    exp = _exp()
    a = assignment.assign(exp, "user-123")
    b = assignment.assign(exp, "user-123")
    assert a == b
    assert a in ("control", "treatment")


def test_no_unit_falls_back_to_control():
    exp = _exp()
    assert assignment.assign(exp, None) == "control"
    assert assignment.assign(exp, "") == "control"


# ── 분포 근사(요구사항 1.2) ─────────────────────────────────────────────────
def test_weighted_distribution_approximates_ratio():
    # 75/25 가중치 — 대량 unit이 비율에 근사해야.
    exp = _exp(variants=(Variant("control", 3.0), Variant("treatment", 1.0)))
    n = 4000
    treat = sum(1 for i in range(n) if assignment.assign(exp, f"u{i}") == "treatment")
    frac = treat / n
    assert 0.18 < frac < 0.32  # 0.25 근방


# ── canary rollout(요구사항 6) ──────────────────────────────────────────────
def test_rollout_zero_all_control():
    exp = _exp(rollout=0.0)
    assert all(assignment.assign(exp, f"u{i}") == "control" for i in range(200))


def test_rollout_partial_some_treatment():
    exp = _exp(rollout=0.5, variants=(Variant("treatment", 1.0),), control="control")
    n = 2000
    treat = sum(1 for i in range(n) if assignment.assign(exp, f"u{i}") == "treatment")
    frac = treat / n
    assert 0.4 < frac < 0.6  # 약 절반만 실험 대상


def test_holdout_excludes_some_to_control():
    # holdout=1.0 → 전원 control(전체 홀드아웃)
    exp = _exp(holdout=1.0, variants=(Variant("treatment", 1.0),))
    assert all(assignment.assign(exp, f"u{i}") == "control" for i in range(200))


# ── 레지스트리 폴백(요구사항 2.2) ───────────────────────────────────────────
def test_variant_for_unknown_key_is_control():
    assert assignment.variant_for("does_not_exist", "user-1") == "control"


def test_variant_for_registered_key():
    register(_exp(key="reg_exp", salt="reg_exp"))
    v = assignment.variant_for("reg_exp", "user-1")
    assert v in ("control", "treatment")
    assert get("reg_exp") is not None


# ── 노출 append + de-dup(요구사항 5) ────────────────────────────────────────
class _FakeSink:
    def __init__(self):
        self.events = []

    def record(self, name, props=None, ts=None, principal=None):
        self.events.append({"name": name, "props": props, "principal": principal})
        return self.events[-1]


def test_exposure_appends_event_with_props():
    sink = _FakeSink()
    ev = exposure.record_exposure("exp_a", "treatment", "user-9", sink=sink)
    assert ev is not None
    assert len(sink.events) == 1
    e = sink.events[0]
    assert e["name"] == "experiment_exposed"
    assert e["props"]["experiment"] == "exp_a"
    assert e["props"]["variant"] == "treatment"


def test_exposure_dedup():
    sink = _FakeSink()
    exposure.record_exposure("exp_a", "treatment", "user-9", sink=sink)
    again = exposure.record_exposure("exp_a", "treatment", "user-9", sink=sink)
    assert again is None
    assert len(sink.events) == 1  # 중복 억제


def test_variant_for_expose_records(monkeypatch):
    register(_exp(key="exp_expose", variants=(Variant("treatment", 1.0),),
                  control="control", salt="exp_expose"))
    sink = _FakeSink()
    v = assignment.variant_for("exp_expose", "user-42", expose=True, sink=sink)
    assert v == "treatment"
    assert any(e["name"] == "experiment_exposed" for e in sink.events)


# ── 통합: 라우터(요구사항 4.3) ──────────────────────────────────────────────
def test_assign_endpoint_returns_assignments(monkeypatch):
    monkeypatch.setenv("EXPERIMENTS", "1")
    register(_exp(key="ep_exp", salt="ep_exp"))
    client = TestClient(app)
    r = client.get("/internal/experiments/assign", params={"keys": "ep_exp"})
    assert r.status_code == 200
    body = r.json()
    assert "assignments" in body
    assert body["assignments"]["ep_exp"] in ("control", "treatment")
    # 같은 unit(기본 사용자) → 결정적 동일
    r2 = client.get("/internal/experiments/assign", params={"keys": "ep_exp"})
    assert r2.json()["assignments"]["ep_exp"] == body["assignments"]["ep_exp"]


def test_assign_endpoint_toggle_off_control(monkeypatch):
    monkeypatch.setenv("EXPERIMENTS", "0")
    register(_exp(key="ep_off", variants=(Variant("treatment", 1.0),),
                  control="control", salt="ep_off"))
    client = TestClient(app)
    r = client.get("/internal/experiments/assign", params={"keys": "ep_off"})
    assert r.json()["assignments"]["ep_off"] == "control"
