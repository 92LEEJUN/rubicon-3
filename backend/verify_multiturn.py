"""멀티턴 검증 하니스 — CapabilityOrchestrator(ADR-0046)를 실제 Mock 데이터로 구동.

각 시나리오를 턴 단위로 흘려보내고 실제 산출(섹션 종류·CTA·게이팅 설명)을 요약 출력한다.
사용: cd backend && python verify_multiturn.py
"""
from app.container import build_container
from app.domain import Solution, SolutionStep
from app.orchestrator.capability import CapabilityOrchestrator
from app.orchestrator.classify import RuleBasedClassifier


def render_turn(orch, sid, user_text):
    turn = orch.build_turn(user_text, session_id=sid)
    print(f"  👤 {user_text}")
    if not turn.sections:
        print("     🤖 (빈 응답)")
    for s in turn.sections:
        flag = "" if s.handled else "  [unhandled]"
        print(f"     🤖 [{s.label}/{s.intent}] kind={s.template.kind}{flag}")
        notice = s.template.data.get("cta_notice")
        if notice:
            print(f"        💬 설명: {notice}")
        kind_id = s.template.data.get("id") or s.template.data.get("part_id")
        if kind_id:
            print(f"        item={kind_id}")
        if s.ctas:
            print(f"        CTA: {[f'{c.label}({c.kind})' for c in s.ctas]}")
    print(f"     flow={turn.active_flow}")
    print()


def main():
    print("=" * 74)
    print("시나리오 1 — 진단 → 무관 질의 → 크로스턴 부품 주문 (세션 carry)")
    print("=" * 74)
    o = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier())
    render_turn(o, "s1", "세탁기에서 물이 안 빠져요. 어떻게 해요?")
    render_turn(o, "s1", "아 그리고 오늘 비 와요?")
    render_turn(o, "s1", "아까 그 부품 주문해줘")

    print("=" * 74)
    print("시나리오 2 — 보증 무상 부품(냉장고 정수필터): 부품 CTA 숨김 + 설명")
    print("=" * 74)
    o = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier())
    render_turn(o, "s2", "냉장고 정수필터 문제 해결 방법 알려줘")

    print("=" * 74)
    print("시나리오 3 — 추천(반응형) → 복합(진단+주문)")
    print("=" * 74)
    o = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier())
    render_turn(o, "s3", "공기청정기 신제품 추천해줘")
    render_turn(o, "s3",
                "세탁기 물 안 빠지는 거 해결법 알려주고 냉장고 정수필터랑 공기청정기 HEPA 필터도 주문해줘")

    print("=" * 74)
    print("시나리오 4 — 안전 위험(danger, 합성 데이터): 부품 CTA 숨김 + 위험 설명")
    print("=" * 74)
    c = build_container()
    danger = Solution(
        id="sol_induction_danger", anomaly_id=None,
        steps=[SolutionStep(order=1, instruction="사용을 멈추고 전원을 차단하세요.", safety="danger")],
        required_parts=["part_drain_filter"], escalation_needed=True, coverage="unknown")
    c.knowledge.best_solution = lambda *a, **k: danger  # 합성 주입(픽스처엔 danger 없음)
    o = CapabilityOrchestrator(container=c, classifier=RuleBasedClassifier())
    render_turn(o, "s4", "인덕션에서 타는 냄새랑 소리가 나요. 고장인가요? 해결법 알려줘")

    print("=" * 74)
    print("시나리오 5 — 범위 밖/모호: 행동형 자동 라우팅 안 함")
    print("=" * 74)
    o = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier())
    print(f"  plan('주식 추천해줘') = {o.plan('주식 좀 알려줘').capabilities}")
    print(f"  plan('세탁기 이상해요') = {o.plan('세탁기 물이 안 빠져요').capabilities}  (order 없음)")
    print(f"  plan('배수필터 주문해줘') = {o.plan('배수필터 주문해줘').capabilities}  (명시 order 허용)")


if __name__ == "__main__":
    main()
