/**
 * 모션 프리미티브 — framer-motion × react-native-web(ADR-0068).
 *
 * `motion.create(View)`로 RNW 컴포넌트를 모션 래핑한다(transform/opacity는 framer가 DOM 노드에
 * 직접 적용 → RNW 스타일과 충돌 없음). **reduced-motion 존중**: 활성 시 정적 렌더(콘텐츠 동일).
 * 모션은 표현 계층이라 비활성·테스트에서도 자식 콘텐츠·기능은 동일하다(요구 4-1·4-2).
 */
import React from 'react';
import { Pressable, StyleSheet, View, ViewStyle } from 'react-native';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { fadeInUp, hoverLift, pressTap, spring, staggerParent } from '../design/motion';

export const MotionView = motion.create(View as any);
export const MotionPressable = motion.create(Pressable as any);
export { AnimatePresence };

// framer-motion은 `style`을 CSS 객체로 다룬다 — RN 배열 스타일을 넘기면 인덱스 순회로 깨진다.
// Motion* 컴포넌트에 넘기기 전 항상 단일 객체로 평탄화한다.
const flat = (s?: ViewStyle | ViewStyle[]) => StyleSheet.flatten(s) as any;

type Kids = { children: React.ReactNode; style?: ViewStyle | ViewStyle[]; testID?: string };

/** 마운트 시 fadeInUp 등장. reduced-motion이면 즉시 표시. */
export function FadeInView({ children, style, testID, delay = 0 }: Kids & { delay?: number }) {
  const reduce = useReducedMotion();
  if (reduce) {
    return (
      <View style={style} testID={testID}>
        {children}
      </View>
    );
  }
  return (
    <MotionView
      style={flat(style)}
      testID={testID}
      initial={fadeInUp.hidden}
      animate={fadeInUp.show}
      transition={{ ...fadeInUp.show.transition, delay }}
    >
      {children}
    </MotionView>
  );
}

/** 자식(StaggerItem)을 순차 등장시키는 부모 컨테이너. */
export function Stagger({ children, style, testID, stagger = 0.06 }: Kids & { stagger?: number }) {
  const reduce = useReducedMotion();
  if (reduce) {
    return (
      <View style={style} testID={testID}>
        {children}
      </View>
    );
  }
  return (
    <MotionView
      style={flat(style)}
      testID={testID}
      initial="hidden"
      animate="show"
      variants={staggerParent(stagger)}
    >
      {children}
    </MotionView>
  );
}

/** Stagger 자식 1개 — 부모 타이밍에 맞춰 fadeInUp. */
export function StaggerItem({ children, style, testID }: Kids) {
  const reduce = useReducedMotion();
  if (reduce) {
    return (
      <View style={style} testID={testID}>
        {children}
      </View>
    );
  }
  return (
    <MotionView style={flat(style)} testID={testID} variants={fadeInUp}>
      {children}
    </MotionView>
  );
}

/** 스프링 누름(+호버 lift) 피드백 Pressable. onPress·접근성은 그대로 유지. */
export function PressableScale({
  children,
  onPress,
  style,
  testID,
  accessibilityRole = 'button',
  lift = true,
}: Kids & {
  onPress?: () => void;
  accessibilityRole?: any;
  lift?: boolean;
}) {
  const reduce = useReducedMotion();
  if (reduce) {
    return (
      <Pressable
        onPress={onPress}
        style={style as any}
        testID={testID}
        accessibilityRole={accessibilityRole}
      >
        {children}
      </Pressable>
    );
  }
  return (
    <MotionPressable
      onPress={onPress}
      style={flat(style)}
      testID={testID}
      accessibilityRole={accessibilityRole}
      whileTap={pressTap}
      whileHover={lift ? hoverLift : undefined}
      transition={spring.press as any}
    >
      {children}
    </MotionPressable>
  );
}
