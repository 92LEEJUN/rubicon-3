/** 화면 — 홈(S1) 진입·채팅 패널(S3) 스트림 누적. */
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { App, DEMO_Q } from "../src/App";

test("home renders summary and opens chat", () => {
  render(<App initialScreen="home" />);
  expect(screen.getByTestId("screen-home")).toBeInTheDocument();
  expect(screen.getByText("AI 컨시어지")).toBeInTheDocument(); // 헤딩(정확 일치)
  fireEvent.click(screen.getByTestId("open-chat"));
  expect(screen.getByTestId("screen-chat")).toBeInTheDocument();
});

test("chat panel streams J1 sections from transport", () => {
  render(<App initialScreen="chat" />);
  expect(screen.getByText(DEMO_Q)).toBeInTheDocument();
  // MockTransport가 즉시 재생 → 섹션 3개 누적
  expect(screen.getByTestId("section-troubleshoot")).toBeInTheDocument();
  expect(screen.getByText("₩12,000")).toBeInTheDocument();
});
