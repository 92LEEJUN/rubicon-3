/**
 * 서비스 E2E — 클라이언트(FE 입장)가 BFF HTTP로 수행하는 저니(실 BFF→BE 스택).
 * 커밋 게이트(J1)·선제/브릿지(J2)·추천(J3)·방문 예약(J4).
 */
import { expect, test } from "@playwright/test";

const BFF = "http://127.0.0.1:8000";
const AUTH = { Authorization: "Bearer e2e-token" };

test("J1 — 주문 커밋 게이트(R17): 미확인 409 → 확인 후 CONFIRMED", async ({ request }) => {
  const gated = await request.post(`${BFF}/orders`, {
    headers: AUTH, data: { part_ids: ["part_drain_filter"] },
  });
  expect(gated.status()).toBe(409);
  const body = await gated.json();
  expect(body.template.kind).toBe("confirmation");
  expect(body.template.data.summary.subtotal).toBe(12000);

  const ok = await request.post(`${BFF}/orders`, {
    headers: AUTH, data: { part_ids: ["part_drain_filter"], confirmed: true },
  });
  expect(ok.status()).toBe(200);
  expect((await ok.json()).status).toBe("CONFIRMED");
});

test("J2 — 선제 알림(home_summary) + 카드 탭 브릿지(S4)", async ({ request }) => {
  const home = await request.get(`${BFF}/home`, { headers: AUTH });
  const hb = await home.json();
  expect(hb.kind).toBe("home_summary");
  expect(hb.data.alerts.length).toBeGreaterThanOrEqual(1);  // 정수/HEPA 임박

  const surface = await request.post(`${BFF}/surface`, {
    headers: AUTH, data: { card_type: "consumable", ref: "냉장고" },
  });
  expect((await surface.json()).surface).toBe("bridge");
});

test("J3 — 개인화 추천(관심 카테고리)", async ({ request }) => {
  const r = await request.get(`${BFF}/catalog/recommend`, { headers: AUTH });
  const products = await r.json();
  expect(products.some((p: any) => p.id === "prod_purifier_cube")).toBe(true);
});

test("J4 — 방문 예약(R18): 슬롯 조회 → 예약 확정", async ({ request }) => {
  const slots = await (await request.get(`${BFF}/bookings/slots`, { headers: AUTH })).json();
  expect(slots.length).toBeGreaterThanOrEqual(1);
  const booking = await request.post(`${BFF}/bookings`, {
    headers: AUTH, data: { slot_id: slots[0].id, context_ref: "conv_e2e" },
  });
  expect((await booking.json()).status).toBe("CONFIRMED");
});

test("인증 게이트 — 토큰 없으면 401", async ({ request }) => {
  const r = await request.get(`${BFF}/devices`);
  expect(r.status()).toBe(401);
});
