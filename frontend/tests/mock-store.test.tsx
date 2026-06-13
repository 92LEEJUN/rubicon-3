/** Mock 스토어(ADR-0051) — 주문·예약 add→get·reset. */
import { mockStore } from "../src/mock/store";

beforeEach(() => mockStore.reset());

test("주문 add → getOrders 최신순 반영", () => {
  expect(mockStore.getOrders()).toHaveLength(0);
  const o = mockStore.addOrder([{ part_id: "part_drain_filter", name: "배수필터", price: 12000, qty: 2 }]);
  expect(o.total).toBe(24000);
  const list = mockStore.getOrders();
  expect(list).toHaveLength(1);
  expect(list[0].id).toBe(o.id);
  expect(list[0].status).toBe("CONFIRMED");
});

test("예약 add → getBookings 반영", () => {
  const b = mockStore.addBooking("slot_2", "REPAIR");
  expect(mockStore.getBookings()[0].slot_id).toBe("slot_2");
  expect(b.status).toBe("CONFIRMED");
});

test("candidates 기록/조회", () => {
  mockStore.setCandidates(["prod_purifier_cube"]);
  expect(mockStore.getCandidates()).toEqual(["prod_purifier_cube"]);
});

test("reset 초기화", () => {
  mockStore.addOrder([{ part_id: "p", name: "x", price: 1 }]);
  mockStore.reset();
  expect(mockStore.getOrders()).toHaveLength(0);
  expect(mockStore.getBookings()).toHaveLength(0);
});
