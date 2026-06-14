/**
 * StreamingMessage — 진행 중 어시스턴트 메시지(요구 4).
 *
 * delta 누적 텍스트 + section 세로 스택(템플릿 렌더러 §4 재사용) + 타이핑 인디케이터.
 * - 섹션은 도착 순서대로 스택, 모르는 kind는 SectionView/TemplateView가 text 폴백(§7, 요구 4.3·8.3).
 * - 수신 중(typing=true이거나 아직 내용 없음) 타이핑 인디케이터, done(streaming=false)이면 제거(요구 4.5).
 * - 진행 문구는 답변 중심만 — 내부 시스템·대기 상태는 노출하지 않는다(요구 4.6).
 */
import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';
import { SectionView } from './message';
import { FadeInView } from './motion';
import { color, font, radius, space } from '../design/tokens';
import type { Cta, MessageSection } from '../types/contract';

export function StreamingMessage({
  text,
  sections,
  streaming,
  onCta,
}: {
  text: string;
  sections: MessageSection[];
  streaming: boolean; // 수신 중이면 true
  onCta?: (c: Cta) => void;
}) {
  // 아직 아무것도 도착하지 않은 채 수신 중 → 순수 타이핑 인디케이터(답변 중심, 요구 4.6)
  const showTyping = streaming && !text && sections.length === 0;

  return (
    <View style={styles.row} testID="streaming-message">
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>AI</Text>
      </View>
      <View style={styles.col}>
        {showTyping ? (
          <View style={styles.bubble} testID="streaming-typing">
            <TypingDots />
          </View>
        ) : null}
        {text ? (
          <View style={styles.bubble} testID="streaming-text">
            <Text style={styles.text}>{text}</Text>
          </View>
        ) : null}
        {sections.map((s, i) => (
          <FadeInView key={i}>
            <SectionView section={s} onCta={onCta} />
          </FadeInView>
        ))}
      </View>
    </View>
  );
}

/** 타이핑 인디케이터 — 점 3개 페이드 루프. */
export function TypingDots() {
  const a = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(a, { toValue: 1, duration: 500, useNativeDriver: false }),
        Animated.timing(a, { toValue: 0, duration: 500, useNativeDriver: false }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [a]);
  const op = (lo: number) => a.interpolate({ inputRange: [0, 1], outputRange: [lo, 1] });
  return (
    <View style={styles.typing} testID="typing-dots">
      {[0.3, 0.5, 0.7].map((lo, i) => (
        <Animated.View key={i} style={[styles.typingDot, { opacity: op(lo) }]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: space.sm, marginBottom: space.sm, alignItems: 'flex-start' },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: color.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  avatarText: { color: color.primaryDark, fontWeight: font.weight.bold as any, fontSize: 11 },
  col: { flex: 1, gap: space.sm, alignItems: 'flex-start' },
  bubble: {
    backgroundColor: color.surface,
    borderWidth: 1,
    borderColor: color.border,
    paddingVertical: space.sm,
    paddingHorizontal: space.lg,
    borderTopLeftRadius: radius.sm,
    borderTopRightRadius: radius.lg,
    borderBottomLeftRadius: radius.lg,
    borderBottomRightRadius: radius.lg,
    maxWidth: '92%',
  },
  text: { color: color.text, fontSize: font.size.md, lineHeight: 22 },
  typing: { flexDirection: 'row', gap: 5, paddingVertical: 4 },
  typingDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: color.textMuted },
});
