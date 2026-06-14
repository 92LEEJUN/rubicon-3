"""S6 비용·캐싱 — 토큰/비용 회계·모델 라우팅·예산 가드·응답 캐싱(ADR-0062).

- 토큰/비용: 근사 추정·단가표/override·usage 우선·메트릭 노출·토글 off 무동작.
- 라우팅: off=기본 모델, on=단순/대량 경량·복잡 상위·결정성.
- 예산: 누적·세션/일 차단·강등·일 리셋(주입 시계)·상한 미설정 무제한.
- 캐시: 키 결정성·히트/미스·TTL·무효화·off/Noop=항상 compute·CachePort 재사용.
- llm.py 계측: 토글 off 무동작·시그니처 불변·예외 격리.

추가형 — 기존 테스트는 건드리지 않는다. CachePort/MockCache는 S3 것을 재사용한다.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import pytest

from app.adapters.cache import CachePort, MockCache, NoopCache
from app.cache_layer import ResponseCache, make_key
from app.cost import budget
from app.cost.accounting import (
    CostRecord,
    estimate_cost,
    estimate_messages_tokens,
    estimate_tokens,
    get_cost_metrics,
    maybe_record,
)
from app.cost.budget import BudgetGuard
from app.cost.routing import HEAVY_MODEL, LIGHT_MODEL, route_model


@contextmanager
def _env(**kv):
    """env 임시 설정(테스트 격리)."""
    old = {k: os.environ.get(k) for k in kv}
    try:
        for k, v in kv.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── 가짜 LLM 응답(usage/choices best-effort 추출 검증용) ──────────────────────
class _FakeUsage:
    def __init__(self, pt, ct):
        self.prompt_tokens = pt
        self.completion_tokens = ct


class _FakeMsg:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMsg(content)


class _FakeResp:
    def __init__(self, content="hi", usage=None):
        self.choices = [_FakeChoice(content)]
        self.usage = usage


# ── 토큰/비용 회계 (요구사항 1) ───────────────────────────────────────────────
def test_estimate_tokens_empty_and_monotonic():
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0
    short = estimate_tokens("hello")
    longer = estimate_tokens("hello world this is a longer sentence with more tokens")
    assert short >= 1
    assert longer > short


def test_estimate_messages_tokens_sums_content():
    msgs = [
        {"role": "system", "content": "be helpful"},
        {"role": "user", "content": "turn on the light please"},
    ]
    t = estimate_messages_tokens(msgs)
    assert t > estimate_tokens("turn on the light please")  # role 오버헤드 포함
    assert estimate_messages_tokens([]) == 0


def test_estimate_cost_uses_price_table():
    # gpt-4o-mini: in 0.00015, out 0.0006 per 1k
    cost = estimate_cost("gpt-4o-mini", 1000, 1000)
    assert cost == pytest.approx((0.00015 * 1000 + 0.0006 * 1000) / 1000)


def test_unknown_model_falls_back_to_light_price():
    assert estimate_cost("totally-unknown-model", 1000, 0) == pytest.approx(0.00015)


def test_price_env_override():
    with _env(LLM_PRICE_GPT_4O_MINI_IN="1.0", LLM_PRICE_GPT_4O_MINI_OUT="2.0"):
        cost = estimate_cost("gpt-4o-mini", 1000, 1000)
        assert cost == pytest.approx((1.0 * 1000 + 2.0 * 1000) / 1000)


# ── maybe_record / 메트릭 (요구사항 1, 5) ─────────────────────────────────────
def test_maybe_record_off_is_noop():
    get_cost_metrics().reset()
    budget.reset_default_guard()
    with _env(COST_TRACKING=None):
        rec = maybe_record("gpt-4o-mini", [{"role": "user", "content": "hi"}], _FakeResp())
    assert rec is None
    assert get_cost_metrics().snapshot() == (0.0, 0, 0, 0)


def test_maybe_record_on_uses_usage_when_present():
    get_cost_metrics().reset()
    budget.reset_default_guard()
    with _env(COST_TRACKING="1", COST_DAILY_BUDGET_USD=None, COST_SESSION_BUDGET_USD=None):
        rec = maybe_record(
            "gpt-4o-mini",
            [{"role": "user", "content": "hi"}],
            _FakeResp("ok", usage=_FakeUsage(100, 50)),
        )
    assert rec is not None
    assert rec.prompt_tokens == 100 and rec.completion_tokens == 50
    cost, pt, ct, calls = get_cost_metrics().snapshot()
    assert pt == 100 and ct == 50 and calls == 1
    assert cost == pytest.approx(estimate_cost("gpt-4o-mini", 100, 50))


def test_maybe_record_on_estimates_without_usage():
    get_cost_metrics().reset()
    budget.reset_default_guard()
    with _env(COST_TRACKING="1", COST_DAILY_BUDGET_USD=None, COST_SESSION_BUDGET_USD=None):
        rec = maybe_record(
            "gpt-4o-mini", [{"role": "user", "content": "turn on light"}], _FakeResp("done")
        )
    assert rec is not None and rec.prompt_tokens > 0 and rec.completion_tokens > 0


def test_maybe_record_swallows_bad_response():
    with _env(COST_TRACKING="1"):
        # usage/choices 없는 이상한 객체 — 예외 없이 추정 또는 None.
        assert maybe_record("gpt-4o-mini", None, object()) is not None or True


def test_cost_metrics_prometheus_text():
    get_cost_metrics().reset()
    get_cost_metrics().record(CostRecord("gpt-4o-mini", 10, 5, 0.0001))
    text = get_cost_metrics().prometheus("backend")
    assert "rubicon_llm_cost_usd_total" in text
    assert 'rubicon_llm_tokens_total{service="backend",kind="prompt"} 10' in text
    assert 'rubicon_llm_tokens_total{service="backend",kind="completion"} 5' in text
    assert "rubicon_llm_calls_total" in text


# ── 모델 라우팅 (요구사항 2) ──────────────────────────────────────────────────
def test_routing_off_returns_default_model():
    from app.llm import MODEL

    with _env(MODEL_ROUTING=None):
        assert route_model("complex") == MODEL
        assert route_model("simple", size_hint=99999) == MODEL


def test_routing_on_simple_is_light_complex_is_heavy():
    with _env(MODEL_ROUTING="1"):
        assert route_model("simple") == LIGHT_MODEL
        assert route_model("complex") == HEAVY_MODEL


def test_routing_on_large_downgrades_to_light():
    with _env(MODEL_ROUTING="1", MODEL_ROUTING_BIG_TOKENS=None):
        # 복잡이라도 대량(임계 초과)이면 경량.
        assert route_model("complex", size_hint=100000) == LIGHT_MODEL


def test_routing_is_deterministic():
    with _env(MODEL_ROUTING="1"):
        results = {route_model("complex", size_hint=10) for _ in range(20)}
        assert results == {HEAVY_MODEL}


# ── 예산 가드 (요구사항 3) ────────────────────────────────────────────────────
class _Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def test_budget_unlimited_when_no_caps():
    g = BudgetGuard(daily_usd=None, session_usd=None)
    g.add("s1", 1000.0)
    assert g.allow("s1") is True
    assert g.should_downgrade("s1") is False


def test_budget_session_cap_blocks_and_downgrades():
    g = BudgetGuard(session_usd=1.0)
    g.add("s1", 0.85)  # > 0.8 soft → downgrade
    assert g.should_downgrade("s1") is True
    assert g.allow("s1") is True  # < hard
    g.add("s1", 0.2)  # total 1.05 > hard
    assert g.allow("s1") is False


def test_budget_isolated_per_session():
    g = BudgetGuard(session_usd=1.0)
    g.add("s1", 2.0)
    assert g.allow("s1") is False
    assert g.allow("s2") is True


def test_budget_daily_cap_and_reset():
    clk = _Clock(0.0)
    g = BudgetGuard(daily_usd=1.0, now_fn=clk)
    g.add(None, 1.5)
    assert g.allow() is False
    clk.t = 86400 + 1  # 다음 날 → 일 누적 리셋
    assert g.allow() is True
    assert g.daily_total() == 0.0


# ── 응답 캐싱 (요구사항 4) ────────────────────────────────────────────────────
def test_make_key_deterministic_and_sensitive():
    msgs = [{"role": "user", "content": "hello"}]
    k1 = make_key("gpt-4o-mini", msgs)
    k2 = make_key("gpt-4o-mini", [{"content": "hello", "role": "user"}])  # 키 순서 무관
    assert k1 == k2
    assert make_key("gpt-4o", msgs) != k1  # 모델 다르면 키 다름
    assert make_key("gpt-4o-mini", [{"role": "user", "content": "bye"}]) != k1


def test_cache_off_always_computes():
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return calls["n"]

    rc = ResponseCache(MockCache())
    with _env(RESPONSE_CACHE=None):
        assert rc.get_or_compute("m", [{"content": "x"}], compute) == 1
        assert rc.get_or_compute("m", [{"content": "x"}], compute) == 2  # 캐시 미동작


def test_cache_on_hit_skips_compute():
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return f"v{calls['n']}"

    rc = ResponseCache(MockCache())
    with _env(RESPONSE_CACHE="1"):
        a = rc.get_or_compute("m", [{"content": "x"}], compute)
        b = rc.get_or_compute("m", [{"content": "x"}], compute)
    assert a == b == "v1"
    assert calls["n"] == 1  # 두 번째는 히트


def test_cache_ttl_expiry():
    clk = _Clock(0.0)
    cache = MockCache(now_fn=clk)
    rc = ResponseCache(cache, ttl=10.0)
    n = {"v": 0}

    def compute():
        n["v"] += 1
        return n["v"]

    with _env(RESPONSE_CACHE="1"):
        assert rc.get_or_compute("m", [{"content": "x"}], compute) == 1
        clk.t = 5
        assert rc.get_or_compute("m", [{"content": "x"}], compute) == 1  # 미만료=히트
        clk.t = 11
        assert rc.get_or_compute("m", [{"content": "x"}], compute) == 2  # 만료=재계산


def test_cache_invalidate_and_clear():
    rc = ResponseCache(MockCache())
    n = {"v": 0}

    def compute():
        n["v"] += 1
        return n["v"]

    with _env(RESPONSE_CACHE="1"):
        rc.get_or_compute("m", [{"content": "x"}], compute)
        rc.invalidate_for("m", [{"content": "x"}])
        assert rc.get_or_compute("m", [{"content": "x"}], compute) == 2  # 무효화 후 재계산
        rc.clear()
        assert rc.get_or_compute("m", [{"content": "x"}], compute) == 3


def test_cache_noop_backend_always_misses():
    rc = ResponseCache(NoopCache())
    n = {"v": 0}

    def compute():
        n["v"] += 1
        return n["v"]

    with _env(RESPONSE_CACHE="1"):
        assert rc.get_or_compute("m", [{"content": "x"}], compute) == 1
        assert rc.get_or_compute("m", [{"content": "x"}], compute) == 2  # Noop=항상 미스


def test_response_cache_reuses_cacheport():
    # ResponseCache가 주입된 CachePort를 그대로 쓰는지(새 저장소 안 만듦) 확인.
    backing = MockCache()
    rc = ResponseCache(backing)
    assert isinstance(rc._cache, CachePort)
    with _env(RESPONSE_CACHE="1"):
        rc.get_or_compute("m", [{"content": "x"}], lambda: "v")
    # 주입한 백엔드에 직접 키가 들어가 있어야 한다.
    assert backing.get(make_key("m", [{"content": "x"}])) == "v"


def test_cache_default_backend_is_select_cache():
    # 기본(CACHE_BACKEND 미지정)=NoopCache → 항상 미스(회귀 불변).
    with _env(CACHE_BACKEND=None, RESPONSE_CACHE="1"):
        rc = ResponseCache()
        n = {"v": 0}
        assert rc.get_or_compute("m", [{"content": "x"}], lambda: n.__setitem__("v", n["v"] + 1) or n["v"]) == 1
        assert rc.get_or_compute("m", [{"content": "x"}], lambda: n.__setitem__("v", n["v"] + 1) or n["v"]) == 2


# ── llm.py 계측 회귀 (요구사항 5) ─────────────────────────────────────────────
def test_llm_maybe_cost_isolated_from_main_path():
    import app.llm as llm

    # COST_TRACKING off → 무동작, 예외 없음.
    with _env(COST_TRACKING=None):
        llm._maybe_cost({"model": "gpt-4o-mini", "messages": [{"content": "x"}]}, _FakeResp())
    # 이상 입력에도 예외가 전파되지 않아야 한다.
    with _env(COST_TRACKING="1"):
        llm._maybe_cost({}, None)  # model/messages 누락 + None 응답


def test_chat_completion_signature_unchanged():
    import inspect

    import app.llm as llm

    # **kwargs 단일 시그니처 유지(회귀 불변).
    sig = inspect.signature(llm.chat_completion)
    assert list(sig.parameters) == ["kwargs"]
    asig = inspect.signature(llm.achat_completion)
    assert list(asig.parameters) == ["kwargs"]
