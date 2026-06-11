/** CS 페이지 — 상단 토글로 홈↔고객지원 전환, CS 진입이 채팅을 연다(S2). */
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { App } from "../src/App";

test("main shell shows 홈/고객지원 toggle, defaults to 홈", () => {
  render(<App initialScreen="home" />);
  expect(screen.getByTestId("screen-main")).toBeInTheDocument();
  expect(screen.getByTestId("tab-home")).toBeInTheDocument();
  expect(screen.getByTestId("tab-support")).toBeInTheDocument();
  expect(screen.getByTestId("screen-home")).toBeInTheDocument(); // 기본 홈
});

test("toggle switches to 고객지원(CS) screen", () => {
  render(<App initialScreen="home" />);
  fireEvent.click(screen.getByTestId("tab-support"));
  expect(screen.getByTestId("screen-support")).toBeInTheDocument();
  expect(screen.getByText("무엇을 도와드릴까요?")).toBeInTheDocument();
  expect(screen.getByTestId("cs-troubleshoot")).toBeInTheDocument();
});

test("deep link ?screen=support lands on CS tab", () => {
  render(<App initialScreen="support" />);
  expect(screen.getByTestId("screen-support")).toBeInTheDocument();
});

test("CS quick action opens chat with that question", () => {
  render(<App initialScreen="support" />);
  fireEvent.click(screen.getByTestId("cs-faq-0"));
  expect(screen.getByTestId("screen-chat")).toBeInTheDocument();
  expect(screen.getByText("세탁기 배수가 안 돼요 (5C)")).toBeInTheDocument(); // 사용자 말풍선
});
