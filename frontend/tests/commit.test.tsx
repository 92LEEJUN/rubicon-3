/** 커밋 라운드트립(REST) — 409 확인 · 401 로그인 · 2-step 재제출(요구 ⑤⑥, SHARED CONTRACT §commit). */
import { commit, commitFromCta, isCommitCta } from "../src/transport/commit";
import type { Cta } from "../src/types/contract";

const cfg = { base: "https://bff.test", token: "t" };

function mockFetch(impl: (url: string, init?: any) => { status?: number; ok?: boolean; json?: () => any }) {
  (global as any).fetch = jest.fn((url: string, init?: any) => {
    const r = impl(String(url), init);
    return Promise.resolve({
      ok: r.ok ?? (r.status ? r.status < 400 : true),
      status: r.status ?? 200,
      json: async () => (r.json ? r.json() : {}),
    });
  });
}
afterEach(() => { delete (global as any).fetch; });

test("isCommitCta — order/booking commit만 true", () => {
  expect(isCommitCta({ label: "주문", action: "commit", kind: "order" })).toBe(true);
  expect(isCommitCta({ label: "예약", action: "commit", kind: "booking" })).toBe(true);
  expect(isCommitCta({ label: "자세히", action: "chat", kind: "explain" })).toBe(false);
  expect(isCommitCta({ label: "로그인", action: "navigate", kind: "login" })).toBe(false);
});

test("409 ConfirmationRequired → confirm 상태 + 확인 템플릿(주문)", async () => {
  mockFetch((url) => {
    expect(url).toContain("/orders");
    return { status: 409, json: () => ({ code: "ConfirmationRequired", template: { kind: "confirmation", data: { x: 1 } } }) };
  });
  const res = await commit(cfg, "order", { part_ids: ["p1"] });
  expect(res.status).toBe("confirm");
  if (res.status === "confirm") {
    expect(res.template.kind).toBe("confirmation");
    expect(res.payload).toMatchObject({ part_ids: ["p1"] });
  }
});

test("409 → 2-step 재제출은 confirmed:true 동반, 200이면 ok", async () => {
  let lastBody: any = null;
  mockFetch((_url, init) => {
    lastBody = JSON.parse(init.body);
    return lastBody.confirmed ? { status: 200, json: () => ({ order_id: "o1" }) }
                              : { status: 409, json: () => ({ code: "ConfirmationRequired" }) };
  });
  const first = await commit(cfg, "order", { part_ids: ["p1"] });
  expect(first.status).toBe("confirm");
  const second = await commit(cfg, "order", first.status === "confirm" ? first.payload : {}, true);
  expect(second.status).toBe("ok");
  expect(lastBody.confirmed).toBe(true);
});

test("401 LoginRequired → login 상태 + login CTA", async () => {
  mockFetch(() => ({ status: 401, json: () => ({ code: "LoginRequired", cta: { kind: "login", action: "navigate", label: "로그인" } }) }));
  const res = await commit(cfg, "booking", { slot_id: "s1" });
  expect(res.status).toBe("login");
  if (res.status === "login") expect(res.cta?.kind).toBe("login");
});

test("booking commit은 /bookings로 POST", async () => {
  let path = "";
  mockFetch((url) => { path = url; return { status: 200, json: () => ({ booking_id: "b1" }) }; });
  const res = await commit(cfg, "booking", { slot_id: "s1" }, true);
  expect(path).toContain("/bookings");
  expect(res.status).toBe("ok");
});

test("commitFromCta — commit 대상 아니면 null", async () => {
  (global as any).fetch = jest.fn();
  const r = await commitFromCta(cfg, { label: "자세히", action: "chat", kind: "explain" } as Cta);
  expect(r).toBeNull();
  expect((global as any).fetch).not.toHaveBeenCalled();
  delete (global as any).fetch;
});

test("base 미설정(정적 배포) — 첫 호출은 데모 확인, 확정은 ok", async () => {
  (global as any).fetch = jest.fn();
  const first = await commit({}, "order", {});
  expect(first.status).toBe("confirm");
  const second = await commit({}, "order", {}, true);
  expect(second.status).toBe("ok");
  expect((global as any).fetch).not.toHaveBeenCalled();
  delete (global as any).fetch;
});
