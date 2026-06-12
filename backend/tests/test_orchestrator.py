"""오케스트레이터 — 분류·우선순위·섹션 생성(복합 R7). 규칙기반 분류기로 네트워크 없이 검증.

옛 core.Orchestrator 제거(§12.3) 후 결정적 경로는 CapabilityOrchestrator(플래너 없음)로 수렴.
"""
from app.orchestrator import CapabilityOrchestrator, RuleBasedClassifier
from app.orchestrator.classify import OpenAIClassifier


def _orch(container):
    return CapabilityOrchestrator(container=container, classifier=RuleBasedClassifier())


# ── 분류기 ───────────────────────────────────────────────────────────────────
def test_classifier_single_troubleshoot():
    r = RuleBasedClassifier().classify("세탁기에서 물이 안 빠져요")
    assert r.intents == ["troubleshoot"]
    assert r.is_compound is False


def test_classifier_compound_j5():
    msg = "세탁기 물 안 빠지는 거 해결법 알려주고, 냉장고 정수필터랑 공기청정기 HEPA 필터도 주문해줘"
    r = RuleBasedClassifier().classify(msg)
    assert set(r.intents) == {"troubleshoot", "order"}
    assert r.is_compound is True


# ── J1: 해결 + 부품 주문(맥락 전달) ─────────────────────────────────────────
def test_j1_troubleshoot_then_order_carries_part(container):
    turn = _orch(container).build_turn("세탁기에서 물이 안 빠져요. 해결하고 부품도 주문할래요")
    kinds = [s.template.kind for s in turn.sections]
    assert "guide_steps" in kinds                      # 해결 가이드
    assert "product_card" in kinds                     # 배수필터 주문 카드(맥락 전달)
    guide = next(s for s in turn.sections if s.template.kind == "guide_steps")
    assert guide.template.data["required_parts"] == ["part_drain_filter"]
    card = next(s for s in turn.sections if s.template.kind == "product_card")
    assert card.template.data["id"] == "part_drain_filter"
    assert turn.active_flow == "troubleshoot"


def test_troubleshoot_priority_before_order(container):
    turn = _orch(container).build_turn("세탁기 물 안 빠져요 부품 주문해줘")
    intents_order = [s.intent for s in turn.sections]
    assert intents_order.index("troubleshoot") < intents_order.index("order")


# ── J5: 복합 — handled/unhandled 구분 ───────────────────────────────────────
def test_j5_compound_handled_and_unhandled(container):
    msg = "세탁기 물 안 빠지는 거 해결법 알려주고, 냉장고 정수필터랑 공기청정기 HEPA 필터도 주문해줘"
    turn = _orch(container).build_turn(msg)
    by_part = {s.template.data.get("id") or s.template.data.get("part_id"): s
               for s in turn.sections if s.intent == "order"}
    # 정수필터 = 재고 → 처리(product_card)
    assert by_part["part_water_filter"].handled is True
    assert by_part["part_water_filter"].template.kind == "product_card"
    # HEPA = 품절 → 미처리(text, handled=False)
    assert by_part["part_hepa"].handled is False
    assert by_part["part_hepa"].template.kind == "text"


# ── 스트림 봉투(api-contract §2.1) ──────────────────────────────────────────
def test_stream_emits_section_flow_done(container):
    chunks = list(_orch(container).stream_turn("세탁기 물이 안 빠져요"))
    types = [c["type"] for c in chunks]
    assert "section" in types
    assert types[-1] == "done"
    assert any(c["type"] == "flow" for c in chunks)


def test_stream_fallback_on_error(container, monkeypatch):
    orch = _orch(container)
    monkeypatch.setattr(orch, "build_turn",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    chunks = list(orch.stream_turn("아무거나"))
    assert chunks[0]["type"] == "error"
    assert chunks[0]["fallback"]["kind"] == "text"


# ── 추천(개인화) ─────────────────────────────────────────────────────────────
def test_recommend_section(container):
    turn = _orch(container).build_turn("공기청정기 신제품 추천해줘")
    rec = next(s for s in turn.sections if s.intent == "recommend")
    assert rec.template.kind == "recommendation_list"
    assert any(p["id"] == "prod_purifier_cube" for p in rec.template.data["products"])


def test_classifiers_satisfy_protocol():
    from app.orchestrator.classify import IntentClassifier
    assert isinstance(RuleBasedClassifier(), IntentClassifier)
    assert isinstance(OpenAIClassifier(), IntentClassifier)
