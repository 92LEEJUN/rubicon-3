"""장문 멀티턴 코퍼스 회귀 — `specs/capability-orchestrator/test-set.md` §2를 자동 단언.

`verify_multiturn_long.py`(수동 하니스)의 대화 A~D를 결정적(규칙 폴백)으로 고정하고,
LLM 라우팅 교정분은 stub 플래너로 병합만 검증한다(실 네트워크 없음, 요구사항 15).
발화를 바꾸면 하니스와 본 파일을 함께 갱신한다(test-set.md 갱신 규칙).
"""
from app.orchestrator.capability import CapabilityOrchestrator, Plan
from app.orchestrator.classify import RuleBasedClassifier

# ── 코퍼스(verify_multiturn_long.py와 동일 발화) ────────────────────────────
A_T1 = ("어제 저녁부터 세탁기를 돌리면 중간에 멈추면서 물이 안 빠지는 것 같아요. "
        "안을 열어보니 물이 가득 차 있고 화면에 5C인가 하는 에러도 떴어요. "
        "세제도 바꿔봤는데 똑같네요. 어떻게 해결하면 좋을까요?")
A_T2 = ("음 그러면 제가 직접 하단 필터를 청소해봤는데도 계속 그러면 부품을 갈아야 하나요? "
        "비용이 많이 들면 그냥 새로 살까 고민도 되는데, "
        "일단 그 배수 필터라는 거 어떤 건지 한번 확인해서 가격이랑 같이 알려주세요.")
A_T3 = ("네 그럼 아까 말씀하신 그 배수필터로 주문 넣어주세요. 집으로 배송되는 거 맞죠? 빠르면 좋겠어요.")
B_T1 = ("주방에서 인덕션을 쓰는데 며칠 전부터 켜기만 하면 어디선가 타는 냄새가 나고 "
        "가끔 탁탁 하는 소리도 같이 나요. 산 지 1년도 안 됐는데 이래도 되나 싶고 "
        "솔직히 좀 무섭기도 해요. 그냥 계속 써도 괜찮은 건지 어떻게 해야 할지 해결법 알려주세요.")
B_T2 = ("헐 그러면 일단 쓰지 말아야겠네요. 근데 산 지 얼마 안 됐으니까 보증 같은 걸로 무상 수리가 "
        "되는 건지도 궁금하고, 기사님이 직접 오셔서 봐주시는 게 나을 것 같은데 예약도 가능한가요?")
C_T1 = ("이번에 새 아파트로 이사를 가는데 거실이 한 60제곱미터 정도 돼요. "
        "아이가 비염이 좀 있어서 공기청정기를 새로 하나 장만하려고 하는데, "
        "너무 시끄럽지 않고 관리도 편한 걸로 추천해줄 수 있을까요? 예산은 크게 상관없어요.")
C_T2 = ("오 비스포크 큐브 그거 괜찮아 보이는데 필터 교체나 소음이 어느 정도인지 더 알려주고, "
        "겸사겸사 지금 우리 집 공기청정기 상태도 어떤지 같이 확인해줄 수 있어요? "
        "그리고 헤파 필터도 슬슬 갈 때 됐으면 그것도 같이 주문해주세요.")
D = ("주말에 집 정리하면서 몰아서 여쭤볼게요. 세탁기 물 안 빠지는 거 해결법 알려주고, "
     "냉장고 정수필터랑 공기청정기 헤파 필터는 떨어졌으니 주문도 해주고, "
     "거실용 새 공기청정기도 하나 추천해주세요. 아 그리고 이번 주말 날씨도 알려주면 좋고요.")


def _orch(container, planner=None):
    return CapabilityOrchestrator(container=container, classifier=RuleBasedClassifier(),
                                  llm_planner=planner)


def _by_intent(sections, intent):
    return [s for s in sections if s.intent == intent]


class _Stub:
    """고정 plan을 내는 결정적 stub 플래너(LLM 라우팅 대역)."""
    def __init__(self, caps):
        self.caps = caps

    def propose(self, catalog, message):
        return Plan(capabilities=list(self.caps))


