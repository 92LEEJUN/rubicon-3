/** 앱 루트 — 홈(S1) ↔ 전역 채팅 패널(S3). 스크린샷은 initialScreen로 직접 진입. */
import React, { useState } from "react";
import { HomeScreen } from "./screens/HomeScreen";
import { ChatPanel } from "./screens/ChatPanel";
import { j1Sections } from "./fixtures/journeys";

export const DEMO_Q = "세탁기에서 물이 안 빠져요. 해결하고 부품도 주문할래요.";

export function App({ initialScreen = "home" }: { initialScreen?: "home" | "chat" }) {
  const [screen, setScreen] = useState<"home" | "chat">(initialScreen);
  if (screen === "chat") {
    return <ChatPanel question={DEMO_Q} sections={j1Sections} flow="troubleshoot" />;
  }
  return <HomeScreen onOpenChat={() => setScreen("chat")} />;
}
