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


DISPATCH = {
    "device_status": handle_device_status,
    "troubleshoot": handle_troubleshoot,
    "order": handle_order,
    "recommend": handle_recommend,
    "general": handle_general,
}
