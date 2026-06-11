/**
 * 데모/스크린샷/테스트용 섹션 fixtures — BE 오케스트레이터 출력과 동형(api-contract §2.1).
 * 실제 앱은 BFF WS에서 같은 형태의 청크를 받는다(여기선 정적 재생).
 */
import type { MessageSection, Template } from "../types/contract";

export const homeSummary: Template = {
  kind: "home_summary",
  data: {
    user: "홍길동",
    devices: [
      { id: "dev_washer_01", type: "washer", model: "WF45T6000AW", status: "UNHEALTHY",
        consumables: [{ name: "drain_filter", life_remaining: 0.4, threshold: 0.2 }] },
      { id: "dev_fridge_01", type: "refrigerator", model: "RF28R7351SR", status: "ONLINE",
        consumables: [{ name: "water_filter", life_remaining: 0.15, threshold: 0.2 }] },
      { id: "dev_purifier_01", type: "air_purifier", model: "AX47T9080WD", status: "ONLINE",
        consumables: [{ name: "hepa_filter", life_remaining: 0.12, threshold: 0.15 }] },
    ],
    alerts: [
      { id: "alert_fridge", device_id: "dev_fridge_01", type: "consumable", severity: "warning",
        detail: "정수필터 수명 15% 남음(임계치 20%)." },
      { id: "alert_purifier", device_id: "dev_purifier_01", type: "consumable", severity: "info",
        detail: "HEPA 필터 교체 시기가 임박했습니다." },
    ],
  },
};

// J1: 세탁기 5C → 해결 가이드 → 배수필터 주문 (복합 섹션)
export const j1Sections: MessageSection[] = [
  {
    label: "기기 상태", intent: "device_status", handled: true, ctas: [],
    template: { kind: "device_status", data: {
      device: { id: "dev_washer_01", type: "washer", model: "WF45T6000AW", status: "UNHEALTHY" },
      anomalies: [{ id: "ano_washer_5c", type: "error_code", severity: "warning",
        detail: "5C — 배수가 원활하지 않습니다." }],
    } },
  },
  {
    label: "해결 가이드", intent: "troubleshoot", handled: true,
    template: { kind: "guide_steps", data: {
      solution_id: "sol_washer_5c", coverage: "unknown", required_parts: ["part_drain_filter"],
      steps: [
        { order: 1, instruction: "배수 호스가 꺾이거나 눌리지 않았는지 확인하세요.", safety: "none" },
        { order: 2, instruction: "전원을 끄고 하단 배수 필터를 분리해 이물질을 청소하세요.", safety: "caution" },
        { order: 3, instruction: "배수 호스를 배수구에 15~20cm 깊이로 정리해 다시 연결하세요.", safety: "none" },
      ],
      sources: [{ title: "삼성 세탁기 4C/5C 오류 해결", ref: "https://www.samsung.com/us/support/troubleshoot/TSG10000997/", confidence: 0.9 }],
    } },
    ctas: [{ label: "주문하기", action: "commit", kind: "order", payload: { part_ids: ["part_drain_filter"] } }],
  },
  {
    label: "부품 주문", intent: "order", handled: true,
    template: { kind: "product_card", data: {
      id: "part_drain_filter", name: "세탁기 배수 필터", sku: "DC97-16513A", price: 12000, in_stock: true } },
    ctas: [{ label: "주문하기", action: "commit", kind: "order", payload: { part_ids: ["part_drain_filter"] } }],
  },
];

// J5: 복합 — HEPA 품절 미처리 섹션
export const j5UnhandledHepa: MessageSection = {
  label: "부품 주문", intent: "order", handled: false,
  template: { kind: "text", data: {
    message: "'공기청정기 HEPA 교체 필터'은(는) 현재 품절입니다. 입고 알림을 신청하거나 대체 제품을 안내해 드릴게요.",
    part_id: "part_hepa" } },
  ctas: [
    { label: "입고 알림", action: "chat", kind: "restock_alert", payload: { part_id: "part_hepa" } },
    { label: "대체 추천", action: "chat", kind: "recommend" },
  ],
};

export const recommendation: MessageSection = {
  label: "추천", intent: "recommend", handled: true,
  template: { kind: "recommendation_list", data: {
    products: [{ id: "prod_purifier_cube", category: "air_purifier", name: "비스포크 큐브 에어 공기청정기",
      model: "AX9500", price: 599000, specs: { coverage: "60㎡", noise: "22dB" }, in_stock: true }] } },
  ctas: [{ label: "자세히", action: "chat", kind: "explain" }],
};

export const confirmation: Template = {
  kind: "confirmation",
  data: {
    order: { id: "ord_0001", status: "DRAFT", items: [{ part_id: "part_drain_filter", name: "세탁기 배수 필터", unit_price: 12000, qty: 1 }] },
    summary: { subtotal: 12000, shipping_fee: 3000, tax: 0, discount: 0, total: 15000 },
  },
};
