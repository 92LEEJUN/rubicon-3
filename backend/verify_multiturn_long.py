"""장문(3~4줄) 멀티턴 검증 — 규칙 분류기의 한계를 실측한다.

짧은 한 문장이 아니라 실제 사용자가 쓰는 장황한 발화로 CapabilityOrchestrator를 구동해,
의도 분류·부품 해석·복합 과트리거·크로스턴 carry가 어떻게 동작하는지(또는 깨지는지) 출력한다.
사용: cd backend && python verify_multiturn_long.py
"""
from app.container import build_container
from app.orchestrator.capability import CapabilityOrchestrator
from app.orchestrator.classify import RuleBasedClassifier


def show(orch, sid, text):
    intents = orch.classifier.classify(text)
    plan = orch.plan(text)
    turn = orch.build_turn(text, session_id=sid)
    oneline = " ".join(text.split())
    print(f"  👤 {oneline[:90]}{'…' if len(oneline) > 90 else ''}")
    print(f"     분류 intents={intents.intents} compound={intents.is_compound} → plan={plan.capabilities}")
    for s in turn.sections:
        flag = "" if s.handled else " [unhandled]"
        item = s.template.data.get("id") or s.template.data.get("part_id") or ""
        ctas = [c.kind for c in s.ctas]
        note = " ⚠️설명" if s.template.data.get("cta_notice") else ""
        print(f"     🤖 {s.intent:13} kind={s.template.kind:18} {item:18} CTA={ctas}{flag}{note}")
    print()


def header(t):
    print("=" * 80); print(t); print("=" * 80)


def main():
    header("대화 A — 세탁기 고장: 장황한 증상 서술 → 비용 고민 → 부품 주문")
    o = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier())
    show(o, "A", "어제 저녁부터 세탁기를 돌리면 중간에 멈추면서 물이 안 빠지는 것 같아요. "
                 "안을 열어보니 물이 가득 차 있고 화면에 5C인가 하는 에러도 떴어요. "
                 "세제도 바꿔봤는데 똑같네요. 어떻게 해결하면 좋을까요?")
    show(o, "A", "음 그러면 제가 직접 하단 필터를 청소해봤는데도 계속 그러면 부품을 갈아야 하나요? "
                 "비용이 많이 들면 그냥 새로 살까 고민도 되는데, "
                 "일단 그 배수 필터라는 거 어떤 건지 한번 확인해서 가격이랑 같이 알려주세요.")
    show(o, "A", "네 그럼 아까 말씀하신 그 배수필터로 주문 넣어주세요. "
                 "집으로 배송되는 거 맞죠? 빠르면 좋겠어요.")

    header("대화 B — 인덕션 안전 위험: 무섭다는 장황한 서술 → 보증 여부 → 기사 예약")
    o = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier())
    show(o, "B", "주방에서 인덕션을 쓰는데 며칠 전부터 켜기만 하면 어디선가 타는 냄새가 나고 "
                 "가끔 탁탁 하는 소리도 같이 나요. 산 지 1년도 안 됐는데 이래도 되나 싶고 "
                 "솔직히 좀 무섭기도 해요. 그냥 계속 써도 괜찮은 건지 어떻게 해야 할지 해결법 알려주세요.")
    show(o, "B", "헐 그러면 일단 쓰지 말아야겠네요. 근데 산 지 얼마 안 됐으니까 "
                 "보증 같은 걸로 무상 수리가 되는 건지도 궁금하고, "
                 "기사님이 직접 오셔서 봐주시는 게 나을 것 같은데 예약도 가능한가요?")

    header("대화 C — 공기청정기 추천: 장황한 상황 서술 → 비교/상태 확인 복합")
    o = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier())
    show(o, "C", "이번에 새 아파트로 이사를 가는데 거실이 한 60제곱미터 정도 돼요. "
                 "아이가 비염이 좀 있어서 공기청정기를 새로 하나 장만하려고 하는데, "
                 "너무 시끄럽지 않고 관리도 편한 걸로 추천해줄 수 있을까요? 예산은 크게 상관없어요.")
    show(o, "C", "오 비스포크 큐브 그거 괜찮아 보이는데 필터 교체나 소음이 어느 정도인지 더 알려주고, "
                 "겸사겸사 지금 우리 집 공기청정기 상태도 어떤지 같이 확인해줄 수 있어요? "
                 "그리고 헤파 필터도 슬슬 갈 때 됐으면 그것도 같이 주문해주세요.")

    header("대화 D — 복합 폭탄: 한 발화에 진단+주문+추천+무관 질의 뒤섞기")
    o = CapabilityOrchestrator(container=build_container(), classifier=RuleBasedClassifier())
    show(o, "D", "주말에 집 정리하면서 몰아서 여쭤볼게요. 세탁기 물 안 빠지는 거 해결법 알려주고, "
                 "냉장고 정수필터랑 공기청정기 헤파 필터는 떨어졌으니 주문도 해주고, "
                 "거실용 새 공기청정기도 하나 추천해주세요. 아 그리고 이번 주말 날씨도 알려주면 좋고요.")


if __name__ == "__main__":
    main()
