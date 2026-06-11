/** 템플릿 렌더러 — kind별 렌더 + 미등록 폴백(response-templates §7). */
import React from "react";
import { render, screen } from "@testing-library/react";
import { TemplateView } from "../src/templates";
import { homeSummary, confirmation, j1Sections } from "../src/fixtures/journeys";

test("device_status renders model + 점검 필요 상태", () => {
  const t = j1Sections[0].template;
  render(<TemplateView template={t} />);
  expect(screen.getByText(/WF45T6000AW/)).toBeInTheDocument();
  expect(screen.getByText("점검 필요")).toBeInTheDocument();
});

test("guide_steps renders numbered steps + 주의 badge", () => {
  render(<TemplateView template={j1Sections[1].template} />);
  expect(screen.getByText(/배수 호스가 꺾이거나/)).toBeInTheDocument();
  expect(screen.getByText("주의")).toBeInTheDocument(); // safety=caution
});

test("product_card renders price + 재고", () => {
  render(<TemplateView template={j1Sections[2].template} />);
  expect(screen.getByText("₩12,000")).toBeInTheDocument();
  expect(screen.getByText("재고 있음")).toBeInTheDocument();
});

test("confirmation renders 금액 분해 총액", () => {
  render(<TemplateView template={confirmation} />);
  expect(screen.getByText("₩15,000")).toBeInTheDocument(); // total
});

test("home_summary renders greeting + alert", () => {
  render(<TemplateView template={homeSummary} />);
  expect(screen.getByText(/홍길동님/)).toBeInTheDocument();
  expect(screen.getByText(/정수필터 수명/)).toBeInTheDocument();
});

test("unknown kind falls back to text", () => {
  render(<TemplateView template={{ kind: "totally_unknown", data: {} }} />);
  expect(screen.getByText(/지원하지 않는 형식/)).toBeInTheDocument();
});
