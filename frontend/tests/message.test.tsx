/** 섹션/메시지 렌더 — 복합 스택·미처리 표시·CTA(R7). */
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { MessageView } from "../src/components/message";
import { j1Sections, j5UnhandledHepa } from "../src/fixtures/journeys";

test("renders one card per section (복합 R7)", () => {
  render(<MessageView sections={j1Sections} />);
  expect(screen.getByTestId("section-device_status")).toBeInTheDocument();
  expect(screen.getByTestId("section-troubleshoot")).toBeInTheDocument();
  expect(screen.getByTestId("section-order")).toBeInTheDocument();
});

test("unhandled section shows 미처리 badge (R7-3)", () => {
  render(<MessageView sections={[j5UnhandledHepa]} />);
  expect(screen.getByText("미처리")).toBeInTheDocument();
});

test("CTA press fires handler", () => {
  const onCta = jest.fn();
  render(<MessageView sections={j1Sections} onCta={onCta} />);
  fireEvent.click(screen.getAllByTestId("cta-order")[0]);
  expect(onCta).toHaveBeenCalledTimes(1);
  expect(onCta.mock.calls[0][0].kind).toBe("order");
});
