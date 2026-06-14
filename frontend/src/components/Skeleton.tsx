/**
 * Skeleton — 로딩 자리표시(시머). 빈 화면 대신 형태를 먼저 보여준다(요구 3-1, ADR-0068).
 * reduced-motion이면 정적 박스(콘텐츠 동일). frontend-architecture §6 "스켈레톤 4종" 토대.
 */
import React from 'react';
import { View, ViewStyle } from 'react-native';
import { useReducedMotion } from 'framer-motion';
import { MotionView } from './motion';
import { color, radius as radiusToken, space } from '../design/tokens';

export function Skeleton({
  width,
  height = 14,
  radius = radiusToken.sm,
  style,
  testID = 'skeleton',
}: {
  width?: number | string;
  height?: number;
  radius?: number;
  style?: ViewStyle;
  testID?: string;
}) {
  const reduce = useReducedMotion();
  const base: ViewStyle = {
    width: (width as any) ?? '100%',
    height,
    borderRadius: radius,
    backgroundColor: color.surfaceAlt,
  };
  if (reduce) {
    return <View style={[base, style]} testID={testID} />;
  }
  return (
    <MotionView
      style={[base, style] as any}
      testID={testID}
      animate={{ opacity: [0.5, 1, 0.5] }}
      transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
    />
  );
}

/** 카드형 스켈레톤 — 제목+본문 2줄. 홈/추천 로딩 폴백. */
export function SkeletonCard({ testID = 'skeleton-card' }: { testID?: string }) {
  return (
    <View
      testID={testID}
      style={{
        backgroundColor: color.surface,
        borderRadius: radiusToken.lg,
        padding: space.lg,
        borderWidth: 1,
        borderColor: color.border,
        gap: space.sm,
      }}
    >
      <Skeleton width={'60%'} height={16} />
      <Skeleton width={'100%'} height={12} />
      <Skeleton width={'80%'} height={12} />
    </View>
  );
}
