/** 채팅 reducer — 청크 누적·완료·에러 폴백(R7·R13). */
import { chatReducer, initialChat } from "../src/state/chat";
import { j1Sections } from "../src/fixtures/journeys";

test("send resets and enters streaming", () => {
  const s = chatReducer({ ...initialChat, sections: j1Sections }, { type: "send" });
  expect(s.status).toBe("streaming");
  expect(s.sections).toHaveLength(0);
});

test("section chunks accumulate in order (R7)", () => {
  let s = chatReducer(initialChat, { type: "send" });
  for (const section of j1Sections) s = chatReducer(s, { type: "section", section });
  expect(s.sections.map((x) => x.intent)).toEqual(["device_status", "troubleshoot", "order"]);
});

test("flow + done finalize", () => {
  let s = chatReducer(initialChat, { type: "flow", active_flow: "troubleshoot" });
  s = chatReducer(s, { type: "done", message_id: "msg_1" });
  expect(s.activeFlow).toBe("troubleshoot");
  expect(s.status).toBe("done");
  expect(s.messageId).toBe("msg_1");
});

test("error injects fallback section, does not drop conversation (R13)", () => {
  const s = chatReducer(initialChat, {
    type: "error", code: "upstream_unavailable",
    fallback: { kind: "text", data: { message: "일시적 오류" } },
  });
  expect(s.status).toBe("error");
  expect(s.sections[0].template.kind).toBe("text");
  expect(s.sections[0].handled).toBe(false);
});
