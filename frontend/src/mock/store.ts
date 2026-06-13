/** Mock 상태 스토어(ADR-0051) — 주문·예약·candidates·대화를 localStorage에 영속.
 *  영속 실패(프라이빗 모드 등)면 메모리 폴백(throw 금지, R7). 클라이언트 전용. */

const KEY = "rubicon.mock.v1";

export interface MockOrder {
  id: string;
  status: string;             // CONFIRMED
  items: { part_id: string; name: string; qty: number; price: number }[];
  total: number;
  created_at: string;
}
export interface MockBooking {
  id: string;
  slot_id: string;
  visit_type: string;
  status: string;             // CONFIRMED
  start?: string;
  created_at: string;
}
export interface MockState {
  orders: MockOrder[];
  bookings: MockBooking[];
  candidates: string[];       // 직전 추천 후보 product id(explain carry)
  conversation: { role: "user" | "assistant"; text: string }[];
}

const EMPTY: MockState = { orders: [], bookings: [], candidates: [], conversation: [] };

let memory: MockState | null = null;   // localStorage 불가 시 폴백

function load(): MockState {
  if (memory) return memory;
  try {
    const raw = window.localStorage.getItem(KEY);
    memory = raw ? { ...EMPTY, ...JSON.parse(raw) } : { ...EMPTY };
  } catch {
    memory = { ...EMPTY };
  }
  return memory;
}

function persist(s: MockState): void {
  memory = s;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* 프라이빗 모드 등 — 메모리 유지 */
  }
}

let _seq = 0;
const id = (p: string) => `${p}_${Date.now().toString(36)}${(_seq++).toString(36)}`;

export const mockStore = {
  state(): MockState {
    return load();
  },
  getOrders(): MockOrder[] {
    return [...load().orders].reverse();   // 최신순
  },
  addOrder(items: { part_id: string; name: string; qty?: number; price?: number }[]): MockOrder {
    const s = load();
    const norm = items.map((it) => ({ part_id: it.part_id, name: it.name, qty: it.qty ?? 1, price: it.price ?? 0 }));
    const order: MockOrder = {
      id: id("ord"), status: "CONFIRMED", items: norm,
      total: norm.reduce((a, it) => a + it.price * it.qty, 0),
      created_at: new Date().toISOString(),
    };
    persist({ ...s, orders: [...s.orders, order] });
    return order;
  },
  getBookings(): MockBooking[] {
    return [...load().bookings].reverse();
  },
  addBooking(slot_id: string, visit_type = "REPAIR", start?: string): MockBooking {
    const s = load();
    const bk: MockBooking = {
      id: id("bk"), slot_id, visit_type, status: "CONFIRMED", start,
      created_at: new Date().toISOString(),
    };
    persist({ ...s, bookings: [...s.bookings, bk] });
    return bk;
  },
  setCandidates(ids: string[]): void {
    persist({ ...load(), candidates: ids });
  },
  getCandidates(): string[] {
    return load().candidates;
  },
  reset(): void {
    memory = { ...EMPTY };
    try { window.localStorage.removeItem(KEY); } catch { /* noop */ }
  },
};
