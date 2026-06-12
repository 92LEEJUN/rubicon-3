"""의도별 핸들러 — 서비스 결과를 근거로 MessageSection을 만든다(환각 억제).

각 핸들러는 도메인 서비스만 호출하고, 결과를 response-templates kind로 구조화한다.
복합 응답(R7)은 핸들러가 만든 섹션들을 우선순위 순서로 묶는다(core.py).
"""
from __future__ import annotations

from ..container import Container
from ..domain import Cta, MessageSection, Template, User

# 의도 라벨(FE 표시용)
LABELS = {
    "device_status": "기기 상태",
    "troubleshoot": "해결 가이드",
    "order": "부품 주문",
    "recommend": "추천",
    "general": "안내",
    "warranty": "보증 안내",
    "booking": "방문 예약",
    "explain": "상세 설명",
    "clarify": "확인",
}

# 부품 키워드 → id(데모용 엔티티 해석; 실 전환 시 NER/LLM)
_PART_KEYWORDS = {
    "part_drain_filter": ("배수", "drain"),
    "part_water_filter": ("정수", "냉장"),
    "part_hepa": ("hepa", "헤파", "공기청정"),
}


def resolve_part_ids(message: str) -> list[str]:
    t = (message or "").lower()
    return [pid for pid, kws in _PART_KEYWORDS.items() if any(k in t for k in kws)]


def _order_cta(part_ids: list[str]) -> Cta:
    # 첫 탭은 확인 게이트(R17)로 — 결정적 엔드포인트(commit)
    return Cta(label="주문하기", action="commit", kind="order", payload={"part_ids": part_ids})


def handle_device_status(c: Container, user: User, message: str) -> list[MessageSection]:
    res = c.device.get_status(message)
    if not res.found:
        return [MessageSection(
            label=LABELS["device_status"], intent="device_status",
            template=Template(kind="text", data={"message": res.message or "기기를 찾지 못했습니다."}),
            handled=False)]
    return [MessageSection(
        label=LABELS["device_status"], intent="device_status",
        template=Template(kind="device_status", data={
            "device": res.device.model_dump(mode="json"),
            "anomalies": [a.model_dump(mode="json") for a in res.anomalies],
        }))]


def handle_troubleshoot(c: Container, user: User, message: str) -> list[MessageSection]:
    status = c.device.get_status(message)
    sol = c.knowledge.best_solution(message)
    if sol is None:
        return [MessageSection(
            label=LABELS["troubleshoot"], intent="troubleshoot",
            template=Template(kind="text", data={"message": "관련 해결 가이드를 찾지 못했습니다. 방문 상담을 도와드릴까요?"}),
            ctas=[Cta(label="상담 연결", action="chat", kind="handoff")],
            handled=False)]
    ctas: list[Cta] = []
    if sol.required_parts:
        ctas.append(_order_cta(sol.required_parts))
    if sol.escalation_needed:
        ctas.append(Cta(label="방문 예약", action="chat", kind="handoff"))
    return [MessageSection(
        label=LABELS["troubleshoot"], intent="troubleshoot",
        template=Template(kind="guide_steps", data={
            "solution_id": sol.id,
            "device": status.device.model_dump(mode="json") if status.device else None,
            "steps": [s.model_dump(mode="json") for s in sol.steps],
            "sources": [s.model_dump(mode="json") for s in sol.sources],
            "coverage": sol.coverage,
            "required_parts": sol.required_parts,
        }),
        ctas=ctas)]


def handle_order(c: Container, user: User, message: str,
                 part_ids: list[str] | None = None) -> list[MessageSection]:
    ids = part_ids or resolve_part_ids(message)
    if not ids:
        return [MessageSection(
            label=LABELS["order"], intent="order",
            template=Template(kind="text", data={"message": "주문할 부품을 찾지 못했습니다. 어떤 부품이 필요하신가요?"}),
            handled=False)]
    sections: list[MessageSection] = []
    match = c.catalog.match_parts(part_ids=ids)
    found = {p.id: p for p in match.parts}
    for pid in ids:
        part = found.get(pid)
        if part is None:
            continue
        if part.in_stock:
            sections.append(MessageSection(
                label=LABELS["order"], intent="order",
                template=Template(kind="product_card", data=part.model_dump(mode="json")),
                ctas=[_order_cta([part.id])]))
        else:  # 품절 → 미처리(R13): 입고 알림/대체 안내
            sections.append(MessageSection(
                label=LABELS["order"], intent="order",
                template=Template(kind="text", data={
                    "message": f"'{part.name}'은(는) 현재 품절입니다. 입고 알림을 신청하거나 대체 제품을 안내해 드릴게요.",
                    "part_id": part.id}),
                ctas=[Cta(label="입고 알림", action="chat", kind="restock_alert", payload={"part_id": part.id}),
                      Cta(label="대체 추천", action="chat", kind="recommend")],
                handled=False))
    return sections


