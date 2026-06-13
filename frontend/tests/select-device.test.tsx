/** select_device 칩 — 입력창 편집(prefill)이 아니라 탭 즉시 질의 전송. */
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { ChatPanel } from "../src/screens/ChatPanel";
import type { MessageSection } from "../src/types/contract";

const clarify: MessageSection = {
  label: "확인", intent: "clarify", handled: true,
  template: { kind: "text", data: { message: "어떤 기기가 궁금하세요?" } },
  ctas: [{ label: "washer", action: "chat", kind: "select_device", payload: { device_id: "dev_washer_01" } }],
};

test("select_device 탭 → 바로 질의 전송(사용자 메시지 등장)", () => {
  render(<ChatPanel question="안녕하세요" sections={[clarify]} />);
  fireEvent.click(screen.getAllByTestId("cta-select_device")[0]);
  expect(screen.getByText("dev_washer_01 기기에 대해 알려주세요")).toBeInTheDocument();
});
