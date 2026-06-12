"""capability 오케스트레이터(ADR-0046) — 조언형/행동형 분리·CTA 게이팅·크로스턴 carry.

규칙기반 분류기 + Mock 컨테이너로 네트워크 없이 결정적 검증(요구사항 15).
"""
from app.domain import Solution, SolutionStep
from app.orchestrator.capability import (
    CapabilityOrchestrator,
    Plan,
    TurnCtx,
    advisory_catalog,
    build_registry,
)
from app.orchestrator.classify import RuleBasedClassifier


def _orch(container):
    return CapabilityOrchestrator(container=container, classifier=RuleBasedClassifier())


def _ctx(container):
    return TurnCtx(container, {})


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


# ── 신규 조언형 capability (warranty·booking·explain·clarify, §9.3) ─────────
def test_warranty_capability_free(container):
    sec = _orch(container).registry["warranty"].run(_ctx(container), "냉장고 정수필터 보증 무상 수리 되나요")[0]
    assert sec.intent == "warranty" and sec.template.data["coverage"] == "free"
    assert "booking" in _cta_kinds(sec)            # 보증 수리 접수
    assert "무상" in sec.template.data["message"]


def test_booking_capability_lists_slots(container):
    sec = _orch(container).registry["booking"].run(_ctx(container), "기사님 방문 예약하고 싶어요")[0]
    assert sec.intent == "booking" and sec.template.kind == "booking"
    assert sec.template.data["slots"]              # 가능 슬롯 초안
    assert all(c.action == "commit" and c.kind == "booking" for c in sec.ctas)  # 커밋=확정


def test_explain_capability_uses_candidates(container):
    ctx = _ctx(container)
    ctx.write("candidates", ["prod_purifier_cube"])
    sec = _orch(container).registry["explain"].run(ctx, "그거 소음이랑 가격 더 알려줘")[0]
    assert sec.intent == "explain" and sec.template.kind == "recommendation_list"
    assert any(p["id"] == "prod_purifier_cube" for p in sec.template.data["products"])


def test_clarify_capability_asks_back(container):
    sec = _orch(container).registry["clarify"].run(_ctx(container), "이거 좀 어떻게 해줘")[0]
    assert sec.intent == "clarify"
    assert "select_device" in _cta_kinds(sec)      # 기기 빠른 선택지


def test_advisory_catalog_includes_new_caps():
    names = {c.name for c in advisory_catalog(build_registry())}
    assert {"warranty", "booking", "explain", "clarify"} <= names
    assert "order" not in names                    # 행동형은 여전히 제외


# ── LLM 플래너 = 단일 라우터(ADR-0048, stub로 결정적 검증) ──────────────────
class _StubPlanner:
    def __init__(self, caps):
        self.caps = caps
        self.calls = 0

    def propose(self, catalog, message):
        self.calls += 1
        from app.orchestrator.capability import Plan
        return Plan(capabilities=list(self.caps))


def test_planner_routes_every_query(container):
    # 게이트 폐기 — 깨끗한 짧은 쿼리도 LLM 플래너를 거친다(ADR-0048)
    stub = _StubPlanner(["diagnose"])
    orch = CapabilityOrchestrator(container=container, classifier=RuleBasedClassifier(),
                                  llm_planner=stub)
    orch.route("세탁기 물 안 빠져요")
    assert stub.calls == 1


def test_planner_routes_to_new_caps(container):
    # F2 — LLM이 보증·예약으로 라우팅(목적지 capability 존재)
    stub = _StubPlanner(["warranty", "booking"])
    orch = CapabilityOrchestrator(container=container, classifier=RuleBasedClassifier(),
                                  llm_planner=stub)
    plan = orch.route("보증으로 무상 수리 되는지랑 기사 방문 예약도 가능한가요")
    assert plan.capabilities == ["warranty", "booking"]


def test_route_preserves_explicit_action_with_planner(container):
    stub = _StubPlanner(["diagnose"])
    orch = CapabilityOrchestrator(container=container, classifier=RuleBasedClassifier(),
                                  llm_planner=stub)
    # LLM 조언형(diagnose) + 규칙 행동형(order) 병합
    plan = orch.route("보증 되는지랑 가격 알려주고 배수필터 주문해줘")
    assert "diagnose" in plan.capabilities and "order" in plan.capabilities
    assert plan.capabilities.index("diagnose") < plan.capabilities.index("order")  # 우선순위


def test_route_falls_back_to_rule_without_planner(container):
    # LLM 플래너 미연결 → 규칙 plan으로 폴백(오프라인·테스트 결정성)
    plan = _orch(container).route("세탁기 물이 안 빠져요")
    assert "diagnose" in plan.capabilities


def test_route_planner_failure_falls_back(container):
    class _Boom:
        def propose(self, *a, **k):
            raise RuntimeError("planner down")

    orch = CapabilityOrchestrator(container=container, classifier=RuleBasedClassifier(),
                                  llm_planner=_Boom())
    plan = orch.route("산 지 얼마 안 됐는데 보증으로 무상 수리되는지랑 예약 가능한지 알려줘")
    assert isinstance(plan.capabilities, list)   # 예외 없이 규칙 폴백


# ── 견고성: per-capability 폴백 + 빈 턴 금지(§13.1·R7·F4) ───────────────────
def test_per_capability_failure_isolated(container):
    # 한 capability가 예외를 던져도 나머지는 살고, 실패분은 unhandled 섹션으로 표면화
    orch = _orch(container)
    def _boom(ctx, msg):
        raise RuntimeError("handler down")
    orch.registry["diagnose"] = orch.registry["diagnose"].__class__(
        "diagnose", "advisory", "tool", ("troubleshoot",), _boom, priority=1)
    secs = orch.build_turn("세탁기 물 안 빠져요 배수필터 주문해줘").sections
    diag = [s for s in secs if s.intent == "diagnose"]
    order = [s for s in secs if s.intent == "order"]
    assert diag and diag[0].handled is False              # 실패 step만 폴백
    assert order and order[0].handled is True             # 나머지는 정상


def test_empty_plan_falls_back_to_clarify(container):
    orch = _orch(container)
    ctx = _ctx(container)
    secs = orch._run_capabilities(Plan([]), ctx, "음...", {})
    assert secs and secs[0].intent == "clarify"           # 빈 턴 금지 — 되묻기


# ── 봉투 패리티(요구사항 13) ────────────────────────────────────────────────
def test_stream_emits_section_flow_done(container):
    chunks = list(_orch(container).stream_turn("세탁기 물이 안 빠져요"))
    types = [c["type"] for c in chunks]
    assert "section" in types and types[-1] == "done"
    assert any(c["type"] == "flow" for c in chunks)
