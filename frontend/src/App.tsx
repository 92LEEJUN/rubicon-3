/** 앱 루트 — 메인(홈/고객지원 토글) · 채팅(S3) · 라이브(WS) · 템플릿 갤러리. */
import React, { useState } from "react";
import { MainShell } from "./screens/MainShell";
import { ChatPanel } from "./screens/ChatPanel";
import { LiveChat } from "./screens/LiveChat";
import { Gallery } from "./screens/Gallery";
import { j1Sections } from "./fixtures/journeys";

export const DEMO_Q = "세탁기에서 물이 안 빠져요. 해결하고 부품도 주문할래요.";
export type ScreenName = "home" | "support" | "chat" | "live" | "gallery";

export function App({ initialScreen = "home", wsUrl }:
  { initialScreen?: ScreenName; wsUrl?: string }) {
  const [screen, setScreen] = useState<ScreenName>(initialScreen);
  const [question, setQuestion] = useState<string>(DEMO_Q);

  if (screen === "live") return <LiveChat wsUrl={wsUrl || "ws://localhost:8000/chat?token=demo"} />;
  if (screen === "gallery") return <Gallery />;
  if (screen === "chat") return <ChatPanel question={question} sections={j1Sections} flow="troubleshoot" wsUrl={wsUrl} />;

  return (
    <MainShell
      initialTab={screen === "support" ? "support" : "home"}
      onOpenChat={(q) => { if (q) setQuestion(q); setScreen("chat"); }}
      onGallery={() => setScreen("gallery")}
    />
  );
}
