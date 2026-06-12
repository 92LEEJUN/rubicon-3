"""실 LLM 플래너 검증 — 에스컬레이션 턴에서 규칙 vs LLM plan을 실제 호출로 비교.

규칙 분류기가 오분류하던 F1·F2 장문을 실 LLM(gpt-4o-mini)이 어떻게 교정하는지 실측한다.
**실 LLM 호출**이 필요(OPENAI_API_KEY). pytest 아님 — 결정적 테스트는 stub로 별도.
사용: cd backend && LLM_BACKED=1 python verify_llm_planner.py
"""
from app.container import build_container
from app.orchestrator.capability import CapabilityOrchestrator
from app.orchestrator.classify import RuleBasedClassifier
from app.orchestrator.planner import LLMPlanner

# (라벨, 메시지) — F1·F2 장문 + 깨끗한 케이스(홉0 확인)
CORPUS = [
    ("A-T2(F1 확인해/가격)",
     "음 그러면 직접 하단 필터를 청소해봤는데도 계속 그러면 부품을 갈아야 하나요? "
     "비용이 많이 들면 그냥 새로 살까 고민도 되는데, 일단 그 배수 필터라는 거 어떤 건지 "
     "한번 확인해서 가격이랑 같이 알려주세요."),
    ("B-T2(F2 보증/예약)",
     "산 지 얼마 안 됐으니까 보증 같은 걸로 무상 수리가 되는 건지도 궁금하고, "
     "기사님이 직접 오셔서 봐주시는 게 나을 것 같은데 예약도 가능한가요?"),
    ("C-T2(F2 설명/비교+주문)",
     "비스포크 큐브 그거 필터 교체나 소음이 어느 정도인지 더 알려주고, "
     "지금 우리 집 공기청정기 상태도 어떤지 같이 확인해주고, 헤파 필터도 같이 주문해주세요."),
    ("warranty 단독", "이 냉장고 아직 보증 되나요? 무상으로 고칠 수 있어요?"),
    ("clarify(모호)", "이거 좀 어떻게 해줘"),
    ("clean 단일", "세탁기에서 물이 안 빠져요"),
    ("clean 복합 J5",
     "세탁기 물 안 빠지는 거 해결법 알려주고, 냉장고 정수필터랑 공기청정기 HEPA 필터도 주문해줘"),
]


def main():
    rule_only = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier())
    llm = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier(),
                                 llm_planner=LLMPlanner())
    for label, msg in CORPUS:
        rule_plan = rule_only.plan(msg).capabilities
        routed = llm.route(msg).capabilities   # 모든 질의 LLM 라우팅(ADR-0048)
        print("─" * 78)
        print(f"[{label}]")
        print(f"  규칙폴백 plan : {rule_plan}")
        print(f"  LLM    plan : {routed}" + ("   ← 교정" if routed != rule_plan else "   (동일)"))
        # 실제 산출 섹션
        turn = llm.build_turn(msg, session_id=label)
        for s in turn.sections:
            flag = "" if s.handled else " [unhandled]"
            note = " ⚠️" if s.template.data.get("cta_notice") else ""
            print(f"     🤖 {s.intent:13} {s.template.kind:18} CTA={[c.kind for c in s.ctas]}{flag}{note}")
    print("─" * 78)


if __name__ == "__main__":
    main()