def handle_recommend(c: Container, user: User, message: str) -> list[MessageSection]:
    items = c.recommendation.recommend(user)   # 추천 코어(근거·동의차등·보유제외)
    if not items:
        return [MessageSection(
            label=LABELS["recommend"], intent="recommend",
            template=Template(kind="text", data={"message": "지금은 추천드릴 제품이 없습니다."}),
            handled=False)]
    personalized = items[0].personalized
    return [MessageSection(
        label=LABELS["recommend"], intent="recommend",
        template=Template(kind="recommendation_list", data={
            # 각 제품에 추천 근거(reason) 부착, 개인화 여부 표시(일반 폴백 고지)
            "products": [{**it.product.model_dump(mode="json"), "reason": it.reason} for it in items],
            "personalized": personalized}),
        ctas=[Cta(label="왜 추천?", action="chat", kind="explain"),
              Cta(label="비교", action="chat", kind="compare")])]


def handle_general(c: Container, user: User, message: str) -> list[MessageSection]:
    return [MessageSection(
        label=LABELS["general"], intent="general",
        template=Template(kind="text", data={
            "message": "가전 상태 점검·문제 해결·부품 주문을 도와드릴 수 있어요. 무엇을 도와드릴까요?"}))]


def handle_warranty(c: Container, user: User, message: str) -> list[MessageSection]:
    """보증(유·무상) 안내 — 해결책 coverage 기반(R22). 무상이면 보증 수리 접수로 안내."""
    sol = c.knowledge.best_solution(message)
    coverage = sol.coverage if sol else "unknown"
    if coverage == "free":
        msg = "확인해 보니 보증 기간 내 무상 수리 대상으로 보여요. 비용 없이 점검·수리를 받으실 수 있어요."
        ctas = [Cta(label="보증 수리 접수", action="chat", kind="booking", payload={"visit_type": "REPAIR"}),
                Cta(label="상담원 연결", action="chat", kind="handoff")]
    elif coverage == "paid":
        msg = "보증 범위 밖(유상)일 수 있어요. 정확한 비용은 상담원이 확인해 드릴게요."
        ctas = [Cta(label="상담원 연결", action="chat", kind="handoff")]
    else:
        msg = "보증 여부는 모델·구매 정보로 확인이 필요해요. 상담원이 정확히 안내해 드릴게요."
        ctas = [Cta(label="상담원 연결", action="chat", kind="handoff")]
    return [MessageSection(
        label=LABELS["warranty"], intent="warranty",
        template=Template(kind="text", data={"message": msg, "coverage": coverage}),
        ctas=ctas)]


def handle_booking(c: Container, user: User, message: str) -> list[MessageSection]:
    """방문 예약 — 가능 슬롯을 초안으로 제시(R18). 커밋은 ActionGate(확정 CTA)."""
    slots = c.handoff.list_slots("REPAIR")
    ctas = [Cta(label="이 시간 예약", action="commit", kind="booking", payload={"slot_id": s.id})
            for s in slots[:3]]
    if not ctas:
        ctas = [Cta(label="상담원 연결", action="chat", kind="handoff")]
    return [MessageSection(
        label=LABELS["booking"], intent="booking",
        template=Template(kind="booking", data={
            "visit_type": "REPAIR",
            "slots": [s.model_dump(mode="json") for s in slots]}),
        ctas=ctas)]


def handle_explain(c: Container, user: User, message: str,
                   candidates: list[str] | None = None) -> list[MessageSection]:
    """제품/추천 상세 설명·비교 — 직전 추천 후보(blackboard)나 개인화 추천의 스펙·근거를 제시."""
    items = c.recommendation.recommend(user)
    cand = set(candidates or [])
    chosen = [it for it in items if (not cand or it.product.id in cand)]
    if not chosen:
        return [MessageSection(
            label=LABELS["explain"], intent="explain",
            template=Template(kind="text", data={
                "message": "어떤 제품·부품을 더 알려드릴까요? 모델명이나 알고 싶은 점(소음·가격·필터 등)을 알려주세요."}),
            handled=False)]
    return [MessageSection(
        label=LABELS["explain"], intent="explain",
        template=Template(kind="recommendation_list", data={
            "products": [{**it.product.model_dump(mode="json"), "reason": it.reason} for it in chosen],
            "personalized": chosen[0].personalized,
            "detail": True}),
        ctas=[Cta(label="장바구니", action="commit", kind="order",
                  payload={"product_ids": [it.product.id for it in chosen]})])]


def handle_clarify(c: Container, user: User, message: str) -> list[MessageSection]:
    """모호·범위 불명확 — 되묻기(어느 기기·어떤 증상). 보유 기기를 빠른 선택지로 제시."""
    devices = c.device.list_devices()
    return [MessageSection(
        label=LABELS["clarify"], intent="clarify",
        template=Template(kind="text", data={
            "message": "어떤 기기의 어떤 점이 궁금하신지 알려주시면 정확히 도와드릴게요."}),
        ctas=[Cta(label=d.type, action="chat", kind="select_device", payload={"device_id": d.id})
              for d in devices[:3]])]


DISPATCH = {
    "device_status": handle_device_status,
    "troubleshoot": handle_troubleshoot,
    "order": handle_order,
    "recommend": handle_recommend,
    "general": handle_general,
}
