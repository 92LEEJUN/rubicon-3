/** Mock 데이터셋(ADR-0051) — BE fixtures/문서를 미러한 단일 출처. sections.ts/respond.ts가 사용. */

export const svgThumb = (bg: string) =>
  "data:image/svg+xml," +
  encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><rect width='64' height='64' rx='12' fill='${bg}'/><circle cx='32' cy='26' r='12' fill='white' opacity='0.9'/><rect x='16' y='42' width='32' height='8' rx='4' fill='white' opacity='0.7'/></svg>`);

export interface Part { id: string; name: string; sku: string; price: number; in_stock: boolean; image: string; }
export const PARTS: Record<string, Part> = {
  part_drain_filter: { id: "part_drain_filter", name: "세탁기 배수 필터", sku: "DC97-16513A", price: 12000, in_stock: true, image: svgThumb("#0381FE") },
  part_water_filter: { id: "part_water_filter", name: "냉장고 정수필터", sku: "HAF-QIN", price: 38000, in_stock: true, image: svgThumb("#16A6B6") },
  part_hepa: { id: "part_hepa", name: "공기청정기 HEPA 교체 필터", sku: "CFX-G100", price: 45000, in_stock: false, image: svgThumb("#8B5CF6") },
};

export interface Product { id: string; category: string; name: string; model: string; price: number; specs: Record<string, string>; in_stock: boolean; image: string; reason?: string; }
export const PRODUCTS: Product[] = [
  { id: "prod_purifier_cube", category: "air_purifier", name: "비스포크 큐브 에어 공기청정기", model: "AX9500", price: 599000, specs: { coverage: "60㎡", noise: "22dB", filter: "3중 HEPA" }, in_stock: true, image: svgThumb("#1FA463"), reason: "거실 면적·저소음 선호 추천" },
  { id: "prod_washer_bespoke", category: "washer", name: "비스포크 그랑데 AI 세탁기", model: "WF24B9600", price: 1490000, specs: { capacity: "24kg", noise: "저소음", ai: "AI 맞춤세탁" }, in_stock: true, image: svgThumb("#0257D8"), reason: "노후 세탁기 교체 후보" },
];

export const DEVICES = [
  { id: "dev_washer_01", type: "washer", model: "WF45T6000AW", status: "UNHEALTHY", consumables: [{ name: "drain_filter", life_remaining: 0.4, threshold: 0.2 }] },
  { id: "dev_fridge_01", type: "refrigerator", model: "RF28R7351SR", status: "ONLINE", consumables: [{ name: "water_filter", life_remaining: 0.15, threshold: 0.2 }] },
  { id: "dev_purifier_01", type: "air_purifier", model: "AX47T9080WD", status: "ONLINE", consumables: [{ name: "hepa_filter", life_remaining: 0.12, threshold: 0.15 }] },
  { id: "dev_induction_01", type: "induction", model: "NZ63T8708EK", status: "ONLINE", consumables: [] },
];

export interface Solution {
  steps: { order: number; instruction: string; safety: "none" | "caution" | "danger" }[];
  required_parts: string[];
  coverage: "unknown" | "free" | "paid";
  danger?: boolean;
  sources?: { title: string; ref: string; confidence: number }[];
}
/** 증상/에러코드 → 해결책. respond가 키워드로 매칭. */
export const SOLUTIONS: { match: RegExp; label: string; solution: Solution }[] = [
  {
    match: /5c|물.*안.*빠|배수|세탁/, label: "세탁기 배수(5C)",
    solution: {
      required_parts: ["part_drain_filter"], coverage: "unknown",
      steps: [
        { order: 1, instruction: "배수 호스가 꺾이거나 눌리지 않았는지 확인하세요.", safety: "none" },
        { order: 2, instruction: "전원을 끄고 하단 배수 필터를 분리해 이물질을 청소하세요.", safety: "caution" },
        { order: 3, instruction: "배수 호스를 배수구에 15~20cm 깊이로 정리해 다시 연결하세요.", safety: "none" },
      ],
      sources: [{ title: "삼성 세탁기 4C/5C 오류 해결", ref: "https://www.samsung.com/us/support/troubleshoot/TSG10000997/", confidence: 0.9 }],
    },
  },
  {
    match: /타는 냄새|탄내|스파크|연기|감전|가스|인덕션/, label: "인덕션 안전 위험",
    solution: { required_parts: [], coverage: "unknown", danger: true, steps: [] },
  },
  {
    match: /냉장고|정수|물맛/, label: "냉장고 정수필터",
    solution: {
      required_parts: ["part_water_filter"], coverage: "free",
      steps: [
        { order: 1, instruction: "정수필터 표시등을 확인하세요.", safety: "none" },
        { order: 2, instruction: "필터를 반시계로 돌려 분리 후 새 필터로 교체하세요.", safety: "none" },
      ],
    },
  },
];

export interface Slot { id: string; start: string; end: string; visit_type: string; }
export const SLOTS: Slot[] = [
  { id: "slot_1", start: "6/14(토) 10:00", end: "12:00", visit_type: "REPAIR" },
  { id: "slot_2", start: "6/14(토) 14:00", end: "16:00", visit_type: "REPAIR" },
  { id: "slot_3", start: "6/15(일) 10:00", end: "12:00", visit_type: "REPAIR" },
];

/** 홈 시드(주문/예약 이력은 store에서 병합). */
export const HOME = {
  user: "홍길동",
  devices: DEVICES,
  alerts: [
    { id: "alert_fridge", device_id: "dev_fridge_01", type: "consumable", severity: "warning", detail: "정수필터 수명 15% 남음(임계치 20%)." },
    { id: "alert_purifier", device_id: "dev_purifier_01", type: "consumable", severity: "info", detail: "HEPA 필터 교체 시기가 임박했습니다." },
  ],
  recommendations: [PRODUCTS[0]],
};

export const SEED_ORDERS = [
  { id: "ord_seed_1", status: "DELIVERED", items: [{ part_id: "part_drain_filter", name: "세탁기 배수 필터", qty: 1, price: 12000 }], total: 15000, created_at: "2026-06-09T10:00:00Z" },
];
export const SEED_BOOKINGS: { id: string; slot_id: string; visit_type: string; status: string; start?: string; created_at: string }[] = [];
