/** 앱 루트 — 메인(홈/고객지원 토글) · 채팅(S3) · 라이브(WS) · 템플릿 갤러리. */
import React, { useState } from "react";
import { MainShell } from "./screens/MainShell";
import { ChatPanel } from "./screens/ChatPanel";
import { LiveChat } from "./screens/LiveChat";
import { Gallery } from "./screens/Gallery";
import { Scenario } from "./screens/Scenario";
import { Docs } from "./screens/Docs";
import { ConsentProvider } from "./state/useConsent";
import { j1Sections } from "./fixtures/journeys";

export const DEMO_Q = "세탁기에서 물이 안 빠져요. 해결하고 부품도 주문할래요.";
export type ScreenName = "home" | "support" | "chat" | "live" | "gallery" | "scenario" | "docs";

export function App({ initialScreen = "home", wsUrl, apiBase, token, scenarioId }:
  { initialScreen?: ScreenName; wsUrl?: string; apiBase?: string; token?: string; scenarioId?: string }) {
  const [screen, setScreen] = useState<ScreenName>(initialScreen);
  const [question, setQuestion] = useState<string>(DEMO_Q);

  // 동의 게이트(R19)는 앱 전역에서 공유 — 선제/개인화 표현 훅이 이 Provider를 본다.
  return (
    <ConsentProvider>
      {screen === "live" ? <LiveChat wsUrl={wsUrl || "ws://localhost:8000/chat?token=demo"} apiBase={apiBase} token={token} /> :
       screen === "gallery" ? <Gallery /> :
       screen === "docs" ? <Docs onClose={() => setScreen("home")} /> :
       screen === "scenario" ? <Scenario id={scenarioId} /> :
       screen === "chat" ? (
        <ChatPanel question={question} sections={j1Sections} flow="troubleshoot"
                   wsUrl={wsUrl} apiBase={apiBase} token={token} onClose={() => setScreen("home")} />
      ) : (
        <MainShell
          initialTab={screen === "support" ? "support" : "home"}
          apiBase={apiBase}
          token={token}
          onOpenChat={(q) => { setQuestion(q ?? ""); setScreen("chat"); }}
          onGallery={() => setScreen("gallery")}
          onDocs={() => setScreen("docs")}
        />
      )}
    </ConsentProvider>
  );
}
