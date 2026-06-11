/** 웹 진입(react-native-web) — AppRegistry로 루트 마운트. ?screen=home|chat 로 화면 선택. */
import React from "react";
import { AppRegistry } from "react-native";
import { App } from "./App";

function Root() {
  const params = new URLSearchParams(typeof location !== "undefined" ? location.search : "");
  const screen = params.get("screen") === "chat" ? "chat" : "home";
  return <App initialScreen={screen} />;
}

AppRegistry.registerComponent("ConciergeApp", () => Root);
AppRegistry.runApplication("ConciergeApp", {
  rootTag: document.getElementById("root"),
});
