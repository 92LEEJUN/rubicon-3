/** 세그먼트 토글 — 홈 ↔ 고객지원(CS) 전환(One UI 스타일 pill). */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { color, font, radius, space } from "../design/tokens";

export interface TabOption<K extends string = string> { key: K; label: string; }

export function SegmentedTabs<K extends string>({ options, value, onChange }:
  { options: TabOption<K>[]; value: K; onChange: (k: K) => void }) {
  return (
    <View style={styles.bar} accessibilityRole="tablist">
      {options.map((o) => {
        const active = o.key === value;
        return (
          <Pressable
            key={o.key}
            testID={`tab-${o.key}`}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            onPress={() => onChange(o.key)}
            style={[styles.seg, active && styles.segActive]}
          >
            <Text style={[styles.text, active && styles.textActive]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: "row", backgroundColor: color.surfaceAlt, borderRadius: radius.pill, padding: 4, gap: 4 },
  seg: { flex: 1, paddingVertical: space.sm, alignItems: "center", borderRadius: radius.pill },
  segActive: { backgroundColor: color.surface, shadowColor: "#000", shadowOpacity: 0.08, shadowRadius: 6, shadowOffset: { width: 0, height: 2 } },
  text: { fontSize: font.size.md, fontWeight: font.weight.medium as any, color: color.textSub },
  textActive: { color: color.primaryDark, fontWeight: font.weight.semibold as any },
});
