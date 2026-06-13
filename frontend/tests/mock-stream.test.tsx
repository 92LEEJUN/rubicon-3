/** MockTransport 스트리밍(ADR-0051) — delayMs>0이면 청크 점진 방출, delta는 글자 단위. */
import { MockTransport } from "../src/transport";
import type { Chunk } from "../src/types/contract";

const script = (): Chunk[] => [
  { type: "delta", text: "abcdef" },                                  // 6자 → 2조각(3자씩)
  { type: "section", section: { label: "x", intent: "general", template: { kind: "text", data: {} }, ctas: [], handled: true } },
  { type: "flow", active_flow: null },
  { type: "done", message_id: "m1" },
];

test("delayMs>0 → 점진 방출(즉시 0, 타이머 진행 시 순차, 마지막 done)", () => {
  jest.useFakeTimers();
  const got: Chunk[] = [];
  const m = new MockTransport(script, { delayMs: 10 });
  m.onChunk((c) => got.push(c));
  m.connect();
  m.send({ type: "user_message", text: "hi" });

  expect(got).toHaveLength(0);              // 동기 즉시 방출 안 함
  jest.advanceTimersByTime(10);
  expect(got).toHaveLength(1);              // 첫 청크(delta 조각)
  jest.runAllTimers();
  expect(got[got.length - 1].type).toBe("done");
  expect(got.filter((c) => c.type === "delta")).toHaveLength(2);   // delta 쪼개짐
  jest.useRealTimers();
});

test("delayMs 미지정 → 동기 방출(테스트 단언 안정)", () => {
  const got: Chunk[] = [];
  const m = new MockTransport(script);
  m.onChunk((c) => got.push(c));
  m.send({ type: "user_message", text: "hi" });
  expect(got[got.length - 1].type).toBe("done");   // 즉시 전부
});
