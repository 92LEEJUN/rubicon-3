/** 동의 게이트 즉시 갱신 + 트랜스포트 독립(요구 5·6). */
import React from "react";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useReEngagement } from "../src/state/useReEngagement";
import { ConsentProvider, createConsentStore } from "../src/state/useConsent";
import { companionStore } from "../src/state/companionStore";
import { useChat } from "../src/state/useChat";
import { MockTransport } from "../src/transport";
import type { ChatTransport } from "../src/transport";
import type { Chunk, ClientMessage } from "../src/types/contract";

function mockFetch() {
  (global as any).fetch = jest.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: async () => ({ primary_label: "부품 입고", primary_ref: "r1" }) }),
  );
}
afterEach(() => { delete (global as any).fetch; companionStore.reset(); });

test("동의 철회 시 노출 중 배너 즉시 제거(요구 6.3)", async () => {
  mockFetch();
  const store = createConsentStore({ opted_in: true });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <ConsentProvider store={store}>{children}</ConsentProvider>
  );
  const { result } = renderHook(() => useReEngagement({ base: "https://bff.test" }, true), { wrapper: Wrapper });
  await waitFor(() => expect(result.current.banner).not.toBeNull());

  // 동의 철회 → 구독 통지 → 게이트가 배너 제거
  act(() => { store.set({ opted_in: false }); });
  await waitFor(() => expect(result.current.banner).toBeNull());
  expect(companionStore.get().bannerState).toBe("hidden");
});

test("useChat.resumeFromRef — 임의의 ChatTransport(stub)에만 의존, ref를 screen_context로 주입(요구 2.2·5.1)", () => {
  const sent: ClientMessage[] = [];
  // ChatTransport 인터페이스만 만족하는 stub(구체 트랜스포트 결합 없음)
  const stub: ChatTransport = {
    connect: () => {},
    send: (m) => sent.push(m),
    onChunk: () => {},
    onState: () => {},
    close: () => {},
  };
  const { result } = renderHook(() => useChat(stub));
  act(() => { result.current.resumeFromRef("loop-42", { screen: "home" }); });
  const last = sent[sent.length - 1] as any;
  expect(last.type).toBe("user_message");
  expect(last.screen_context.resume_ref).toBe("loop-42");
  expect(last.screen_context.screen).toBe("home");
});

test("MockTransport 스크립트 청크를 useChat이 reducer로 누적(트랜스포트 독립, 요구 5.1)", async () => {
  const script = (_m: ClientMessage): Chunk[] => [
    { type: "delta", text: "안녕" },
    { type: "section", section: { label: "x", intent: "x", handled: true, ctas: [], template: { kind: "text", data: { message: "x" } } } },
    { type: "done", message_id: "m" },
  ];
  const transport = new MockTransport(script);
  const { result } = renderHook(() => useChat(transport));
  act(() => { result.current.send("hi"); });
  await waitFor(() => expect(result.current.state.status).toBe("done"));
  expect(result.current.state.assistantText).toBe("안녕");
  expect(result.current.state.sections).toHaveLength(1);
});
