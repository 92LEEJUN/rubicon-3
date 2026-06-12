/** 컴패니언 BFF 클라이언트 — resume·reengagement·open-loop 계약 stub(요구 1·2·3·5). */
import { getResume, getReEngagement, postOpenLoopAction } from "../src/transport/companion";

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

test("getResume — has_context payload를 그대로 돌려준다(요구 1.1)", async () => {
  mockFetch(() => ({ json: () => ({ has_context: true, summary: "세탁기 5C", elapsed_label: "어제" }) }));
  const p = await getResume(cfg);
  expect(p.has_context).toBe(true);
  expect(p.summary).toBe("세탁기 5C");
});

test("getResume — fresh=true면 쿼리 파라미터를 붙인다(요구 1.5)", async () => {
  let calledUrl = "";
  mockFetch((url) => { calledUrl = url; return { json: () => ({ has_context: false }) }; });
  await getResume(cfg, true);
  expect(calledUrl).toContain("/resume?fresh=true");
});

test("getResume — 실패 시 has_context=false로 정규화(요구 5.4)", async () => {
  mockFetch(() => ({ status: 500 }));
  const p = await getResume(cfg);
  expect(p.has_context).toBe(false);
});

test("getReEngagement — {}이면 null(미노출, 요구 3.4)", async () => {
  mockFetch(() => ({ json: () => ({}) }));
  expect(await getReEngagement(cfg)).toBeNull();
});

test("getReEngagement — deliver=true면 POST /reengagement/deliver(요구 3.2)", async () => {
  let method = "", path = "";
  mockFetch((url, init) => { method = init?.method; path = url; return { json: () => ({ primary_label: "부품 입고" }) }; });
  const re = await getReEngagement(cfg, true);
  expect(method).toBe("POST");
  expect(path).toContain("/reengagement/deliver");
  expect(re?.primary_label).toBe("부품 입고");
});

test("postOpenLoopAction — 성공 시 ok(요구 2.4)", async () => {
  mockFetch((url) => { expect(url).toContain("/open-loops/ref1/resolve"); return { status: 200, json: () => ({ id: "1" }) }; });
  const r = await postOpenLoopAction(cfg, "ref1", "resolve");
  expect(r.ok).toBe(true);
  expect(r.notFound).toBe(false);
});

test("postOpenLoopAction — 404면 notFound(롤백 신호, 요구 2.5)", async () => {
  mockFetch(() => ({ status: 404 }));
  const r = await postOpenLoopAction(cfg, "gone", "dismiss");
  expect(r.ok).toBe(false);
  expect(r.notFound).toBe(true);
});

test("base 미설정이면 네트워크를 타지 않는다(정적 배포)", async () => {
  (global as any).fetch = jest.fn();
  const p = await getResume({});
  expect(p.has_context).toBe(false);
  expect((global as any).fetch).not.toHaveBeenCalled();
  delete (global as any).fetch;
});
