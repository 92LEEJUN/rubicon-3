/** 데모 모드 표시(ADR-0051) — BE 미연결(mock)일 때 작은 비차단 배지 + 데모 초기화. */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { color, font, radius, space } from "../design/tokens";
import { mockStore } from "../mock/store";

export function DemoBadge() {
  function reset() {
    mockStore.reset();
    try { window.location.reload(); } catch { /* noop */ }
  }
  return (
    <View style={styles.wrap} pointerEvents="box-none" testID="demo-badge">
      <View style={styles.pill}>
        <Text style={styles.dot}>●</Text>
        <Text style={styles.label}>데모 모드 (BE 미연결)</Text>
        <Pressable onPress={reset} testID="demo-reset" accessibilityRole="button">
          <Text style={styles.reset}>초기화</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", bottom: space.md, alignSelf: "center", width: "100%", alignItems: "center" },
  pill: {
    flexDirection: "row", alignItems: "center", gap: space.sm,
    backgroundColor: color.text, borderRadius: radius.pill,
    paddingHorizontal: space.md, paddingVertical: space.xs, opacity: 0.92,
  },
  dot: { color: "#36D399", fontSize: 8 },
  label: { color: color.bg, fontSize: font.size.xs, fontWeight: "600" },
  reset: { color: "#9DC2FF", fontSize: font.size.xs, fontWeight: "700" },
});
