/** 메인 셸 — 상단 브랜드 + 토글(홈↔고객지원) + 하단 고정 채팅바(전 탭 공통, wireframes §6). */
import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Caption, Heading } from "../components/primitives";
import { SegmentedTabs } from "../components/SegmentedTabs";
import { HomeScreen } from "./HomeScreen";
import { SupportScreen } from "./SupportScreen";
import { useHomeData } from "../state/useHomeData";
import { color, font, gradient, radius, space } from "../design/tokens";

export type MainTab = "home" | "support";

export function MainShell({ initialTab = "home", apiBase, token, onOpenChat, onGallery }:
  { initialTab?: MainTab; apiBase?: string; token?: string;
    onOpenChat?: (q?: string) => void; onGallery?: () => void }) {
  const [tab, setTab] = useState<MainTab>(initialTab);
  const data = useHomeData({ base: apiBase, token });

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
        ? <HomeScreen data={data} onOpenChat={(q) => onOpenChat?.(q)} onGallery={onGallery} />
        : <SupportScreen data={data} onAsk={(q) => onOpenChat?.(q)} />}

      {/* 하단 고정 채팅바 — 홈·CS 공통(탭하면 채팅으로 펼침) */}
      <Pressable testID="open-chat" accessibilityRole="button" onPress={() => onOpenChat?.()}
                 style={styles.chatBar}>
        <View style={styles.chatStub}><Text style={styles.chatStubText}>가전 문제·부품 주문을 물어보세요</Text></View>
        <View style={styles.chatSend}><Text style={styles.chatSendIcon}>↑</Text></View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  header: {
    paddingHorizontal: space.lg, paddingTop: space.lg, paddingBottom: space.md,
    backgroundColor: color.bg, maxWidth: 480, width: "100%", alignSelf: "center",
  },
  chatBar: {
    flexDirection: "row", alignItems: "center", gap: space.sm,
    paddingHorizontal: space.lg, paddingTop: space.sm, paddingBottom: space.lg,
    backgroundColor: color.surface, borderTopWidth: 1, borderTopColor: color.border,
    maxWidth: 480, width: "100%", alignSelf: "center",
  },
  chatStub: { flex: 1, backgroundColor: color.surfaceAlt, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: 13 },
  chatStubText: { color: color.textMuted, fontSize: font.size.md },
  chatSend: { width: 46, height: 46, borderRadius: 23, backgroundColor: color.primary, alignItems: "center", justifyContent: "center",
    ...( { backgroundImage: gradient.brand } as any ) },
  chatSendIcon: { color: "#fff", fontSize: 20, fontWeight: font.weight.bold as any },
});