# ── 대화 A — 진단 → (F1 트랩) → 부품 주문 ───────────────────────────────────
def test_dialog_a_diagnose_then_order(container):
    orch = _orch(container)
    t1 = orch.build_turn(A_T1, session_id="A").sections
    g = _by_intent(t1, "troubleshoot")
    assert g and g[0].template.kind == "guide_steps"
    assert g[0].template.data["required_parts"] == ["part_drain_filter"]

    # A-T2: 규칙폴백은 '확인해'로 device_status 트랩 → unhandled (F1, test-set §3)
    t2 = orch.build_turn(A_T2, session_id="A").sections
    ds = _by_intent(t2, "device_status")
    assert ds and ds[0].handled is False

    # A-T3: 배수필터 직접 해석 → product_card
    t3 = orch.build_turn(A_T3, session_id="A").sections
    o = _by_intent(t3, "order")
    assert o and o[0].template.kind == "product_card"
    assert o[0].template.data["id"] == "part_drain_filter" and o[0].handled is True


# ── 대화 B — 안전 위험 게이팅(F3) ───────────────────────────────────────────
def test_dialog_b_danger_gating(container):
    sec = _by_intent(_orch(container).build_turn(B_T1, session_id="B").sections, "troubleshoot")[0]
    assert sec.template.data.get("cta_notice")              # 안전 경고 설명
    kinds = [c.kind for c in sec.ctas]
    assert "order" not in kinds                             # 부품 자가주문 CTA 숨김
    assert "handoff" in kinds and "booking" in kinds        # 상담원·기사 경로


# ── 대화 C — 추천 → 후속 복합(상태+주문) ────────────────────────────────────
def test_dialog_c_recommend_then_complex(container):
    orch = _orch(container)
    t1 = _by_intent(orch.build_turn(C_T1, session_id="C").sections, "recommend")[0]
    assert t1.template.kind == "recommendation_list"
    assert any(p["id"] == "prod_purifier_cube" for p in t1.template.data["products"])

    t2 = orch.build_turn(C_T2, session_id="C").sections
    assert _by_intent(t2, "device_status")                 # 상태 확인
    hepa = _by_intent(t2, "order")
    assert hepa and hepa[0].handled is False               # 헤파 품절 → unhandled


# ── 대화 D — 복합 폭탄 fan-out ──────────────────────────────────────────────
def test_dialog_d_fanout_handled_unhandled(container):
    secs = _orch(container).build_turn(D, session_id="D").sections
    assert _by_intent(secs, "troubleshoot") and _by_intent(secs, "recommend")
    orders = {(s.template.data.get("id") or s.template.data.get("part_id")): s
              for s in _by_intent(secs, "order")}
    assert orders["part_water_filter"].handled is True      # 재고 → product_card
    assert orders["part_water_filter"].template.kind == "product_card"
    assert orders["part_hepa"].handled is False             # 품절 → unhandled


# ── LLM 라우팅 교정(stub 병합) — F2 해소 입증 ───────────────────────────────
def test_llm_routes_b_t2_to_warranty_booking(container):
    orch = _orch(container, planner=_Stub(["warranty", "booking"]))
    plan = orch.route(B_T2)
    assert plan.capabilities == ["warranty", "booking"]
    secs = orch.build_turn(B_T2, session_id="B").sections
    assert _by_intent(secs, "warranty")
    bk = _by_intent(secs, "booking")
    assert bk and bk[0].template.kind == "booking"


def test_llm_explain_uses_carried_candidates(container):
    orch = _orch(container, planner=_Stub(["explain"]))
    orch.build_turn(C_T1, session_id="C")                  # 추천 → candidates 적재(carry)
    secs = orch.build_turn(C_T2, session_id="C").sections
    ex = _by_intent(secs, "explain")
    assert ex and ex[0].template.kind == "recommendation_list"
    assert any(p["id"] == "prod_purifier_cube" for p in ex[0].template.data["products"])


def test_explicit_order_preserved_under_llm(container):
    # C-T2: LLM 조언형(explain) + 규칙 명시 order 병합, 우선순위 정렬(test-set §1)
    orch = _orch(container, planner=_Stub(["device_status", "explain"]))
    plan = orch.route(C_T2)
    assert "explain" in plan.capabilities and "order" in plan.capabilities
    assert plan.capabilities.index("explain") < plan.capabilities.index("order")
