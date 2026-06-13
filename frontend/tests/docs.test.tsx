/** 아키텍처 문서 탭 — 진입·3 서브탭 전환·텍스트 렌더(GH Pages 텍스트 열람). */
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { App } from "../src/App";
import { Docs } from "../src/screens/Docs";

test("홈에서 '아키텍처 문서' 링크로 docs 화면 진입", () => {
  render(<App initialScreen="home" />);
  fireEvent.click(screen.getByTestId("open-docs"));
  expect(screen.getByTestId("screen-docs")).toBeInTheDocument();
});

test("docs는 BE/BFF/FE 3 서브탭 + 본문을 렌더하고 전환된다", () => {
  render(<Docs />);
  expect(screen.getByTestId("docs-tab-be")).toBeInTheDocument();
  expect(screen.getByTestId("docs-tab-bff")).toBeInTheDocument();
  expect(screen.getByTestId("docs-tab-fe")).toBeInTheDocument();
  expect(screen.getByTestId("docs-body")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("docs-tab-fe"));   // 전환해도 본문 유지
  expect(screen.getByTestId("docs-body")).toBeInTheDocument();
});

test("?screen=docs 로 직접 진입", () => {
  render(<App initialScreen="docs" />);
  expect(screen.getByTestId("screen-docs")).toBeInTheDocument();
});
