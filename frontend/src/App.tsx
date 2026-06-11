/** 앱 루트 — 홈(S1) · 채팅 패널(S3) · 라이브(WS) · 템플릿 갤러리. */
import React, { useState } from "react";
import { HomeScreen } from "./screens/HomeScreen";
import { ChatPanel } from "./screens/ChatPanel";
import { LiveChat } from "./screens/LiveChat";
import { Gallery } from "./screens/Gallery";
import { j1Sections } from "./fixtures/journeys";

export const DEMO_Q = "세탁기에서 물이 안 빠져요. 해결하고 부품도 주문할래요.";
export type ScreenName = "home" | "chat" | "live" | "gallery";

export function App({ initialScreen = "home", wsUrl }:
  { initialScreen?: ScreenName; wsUrl?: string }) {
  const [screen, setScreen] = useState<ScreenName>(initialScreen);
  if (screen === "live") return <LiveChat wsUrl={wsUrl || "ws://localhost:8000/chat?token=demo"} />;
  if (screen === "gallery") return <Gallery />;
  if (screen === "chat") {
    return <ChatPanel question={DEMO_Q} sections={j1Sections} flow="troubleshoot" />;
  }
  return <HomeScreen onOpenChat={() => setScreen("chat")} onGallery={() => setScreen("gallery")} />;
}
