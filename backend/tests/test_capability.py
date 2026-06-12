"""capability 오케스트레이터(ADR-0046) — 조언형/행동형 분리·CTA 게이팅·크로스턴 carry.

규칙기반 분류기 + Mock 컨테이너로 네트워크 없이 결정적 검증(요구사항 15).
"""
from app.domain import Solution, SolutionStep
from app.orchestrator.capability import (
    CapabilityOrchestrator,
    advisory_catalog,
    build_registry,
)
from app.orchestrator.classify import RuleBasedClassifier


def _orch(container):
    return CapabilityOrchestrator(container=container, classifier=RuleBasedClassifier())


def _cta_kinds(section):
    return [c.kind for c in section.ctas]


# ── 레지스트리: 조언형/행동형 분리(요구사항 1·4) ────────────────────────────
def test_advisory_catalog_excludes_action():
    reg = build_registry()
    names = {c.name for c in advisory_catalog(reg)}
    assert "order" not in names                      # 행동형은 플래너 후보 아님
    assert {"diagnose", "recommend", "device_status"} <= names


def test_action_not_auto_selected_on_vague_query(container):
    # 모호 질의 — order 의도 없음 → order capability 미포함(자동 라우팅 금지, 요구사항 3-1)
    plan = _orch(container).plan("세탁기에서 물이 안 빠져요")
    assert "order" not in plan.capabilities
    assert "diagnose" in plan.capabilities


def test_explicit_order_intent_allowed(container):
    plan = _orch(container).plan("배수 필터 주문해줘")
    assert "order" in plan.capabilities            # 명시 의도는 허용(초안 산출)


# ── 수리 CTA 게이팅(요구사항 6) ─────────────────────────────────────────────
def test_diagnose_simple_keeps_part_cta(container):
    # 세탁기 5C — 안전 caution·coverage unknown → 부품 자가주문 CTA 노출
    turn = _orch(container).build_turn("세탁기에서 물이 안 빠져요")
    guide = next(s for s in turn.sections if s.template.kind == "guide_steps")
    assert "order" in _cta_kinds(guide)            # add_to_cart 동봉
    assert "handoff" in _cta_kinds(guide) and "booking" in _cta_kinds(guide)
    assert "cta_notice" not in guide.template.data


def test_diagnose_warranty_hides_part_cta(container):
    # 냉장고 정수필터 — coverage=free(보증 무상) → 부품 CTA 숨김 + 설명
    turn = _orch(container).build_turn("냉장고 정수필터 문제 해결 방법 알려줘")
    guide = next(s for s in turn.sections if s.template.kind == "guide_steps")
    assert "order" not in _cta_kinds(guide)        # 자가주문 숨김
    assert "handoff" in _cta_kinds(guide) and "booking" in _cta_kinds(guide)
    assert "보증" in guide.template.data.get("cta_notice", "")


def test_diagnose_message_danger_without_solution(container):
    # 해결책이 없는 기기(인덕션)라도 위험 표지가 있으면 안전 경고로 응답(게이팅)
    turn = _orch(container).build_turn(
        "인덕션에서 타는 냄새가 나고 가끔 스파크도 튀어요. 계속 써도 되나요? 해결법 알려줘")
    sec = next(s for s in turn.sections if s.intent == "troubleshoot")
    assert "order" not in _cta_kinds(sec)              # 부품 CTA 없음
    assert "handoff" in _cta_kinds(sec) and "booking" in _cta_kinds(sec)
    assert "위험" in sec.template.data.get("cta_notice", "")
    assert sec.handled is True                          # 안전 안내는 처리된 응답


def test_diagnose_danger_hides_part_cta(container, monkeypatch):
    # 합성 danger 해결책 — 안전 위험 → 부품 CTA 숨김 + 위험 설명(요구사항 6-3)
    danger = Solution(
        id="sol_danger", anomaly_id=None,
        steps=[SolutionStep(order=1, instruction="가스 밸브를 잠그세요.", safety="danger")],
        required_parts=["part_drain_filter"], escalation_needed=True, coverage="unknown")
    monkeypatch.setattr(container.knowledge, "best_solution", lambda *a, **k: danger)
    turn = _orch(container).build_turn("인덕션 고장 같아요 해결 방법 알려줘")
    guide = next(s for s in turn.sections if s.template.kind == "guide_steps")
    assert "order" not in _cta_kinds(guide)
    assert "위험" in guide.template.data.get("cta_notice", "")


# ── 크로스턴 carry(요구사항 5) ──────────────────────────────────────────────
def test_cross_turn_carry_order(container):
    orch = _orch(container)
    orch.build_turn("세탁기에서 물이 안 빠져요", session_id="sX")          # T1: 진단→required_parts
    # 중간 무관 질의(맥락 유지, capability 오작동 없음)
    orch.build_turn("그냥 안내 좀", session_id="sX")
    turn = orch.build_turn("아까 그 부품 주문해줘", session_id="sX")       # T3: carry
    card = next((s for s in turn.sections if s.template.kind == "product_card"), None)
    assert card is not None and card.template.data["id"] == "part_drain_filter"


def test_session_isolation(container):
    orch = _orch(container)
    orch.build_turn("세탁기에서 물이 안 빠져요", session_id="sA")
    # 다른 세션엔 carry 누수 없음 → 주문할 부품 못 찾음(handled=False)
    turn = orch.build_turn("부품 주문해줘", session_id="sB")
    order_secs = [s for s in turn.sections if s.intent == "order"]
    assert order_secs and all(s.handled is False for s in order_secs)


# ── 봉투 패리티(요구사항 13) ────────────────────────────────────────────────
def test_stream_emits_section_flow_done(container):
    chunks = list(_orch(container).stream_turn("세탁기 물이 안 빠져요"))
    types = [c["type"] for c in chunks]
    assert "section" in types and types[-1] == "done"
    assert any(c["type"] == "flow" for c in chunks)
