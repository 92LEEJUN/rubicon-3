/** 컴패니언 컴포넌트 — ResumeCard·OpenLoopList·ReEngagementBanner·StreamingMessage(요구 1·2·3·4). */
import React from "react";
import { render, fireEvent, screen } from "@testing-library/react";
import { ResumeCard } from "../src/components/ResumeCard";
import { OpenLoopList } from "../src/components/OpenLoopList";
import { ReEngagementBanner } from "../src/components/ReEngagementBanner";
import { StreamingMessage } from "../src/components/StreamingMessage";
import { sortByPriority } from "../src/state/useOpenLoops";
import type { MessageSection, OpenLoop, ResumePayload } from "../src/types/contract";

const loops: OpenLoop[] = [
  { id: "1", kind: "order", ref: "o1", status: "open", priority: 1, summary: "공기청정기 필터 주문" },
  { id: "2", kind: "issue", ref: "i1", status: "open", priority: 5, summary: "세탁기 5C 미해결" },
];

const resume: ResumePayload = {
  has_context: true,
  summary: "세탁기 배수 문제를 진단 중이었어요.",
  elapsed_label: "어제",
  open_loops: loops,
};

test("ResumeCard — 요약·상대시간·open-loop·이어가기/새로시작 렌더(요구 1.1~1.4)", () => {
  const onContinue = jest.fn(), onFresh = jest.fn();
  render(
    <ResumeCard resume={resume} loops={sortByPriority(loops)}
                onContinue={onContinue} onStartFresh={onFresh} />,
  );
  expect(screen.getByTestId("resume-summary")).toHaveTextContent("세탁기 배수");
  expect(screen.getByTestId("resume-elapsed")).toHaveTextContent("어제");
  expect(screen.getByTestId("open-loop-list")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("resume-continue"));
  fireEvent.click(screen.getByTestId("resume-fresh"));
  expect(onContinue).toHaveBeenCalled();
  expect(onFresh).toHaveBeenCalled();
});

test("ResumeCard — degraded면 open-loop 대신 안내만(요구 5.4)", () => {
  render(<ResumeCard resume={{ has_context: true, summary: "요약만" }} loops={[]} degraded />);
  expect(screen.getByTestId("resume-summary")).toHaveTextContent("요약만");
  expect(screen.queryByTestId("open-loop-list")).not.toBeInTheDocument();
});

test("sortByPriority — 우선순위 내림차순(요구 1.3·2.1)", () => {
  expect(sortByPriority(loops).map((l) => l.ref)).toEqual(["i1", "o1"]);
});

test("OpenLoopItem — kind 라벨·탭 재진입·resolve/dismiss(요구 2.1~2.3)", () => {
  const onOpen = jest.fn(), onResolve = jest.fn(), onDismiss = jest.fn();
  render(<OpenLoopList loops={loops} onOpen={onOpen} onResolve={onResolve} onDismiss={onDismiss} />);
  fireEvent.click(screen.getByTestId("open-loop-tap-i1"));
  fireEvent.click(screen.getByTestId("open-loop-resolve-o1"));
  fireEvent.click(screen.getByTestId("open-loop-dismiss-i1"));
  expect(onOpen).toHaveBeenCalledWith("i1");
  expect(onResolve).toHaveBeenCalledWith("o1");
  expect(onDismiss).toHaveBeenCalledWith("i1");
});

test("OpenLoopList — 에러 시 안내·재시도 노출(요구 2.5)", () => {
  const retry = jest.fn();
  render(<OpenLoopList loops={[]} error="처리에 실패했어요" onRetryDismissError={retry} />);
  fireEvent.click(screen.getByTestId("open-loop-error"));
  expect(retry).toHaveBeenCalled();
});

test("ReEngagementBanner — label·message·also_count·탭·닫기(요구 3.1·3.3·3.5)", () => {
  const onOpen = jest.fn(), onDismiss = jest.fn();
  render(
    <ReEngagementBanner
      banner={{ primary_ref: "r9", primary_label: "부품 입고", message: "정수필터가 도착했어요", also_count: 2 }}
      onOpen={onOpen} onDismiss={onDismiss} />,
  );
  expect(screen.getByTestId("reengagement-label")).toHaveTextContent("부품 입고");
  expect(screen.getByTestId("reengagement-also")).toHaveTextContent("2");
  fireEvent.click(screen.getByTestId("reengagement-open"));
  expect(onOpen).toHaveBeenCalledWith("r9");
  fireEvent.click(screen.getByTestId("reengagement-dismiss"));
  expect(onDismiss).toHaveBeenCalled();
});

test("StreamingMessage — 수신 중 타이핑, 내용 도착 시 텍스트+섹션 스택(요구 4.2·4.3)", () => {
  const sections: MessageSection[] = [
    { label: "진단", intent: "device_status", handled: true, ctas: [], template: { kind: "text", data: { message: "5C" } } },
    { label: "주문", intent: "order", handled: false, ctas: [], template: { kind: "unknown_kind", data: {} } },
  ];
  const { rerender } = render(<StreamingMessage text="" sections={[]} streaming />);
  expect(screen.getByTestId("streaming-typing")).toBeInTheDocument();

  rerender(<StreamingMessage text="확인했어요" sections={sections} streaming />);
  expect(screen.queryByTestId("streaming-typing")).not.toBeInTheDocument();
  expect(screen.getByTestId("streaming-text")).toHaveTextContent("확인했어요");
  // 미처리 섹션은 톤다운 안내로 노출(정상 답변 카드 아님, §7·요구 ⑦)
  expect(screen.getByText("이건 아직 도와드리기 어려워요.")).toBeInTheDocument();
});
