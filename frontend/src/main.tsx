/** 웹 진입(react-native-web) — AppRegistry로 루트 마운트.
 *  쿼리: ?screen=home|support|chat|live|gallery, ?ws=<bff ws>, ?api=<bff base>, ?token=<auth>. */
import React from "react";
import { AppRegistry } from "react-native";
import { App, type ScreenName } from "./App";

const SCREENS: ScreenName[] = ["home", "support", "chat", "live", "gallery", "scenario"];

function Root() {
  const params = new URLSearchParams(typeof location !== "undefined" ? location.search : "");
  const raw = (params.get("screen") || "home") as ScreenName;
  const screen = SCREENS.includes(raw) ? raw : "home";
  const wsUrl = params.get("ws") || undefined;
  const apiBase = params.get("api") || undefined;
  const token = params.get("token") || undefined;
  const scenarioId = params.get("id") || undefined;
  return <App initialScreen={screen} wsUrl={wsUrl} apiBase={apiBase} token={token} scenarioId={scenarioId} />;
}

AppRegistry.registerComponent("ConciergeApp", () => Root);
AppRegistry.runApplication("ConciergeApp", {
  rootTag: document.getElementById("root"),
});
