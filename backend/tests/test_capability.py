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


# ── 에스컬레이션 게이트(티어드 플래닝, ADR-0047) ───────────────────────────
# 깨끗한 케이스 = 홉 0(규칙 즉답). F1·F2 장문/모호 = 홉 1(LLM 플래너 필요).
_NO_ESCALATE = [
    "세탁기에서 물이 안 빠져요",                          # 짧은 단일
    "공기청정기 신제품 추천해줘",
    "배수필터 주문해줘",
    # J5 — 장문 복합이지만 규칙이 깨끗이 분류(troubleshoot+order)
    "세탁기 물 안 빠지는 거 해결법 알려주고, 냉장고 정수필터랑 공기청정기 HEPA 필터도 주문해줘",
    # A-T1 — 장문이지만 단일 의도 명확
    "어제 저녁부터 세탁기를 돌리면 중간에 멈추면서 물이 안 빠지는 것 같아요. "
    "안을 열어보니 물이 가득 차 있고 화면에 5C인가 하는 에러도 떴어요. 어떻게 해결하면 좋을까요?",
    # B-T1 — 위험 장문이지만 결정적 안전 게이팅으로 처리(홉 불필요)
    "주방에서 인덕션을 쓰는데 켜기만 하면 타는 냄새가 나고 가끔 스파크도 튀어요. 해결법 알려주세요",
]
_ESCALATE = [
    # F1 — '확인해/가격'이 약한 의도로 장문을 흡수
    "비용이 많이 들면 그냥 새로 살까 고민도 되는데, 그 배수 필터 어떤 건지 한번 확인해서 가격이랑 같이 알려주세요",
    # F2 — 보증·예약 후속 의도(미매핑)
    "산 지 얼마 안 됐으니까 보증으로 무상 수리가 되는지 궁금하고, 기사님 방문 예약도 가능한가요?",
    # F2 — 설명/비교 후속 의도(미매핑)
    "비스포크 큐브 그거 필터 교체나 소음이 어느 정도인지 더 알려주고 비교도 해줄 수 있어요?",
    "정수필터 가격 얼마인지 알려줘",
]


def test_escalation_gate_keeps_clean_on_fast_path(container):
    orch = _orch(container)
    for msg in _NO_ESCALATE:
        d = orch.decide(msg)
        assert d.escalate is False, f"불필요 에스컬레이션: {msg!r} → {d.reasons}"


def test_escalation_gate_flags_ambiguous(container):
    orch = _orch(container)
    for msg in _ESCALATE:
        d = orch.decide(msg)
        assert d.escalate is True, f"에스컬레이션 누락: {msg!r}"
        assert d.reasons


def test_route_falls_back_to_rule_without_planner(container):
    # LLM 플래너 미연결 → 에스컬레이션이어도 규칙 plan으로 폴백(홉 0, 동작 불변)
    orch = _orch(container)
    plan = orch.route(_ESCALATE[0])
    assert orch.last_decision.escalate is True
    assert isinstance(plan.capabilities, list)


# ── 봉투 패리티(요구사항 13) ────────────────────────────────────────────────
def test_stream_emits_section_flow_done(container):
    chunks = list(_orch(container).stream_turn("세탁기 물이 안 빠져요"))
    types = [c["type"] for c in chunks]
    assert "section" in types and types[-1] == "done"
    assert any(c["type"] == "flow" for c in chunks)
