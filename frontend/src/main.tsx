/** 웹 진입(react-native-web) — AppRegistry로 루트 마운트. ?screen=home|chat 로 화면 선택. */
import React from "react";
import { AppRegistry } from "react-native";
import { App, type ScreenName } from "./App";

const SCREENS: ScreenName[] = ["home", "support", "chat", "live", "gallery"];

function Root() {
  const params = new URLSearchParams(typeof location !== "undefined" ? location.search : "");
  const raw = (params.get("screen") || "home") as ScreenName;
  const screen = SCREENS.includes(raw) ? raw : "home";
  const wsUrl = params.get("ws") || undefined;
  return <App initialScreen={screen} wsUrl={wsUrl} />;
}

AppRegistry.registerComponent("ConciergeApp", () => Root);
AppRegistry.runApplication("ConciergeApp", {
  rootTag: document.getElementById("root"),
});
