/** 아키텍처 문서 탭 — BE/BFF/FE 계층 가이드를 텍스트로 열람(이미지·시각화 없음).
 *  문서 원본(../../docs/*.md)을 ?raw로 번들해 그대로 렌더한다(SoT는 docs/). */
import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { color, font, radius, space } from "../design/tokens";
import beDoc from "../../../docs/backend-architecture.md?raw";
import bffDoc from "../../../docs/bff-architecture.md?raw";
import feDoc from "../../../docs/frontend-architecture.md?raw";

type DocKey = "be" | "bff" | "fe";
const DOCS: { key: DocKey; label: string; body: string }[] = [
  { key: "be", label: "Backend", body: beDoc },
  { key: "bff", label: "BFF", body: bffDoc },
  { key: "fe", label: "Frontend", body: feDoc },
];

export function Docs({ onClose }: { onClose?: () => void }) {
  const [key, setKey] = useState<DocKey>("be");
  const doc = DOCS.find((d) => d.key === key)!;
  return (
    <View style={styles.root} testID="screen-docs">
      <View style={styles.header}>
        <View style={styles.topRow}>
          <Text style={styles.title}>아키텍처 문서</Text>
          {onClose && (
            <Pressable onPress={onClose} testID="docs-close" accessibilityRole="button">
              <Text style={styles.close}>닫기</Text>
            </Pressable>
          )}
        </View>
        <View style={styles.tabs}>
          {DOCS.map((d) => (
            <Pressable
              key={d.key}
              onPress={() => setKey(d.key)}
              testID={`docs-tab-${d.key}`}
              accessibilityRole="tab"
              style={[styles.tab, d.key === key && styles.tabActive]}>
              <Text style={[styles.tabLabel, d.key === key && styles.tabLabelActive]}>{d.label}</Text>
            </Pressable>
          ))}
        </View>
      </View>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollInner} testID="docs-body">
        <Text style={styles.mono} selectable>
          {doc.body}
        </Text>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  header: {
    paddingHorizontal: space.lg, paddingTop: space.lg, paddingBottom: space.sm,
    backgroundColor: color.bg, borderBottomWidth: 1, borderBottomColor: color.border,
    maxWidth: 820, width: "100%", alignSelf: "center",
  },
  topRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { fontSize: font.size.lg, fontWeight: "700", color: color.text },
  close: { fontSize: font.size.sm, color: color.textMuted },
  tabs: { flexDirection: "row", gap: space.xs, marginTop: space.md },
  tab: {
    paddingHorizontal: space.md, paddingVertical: space.xs,
    borderRadius: radius.pill, backgroundColor: color.surfaceAlt,
  },
  tabActive: { backgroundColor: color.text },
  tabLabel: { fontSize: font.size.sm, color: color.text },
  tabLabelActive: { color: color.bg, fontWeight: "700" },
  scroll: { flex: 1, maxWidth: 820, width: "100%", alignSelf: "center" },
  scrollInner: { padding: space.lg },
  mono: {
    fontFamily: "monospace",
    fontSize: 12,
    lineHeight: 18,
    color: color.text,
  },
});
