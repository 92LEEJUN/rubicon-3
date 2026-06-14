/**
 * ReEngagementBanner — 선제 재관여 배너(요구 3).
 *
 * primary_label·message·also_count 노출, 탭 → onOpen(primary_ref)로 /chat 재진입(proactive→reactive),
 * 닫기 → onDismiss. 노출 여부·deliver·동의 게이트는 useReEngagement가 책임(여기선 표현만).
 */
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useReducedMotion } from 'framer-motion';
import { MotionView } from './motion';
import { slideInDown } from '../design/motion';
import { color, font, radius, space } from '../design/tokens';
import type { ReEngagement } from '../types/contract';

export function ReEngagementBanner({
  banner,
  onOpen,
  onDismiss,
}: {
  banner: ReEngagement;
  onOpen?: (ref?: string) => void;
  onDismiss?: () => void;
}) {
  const also = banner.also_count ?? 0;
  const reduce = useReducedMotion();
  return (
    <MotionView
      style={styles.banner as any}
      testID="reengagement-banner"
      initial={reduce ? false : slideInDown.hidden}
      animate={reduce ? undefined : slideInDown.show}
      exit={reduce ? undefined : slideInDown.exit}
    >
      <Pressable
        testID="reengagement-open"
        accessibilityRole="button"
        onPress={() => onOpen?.(banner.primary_ref)}
        style={styles.main}
      >
        <View style={styles.dot} />
        <View style={{ flex: 1 }}>
          {banner.primary_label ? (
            <Text style={styles.label} testID="reengagement-label">
              {banner.primary_label}
            </Text>
          ) : null}
          {banner.message ? (
            <Text style={styles.message} testID="reengagement-message">
              {banner.message}
            </Text>
          ) : null}
          {also > 0 ? (
            <Text style={styles.also} testID="reengagement-also">
              외 {also}건 더 있어요
            </Text>
          ) : null}
        </View>
      </Pressable>
      <Pressable
        testID="reengagement-dismiss"
        accessibilityRole="button"
        onPress={onDismiss}
        style={styles.close}
      >
        <Text style={styles.closeIcon}>×</Text>
      </Pressable>
    </MotionView>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: color.primaryTint,
    borderRadius: radius.lg,
    padding: space.md,
    gap: space.sm,
    marginBottom: space.md,
  },
  main: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flex: 1 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: color.primary },
  label: {
    fontSize: font.size.md,
    fontWeight: font.weight.semibold as any,
    color: color.primaryDark,
  },
  message: { fontSize: font.size.sm, color: color.text, lineHeight: 20, marginTop: 2 },
  also: { fontSize: font.size.xs, color: color.textSub, marginTop: 2 },
  close: { width: 28, height: 28, alignItems: 'center', justifyContent: 'center' },
  closeIcon: { fontSize: 20, color: color.textMuted, lineHeight: 22 },
});
