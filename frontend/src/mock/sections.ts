/** Mock capability section 빌더(ADR-0051) — BE handlers/게이팅을 미러해 MessageSection 생성.
 *  문서(backend-architecture §3 흐름·게이팅, response-templates)를 따른다. */
import type { Cta, MessageSection } from "../types/contract";
import { DEVICES, PARTS, PRODUCTS, SLOTS, SOLUTIONS } from "../fixtures/mockData";
import { mockStore } from "./store";

const DANGER = /타는 냄새|탄내|스파크|연기|감전|가스|불꽃|누전|폭발|화재/;

const ctaAgent: Cta = { label: "상담원 연결", action: "chat", kind: "handoff" };
const ctaVisit: Cta = { label: "수리기사 방문", action: "chat", kind: "booking", payload: { visit_type: "REPAIR" } };
const orderCta = (ids: string[]): Cta => ({ label: "주문하기", action: "commit", kind: "order", payload: { part_ids: ids } });

/** 진단(troubleshoot) — guide_steps + 안전/보증 게이팅. */
export function buildDiagnose(text: string): MessageSection[] {
  const danger = DANGER.test(text);
  const hit = SOLUTIONS.find((s) => s.match.test(text));
  // 위험 발화(해결책 없거나 danger) → 안전 경고, 부품 CTA 숨김
  if (danger || hit?.solution.danger) {
    return [{
      label: "해결 가이드", intent: "troubleshoot", handled: true,
      template: { kind: "text", data: {
        cta_notice: "말씀하신 증상은 안전 위험이 있을 수 있어요. 사용을 멈추고 전원(또는 가스)을 차단한 뒤, 직접 손대기보다 상담원·수리기사 방문으로 점검받으시길 권해요.",
        message: "안전을 위해 직접 수리보다 전문 점검을 권장합니다." } },
      ctas: [ctaAgent, ctaVisit],
    }];
  }
  const sol = hit?.solution ?? SOLUTIONS[0].solution;
  const inWarranty = sol.coverage === "free";
  const ctas: Cta[] = [];
  if (sol.required_parts.length && !inWarranty) ctas.push(orderCta(sol.required_parts));
  ctas.push(ctaAgent, ctaVisit);
  const data: Record<string, any> = {
    solution_id: "sol_mock", coverage: sol.coverage, required_parts: sol.required_parts,
    steps: sol.steps, sources: sol.sources ?? [],
  };
  if (inWarranty) data.cta_notice = "보증 기간 내 무상 수리 대상이에요. 부품을 직접 구매하기보다 보증 수리(상담원·방문)를 이용하시는 걸 권해요.";
  return [{ label: "해결 가이드", intent: "troubleshoot", handled: true, template: { kind: "guide_steps", data }, ctas }];
}

function resolvePartIds(text: string): string[] {
  const ids: string[] = [];
  if (/배수|세탁/.test(text)) ids.push("part_drain_filter");
  if (/정수|냉장고/.test(text)) ids.push("part_water_filter");
  if (/헤파|hepa|공기/i.test(text)) ids.push("part_hepa");
  return ids.length ? ids : ["part_drain_filter"];
}

/** 주문 — 재고 product_card / 품절 unhandled. */
export function buildOrder(text: string): MessageSection[] {
  return resolvePartIds(text).map((pid) => {
    const part = PARTS[pid];
    if (part?.in_stock) {
      return {
        label: "부품 주문", intent: "order", handled: true,
        template: { kind: "product_card", data: { ...part } },
        ctas: [orderCta([pid])],
      } as MessageSection;
    }
    return {
      label: "부품 주문", intent: "order", handled: false,
      template: { kind: "text", data: { message: `'${part?.name ?? pid}'은(는) 현재 품절입니다. 입고 알림을 신청하거나 대체 제품을 안내해 드릴게요.`, part_id: pid } },
      ctas: [{ label: "입고 알림", action: "chat", kind: "restock_alert", payload: { part_id: pid } }, { label: "대체 추천", action: "chat", kind: "recommend" }],
    } as MessageSection;
  });
}

/** 추천 — recommendation_list(+candidates 기록). */
export function buildRecommend(): MessageSection[] {
  mockStore.setCandidates(PRODUCTS.map((p) => p.id));
  return [{
    label: "추천", intent: "recommend", handled: true,
    template: { kind: "recommendation_list", data: { products: PRODUCTS, personalized: true } },
    ctas: [{ label: "자세히", action: "chat", kind: "explain" }, { label: "비교", action: "chat", kind: "compare" }],
  }];
}

/** 보증 — text(무상/유상). */
export function buildWarranty(text: string): MessageSection[] {
  const free = /냉장고|정수/.test(text);   // mock: 정수필터 해결책 coverage=free
  const message = free
    ? "확인해 보니 보증 기간 내 무상 수리 대상으로 보여요. 비용 없이 점검·수리를 받으실 수 있어요."
    : "보증 여부는 모델·구매 정보로 확인이 필요해요. 상담원이 정확히 안내해 드릴게요.";
  const ctas: Cta[] = free
    ? [{ label: "보증 수리 접수", action: "chat", kind: "booking", payload: { visit_type: "REPAIR" } }, ctaAgent]
    : [ctaAgent];
  return [{ label: "보증 안내", intent: "warranty", handled: true, template: { kind: "text", data: { message, coverage: free ? "free" : "unknown" } }, ctas }];
}

/** 예약 — booking(슬롯) + 확정 CTA. */
export function buildBooking(): MessageSection[] {
  return [{
    label: "방문 예약", intent: "booking", handled: true,
    template: { kind: "booking", data: { visit_type: "REPAIR", slots: SLOTS } },
    ctas: SLOTS.slice(0, 3).map((s) => ({ label: `${s.start} 예약`, action: "commit", kind: "booking", payload: { slot_id: s.id } })),
  }];
}

/** 설명 — 직전 추천 후보(candidates) 상세. */
export function buildExplain(): MessageSection[] {
  const cand = new Set(mockStore.getCandidates());
  const chosen = cand.size ? PRODUCTS.filter((p) => cand.has(p.id)) : PRODUCTS;
  return [{
    label: "상세 설명", intent: "explain", handled: true,
    template: { kind: "recommendation_list", data: { products: chosen, detail: true, personalized: true } },
    ctas: [{ label: "장바구니", action: "commit", kind: "order", payload: { product_ids: chosen.map((p) => p.id) } }],
  }];
}

/** 모호 — 되묻기 + 기기 빠른 선택지. */
export function buildClarify(): MessageSection[] {
  return [{
    label: "확인", intent: "clarify", handled: true,
    template: { kind: "text", data: { message: "어떤 기기의 어떤 점이 궁금하신지 알려주시면 정확히 도와드릴게요." } },
    ctas: DEVICES.slice(0, 3).map((d) => ({ label: d.type, action: "chat", kind: "select_device", payload: { device_id: d.id } })),
  }];
}

export function buildGeneral(): MessageSection[] {
  return [{
    label: "안내", intent: "general", handled: true,
    template: { kind: "text", data: { message: "가전 상태 점검·문제 해결·부품 주문을 도와드릴 수 있어요. 무엇을 도와드릴까요?" } },
    ctas: [],
  }];
}
