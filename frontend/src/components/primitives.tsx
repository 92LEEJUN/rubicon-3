/** 기본 UI 프리미티브 — 토큰만 참조(One UI 스타일). RN 컴포넌트(웹=react-native-web). */
import React from "react";
import { Pressable, StyleSheet, Text, View, ViewStyle } from "react-native";
import { color, font, radius, space } from "../design/tokens";

export function Card({ children, style, testID }: { children: React.ReactNode; style?: ViewStyle; testID?: string }) {
  return <View testID={testID} style={[styles.card, style]}>{children}</View>;
}

export function Heading({ children }: { children: React.ReactNode }) {
  return <Text style={styles.heading}>{children}</Text>;
}
export function Title({ children }: { children: React.ReactNode }) {
  return <Text style={styles.title}>{children}</Text>;
}
export function Body({ children, muted }: { children: React.ReactNode; muted?: boolean }) {
  return <Text style={[styles.body, muted && { color: color.textSub }]}>{children}</Text>;
}
export function Caption({ children }: { children: React.ReactNode }) {
  return <Text style={styles.caption}>{children}</Text>;
}

type Tone = "neutral" | "primary" | "success" | "warning" | "danger";
const toneMap: Record<Tone, { bg: string; fg: string }> = {
  neutral: { bg: color.surfaceAlt, fg: color.textSub },
  primary: { bg: color.primaryTint, fg: color.primaryDark },
  success: { bg: color.successTint, fg: color.success },
  warning: { bg: color.warningTint, fg: color.warning },
  danger: { bg: color.dangerTint, fg: color.danger },
};

export function Badge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  const t = toneMap[tone];
  return (
    <View style={[styles.badge, { backgroundColor: t.bg }]}>
      <Text style={[styles.badgeText, { color: t.fg }]}>{label}</Text>
    </View>
  );
}

export function Button({ label, onPress, variant = "primary", testID }:
  { label: string; onPress?: () => void; variant?: "primary" | "secondary"; testID?: string }) {
  const primary = variant === "primary";
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.btn,
        primary ? styles.btnPrimary : styles.btnSecondary,
        pressed && { opacity: 0.85 },
      ]}
    >
      <Text style={[styles.btnText, primary ? { color: "#fff" } : { color: color.primaryDark }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: color.surface, borderRadius: radius.lg, padding: space.lg,
    borderWidth: 1, borderColor: color.border,
  },
  heading: { fontSize: font.size.xxl, fontWeight: font.weight.bold as any, color: color.text },
  title: { fontSize: font.size.lg, fontWeight: font.weight.semibold as any, color: color.text },
  body: { fontSize: font.size.md, color: color.text, lineHeight: 22 },
  caption: { fontSize: font.size.xs, color: color.textMuted },
  badge: { alignSelf: "flex-start", paddingHorizontal: space.sm, paddingVertical: 2, borderRadius: radius.pill },
  badgeText: { fontSize: font.size.xs, fontWeight: font.weight.semibold as any },
  btn: { borderRadius: radius.pill, paddingVertical: space.md, paddingHorizontal: space.xl, alignItems: "center" },
  btnPrimary: { backgroundColor: color.primary },
  btnSecondary: { backgroundColor: color.primaryTint },
  btnText: { fontSize: font.size.md, fontWeight: font.weight.semibold as any },
});
