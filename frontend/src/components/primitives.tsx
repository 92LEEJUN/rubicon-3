/** 기본 UI 프리미티브 — 토큰만 참조(One UI 스타일). RN 컴포넌트(웹=react-native-web). */
import React from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';
import { color, font, radius, shadow, space } from '../design/tokens';
import { spring, pressTap, hoverLift } from '../design/motion';
import { MotionPressable } from './motion';

export function Card({
  children,
  style,
  testID,
  onPress,
  elevated,
}: {
  children: React.ReactNode;
  style?: ViewStyle;
  testID?: string;
  onPress?: () => void;       // 주면 누름 가능한 카드(스프링 피드백)
  elevated?: boolean;         // 깊이 강조 그림자
}) {
  const cardStyle = [styles.card, elevated && (shadow.elevated as any), style];
  if (onPress) {
    return (
      <MotionPressable
        testID={testID}
        accessibilityRole="button"
        onPress={onPress}
        style={StyleSheet.flatten(cardStyle) as any}
        whileTap={pressTap}
        whileHover={hoverLift}
        transition={spring.press as any}
      >
        {children}
      </MotionPressable>
    );
  }
  return (
    <View testID={testID} style={cardStyle}>
      {children}
    </View>
  );
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

type Tone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger';
const toneMap: Record<Tone, { bg: string; fg: string }> = {
  neutral: { bg: color.surfaceAlt, fg: color.textSub },
  primary: { bg: color.primaryTint, fg: color.primaryDark },
  success: { bg: color.successTint, fg: color.success },
  warning: { bg: color.warningTint, fg: color.warning },
  danger: { bg: color.dangerTint, fg: color.danger },
};

export function Badge({ label, tone = 'neutral' }: { label: string; tone?: Tone }) {
  const t = toneMap[tone];
  return (
    <View style={[styles.badge, { backgroundColor: t.bg }]}>
      <Text style={[styles.badgeText, { color: t.fg }]}>{label}</Text>
    </View>
  );
}

export function Button({
  label,
  onPress,
  variant = 'primary',
  testID,
}: {
  label: string;
  onPress?: () => void;
  variant?: 'primary' | 'secondary';
  testID?: string;
}) {
  const primary = variant === 'primary';
  return (
    <MotionPressable
      testID={testID}
      accessibilityRole="button"
      onPress={onPress}
      style={StyleSheet.flatten([styles.btn, primary ? styles.btnPrimary : styles.btnSecondary]) as any}
      whileTap={pressTap}
      whileHover={hoverLift}
      transition={spring.press as any}
    >
      <Text style={[styles.btnText, primary ? { color: '#fff' } : { color: color.primaryDark }]}>
        {label}
      </Text>
    </MotionPressable>
  );
}

const styles = StyleSheet.create({
  // 토스st 카드 — 보더 없이 아주 부드러운 섀도우로 분리, 큰 라운드.
  card: {
    backgroundColor: color.surface,
    borderRadius: radius.xl,
    padding: space.xl,
    ...(shadow.card as any),
  },
  heading: {
    fontSize: font.size.display,
    fontWeight: font.weight.bold as any,
    color: color.text,
    lineHeight: 40,
  },
  title: { fontSize: font.size.lg, fontWeight: font.weight.bold as any, color: color.text },
  body: { fontSize: font.size.md, color: color.textSub, lineHeight: 23 },
  caption: { fontSize: font.size.xs, color: color.textMuted, fontWeight: font.weight.medium as any },
  badge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.pill,
  },
  badgeText: { fontSize: font.size.xs, fontWeight: font.weight.bold as any },
  // 토스st 버튼 — 큰 라운드(14)·넉넉한 높이·볼드.
  btn: {
    borderRadius: 14,
    paddingVertical: 15,
    paddingHorizontal: space.xl,
    alignItems: 'center',
  },
  btnPrimary: { backgroundColor: color.primary },
  btnSecondary: { backgroundColor: color.primaryTint },
  btnText: { fontSize: font.size.lg, fontWeight: font.weight.bold as any },
});
