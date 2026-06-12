"""멀티에이전트 런타임 — 결정적 판정(plan/review) + 스텁 스트리밍 순서 (specs/multi-agent-runtime)."""
import asyncio
import types

from app.orchestrator import runtime


# ── 결정적 오케스트레이션 판정(LLM 무관) ──────────────────────────────────────
def test_plan_workers_mapping():
    assert runtime.plan_workers(["troubleshoot"]) == ["diagnosis"]
    assert runtime.plan_workers(["troubleshoot", "order"]) == ["diagnosis", "commerce"]
    assert runtime.plan_workers(["order"]) == ["commerce"]
    assert runtime.plan_workers(["recommend"]) == ["recommend"]           # 추천 = agent(ADR-0044)
    assert runtime.plan_workers(["troubleshoot", "recommend"]) == ["diagnosis", "recommend"]
    assert runtime.plan_workers([]) == ["general"]            # 폴백
    assert runtime.plan_workers(["device_status"]) == ["diagnosis"]


def test_recommend_tool_returns_products():
    from app.tools import call
    res = call("recommend", {})
    assert "products" in res and isinstance(res["products"], list)
    res_b = call("recommend", {"budget": 1})                  # 예산 상한 적용(결정적)
    assert all(p["price"] <= 1 for p in res_b["products"])


def test_should_review_conditional():
    assert runtime.should_review(["order"]) is True            # 커밋(R17)
    assert runtime.should_review(["troubleshoot"]) is False    # 일반 정보성 → 스킵
    assert runtime.should_review(["troubleshoot"], safety=True) is True   # 안전(R23)
    assert runtime.should_review(["recommend"], uncertain=True) is True   # 불확실(R16)


def test_extract_required_parts():
    res = {"solutions": [{"required_parts": ["part_a"]}, {"required_parts": ["part_b"]}]}
    assert runtime._extract_required_parts(res) == ["part_a", "part_b"]
    assert runtime._extract_required_parts({"required_parts": ["p"]}) == ["p"]
    assert runtime._extract_required_parts({}) == []


# ── 스텁 스트리밍 순서(LLM 미발동) ────────────────────────────────────────────
def _fake_resp(text):
    msg = types.SimpleNamespace(content=text, tool_calls=None)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


async def _collect(agen):
    return [c async for c in agen]


def test_streaming_order_compound(monkeypatch):
    async def fake_classify(_msg):
        return {"intents": ["troubleshoot", "order"], "is_compound": True}

    async def fake_achat(**_kw):
        return _fake_resp("ok")

    monkeypatch.setattr(runtime, "aclassify", fake_classify)
    monkeypatch.setattr(runtime, "achat_completion", fake_achat)

    chunks = asyncio.run(_collect(runtime.astream_multiagent("세탁기 5C, 부품 주문")))
    types_seq = [c["type"] for c in chunks]
    assert types_seq[-2:] == ["flow", "done"]          # 봉투 종료(api-contract §2.1)
    assert types_seq.count("delta") >= 2               # 진단·커머스 단계 점진 방출
    # 복합+order → 리뷰 발동(델타 1개 더): 진단·커머스·리뷰 = 3 delta
    assert types_seq.count("delta") == 3


def test_streaming_error_fallback(monkeypatch):
    async def boom(_msg):
        raise RuntimeError("classify down")

    monkeypatch.setattr(runtime, "aclassify", boom)
    chunks = asyncio.run(_collect(runtime.astream_multiagent("x")))
    assert chunks[0]["type"] == "error"                # 분해 실패 → error 폴백(중단 금지)
    assert chunks[0]["fallback"]["kind"] == "text"


def test_streaming_partial_fallback(monkeypatch):
    async def fake_classify(_msg):
        return {"intents": ["troubleshoot", "order"], "is_compound": True}

    async def boom_achat(**_kw):
        raise RuntimeError("worker down")

    monkeypatch.setattr(runtime, "aclassify", fake_classify)
    monkeypatch.setattr(runtime, "achat_completion", boom_achat)
    chunks = asyncio.run(_collect(runtime.astream_multiagent("세탁기 5C, 주문")))
    types_seq = [c["type"] for c in chunks]
    assert "error" not in types_seq                    # 단계 실패는 중단 아님(부분 폴백)
    assert types_seq[-1] == "done"
    assert types_seq.count("delta") >= 1               # 폴백 델타로 부분결과 유지


def test_streaming_recommend_stage(monkeypatch):
    async def fc(_m):
        return {"intents": ["recommend"], "is_compound": False}

    async def fa(**_k):
        return _fake_resp("공기청정기 추천")

    monkeypatch.setattr(runtime, "aclassify", fc)
    monkeypatch.setattr(runtime, "achat_completion", fa)
    chunks = asyncio.run(_collect(runtime.astream_multiagent("공기청정기 추천해줘")))
    types = [c["type"] for c in chunks]
    assert types.count("delta") == 1 and types[-1] == "done"  # recommend 단계 1개, 리뷰 스킵


def test_streaming_simple_no_review(monkeypatch):
    async def fake_classify(_msg):
        return {"intents": ["troubleshoot"], "is_compound": False}

    async def fake_achat(**_kw):
        return _fake_resp("가이드")

    monkeypatch.setattr(runtime, "aclassify", fake_classify)
    monkeypatch.setattr(runtime, "achat_completion", fake_achat)
    chunks = asyncio.run(_collect(runtime.astream_multiagent("세탁기 5C")))
    types_seq = [c["type"] for c in chunks]
    assert types_seq.count("delta") == 1               # 진단만(리뷰 스킵)
    assert types_seq[-1] == "done"
