/** 메인 셸 — 상단 브랜드 + 토글(홈 ↔ 고객지원)으로 화면 전환(wireframes S1·S2). */
import React, { useState } from "react";
import { StyleSheet, View } from "react-native";
import { Caption, Heading } from "../components/primitives";
import { SegmentedTabs } from "../components/SegmentedTabs";
import { HomeScreen } from "./HomeScreen";
import { SupportScreen } from "./SupportScreen";
import { color, space } from "../design/tokens";

export type MainTab = "home" | "support";

export function MainShell({ initialTab = "home", onOpenChat, onGallery }:
  { initialTab?: MainTab; onOpenChat?: (q?: string) => void; onGallery?: () => void }) {
  const [tab, setTab] = useState<MainTab>(initialTab);
  return (
    <View style={styles.root} testID="screen-main">
      <View style={styles.header}>
        <Caption>Samsung</Caption>
        <Heading>AI 컨시어지</Heading>
        <View style={{ height: space.md }} />
        <SegmentedTabs
          value={tab}
          onChange={setTab}
          options={[{ key: "home", label: "홈" }, { key: "support", label: "고객지원" }]}
        />
      </View>
      {tab === "home"
        ? <HomeScreen onOpenChat={() => onOpenChat?.()} onGallery={onGallery} />
        : <SupportScreen onAsk={(q) => onOpenChat?.(q)} />}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  header: {
    paddingHorizontal: space.lg, paddingTop: space.lg, paddingBottom: space.md,
    backgroundColor: color.bg, maxWidth: 480, width: "100%", alignSelf: "center",
  },
});
