/**
 * DeviceDeck — 3D 스택 스와이프 카드 덱(ADR-0068). 토스st 위에 입체감·모션을 더한다.
 *
 * - 뒤 카드 2장이 작게 겹쳐 **스택(깊이)** 을 만든다.
 * - 앞 카드는 **드래그(framer drag)** — 드래그 x에 따라 rotateY/Z **3D 틸트**(perspective).
 * - 임계 넘기면 옆으로 **날아가고**(opacity 0) 다음 카드가 **팝인**(spring scale)으로 올라온다.
 * - 카드엔 실제 기기 사진 + 톤별 그라데이션 오버레이(가독성·통일감). 탭 → onPick(질문).
 * 모션은 표현 계층 — reduced-motion/테스트에선 정적으로 콘텐츠만 렌더된다.
 */
import React, { useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from 'framer-motion';
import { DEVICE_IMAGE } from '../design/deviceImages';
import { color, font, radius, shadow, space } from '../design/tokens';

const MotionView = motion.create(View as any);

export type DeckItem = {
  tone: 'warning' | 'danger' | 'primary';
  tag: string;
  title: string;
  desc: string;
  cta: string;
  ask: string;
  deviceType?: string;
};

// 톤별 비주얼 — 사진을 살리되(위) 아래로 갈수록 스크림으로 가독성 확보. solid=글로우/CTA 텍스트색.
const TONE: Record<string, { tint: string; scrim: string; solid: string; text: string }> = {
  danger: {
    tint: 'rgba(240,68,82,0.28)',
    scrim:
      'linear-gradient(180deg, rgba(120,16,26,0) 0%, rgba(120,16,26,0.12) 34%, rgba(150,22,33,0.95) 100%)',
    solid: '#F04452',
    text: '#E5384A',
  },
  warning: {
    tint: 'rgba(255,138,0,0.26)',
    scrim:
      'linear-gradient(180deg, rgba(120,64,0,0) 0%, rgba(120,64,0,0.12) 34%, rgba(150,80,0,0.95) 100%)',
    solid: '#FF8A00',
    text: '#D87400',
  },
  primary: {
    tint: 'rgba(49,130,246,0.26)',
    scrim:
      'linear-gradient(180deg, rgba(12,48,120,0) 0%, rgba(12,48,120,0.12) 34%, rgba(14,54,140,0.96) 100%)',
    solid: '#3182F6',
    text: '#1B64DA',
  },
};

const DECK_EMOJI: Record<string, string> = {
  washer: '🧺',
  refrigerator: '❄️',
  air_purifier: '🌀',
};

function CardFace({ item }: { item: DeckItem }) {
  const img = item.deviceType ? DEVICE_IMAGE[item.deviceType] : undefined;
  const emoji = item.deviceType ? DECK_EMOJI[item.deviceType] : undefined;
  const t = TONE[item.tone];
  return (
    <>
      {img ? (
        <Image source={{ uri: img }} style={styles.photo} resizeMode="cover" />
      ) : (
        <View style={[styles.photo, { backgroundColor: t.solid }]} />
      )}
      {/* 톤 워시(브랜드색) + 하단 스크림(가독성) — 사진은 위쪽에서 살아 보인다 */}
      <View style={[styles.fill, { backgroundColor: t.tint }]} pointerEvents="none" />
      <View style={[styles.fill, { backgroundImage: t.scrim } as any]} pointerEvents="none" />
      <View style={styles.faceContent}>
        <View style={styles.topRow}>
          <View style={styles.tag}>
            <Text style={styles.tagText}>{item.tag}</Text>
          </View>
          {emoji ? (
            <View style={styles.glassBadge}>
              <Text style={styles.glassEmoji}>{emoji}</Text>
            </View>
          ) : null}
        </View>
        <View style={{ flex: 1 }} />
        <Text style={styles.title} numberOfLines={2}>
          {item.title}
        </Text>
        <Text style={styles.desc} numberOfLines={2}>
          {item.desc}
        </Text>
        <View style={styles.ctaPill}>
          <Text style={[styles.ctaPillText, { color: t.text }]}>{item.cta}</Text>
          <Text style={[styles.ctaPillChev, { color: t.text }]}>›</Text>
        </View>
      </View>
    </>
  );
}

export function DeviceDeck({
  items,
  onPick,
  height = 230,
}: {
  items: DeckItem[];
  onPick?: (ask: string) => void;
  height?: number;
}) {
  const [i, setI] = useState(0);
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const sc = useMotionValue(1);
  const rotateY = useTransform(x, [-220, 220], [16, -16]);
  const rotateZ = useTransform(x, [-220, 220], [-7, 7]);
  const opacity = useTransform(x, [-340, -180, 0, 180, 340], [0, 1, 1, 1, 0]);

  if (!items.length) return null;
  const n = items.length;
  const front = items[i];
  const second = items[(i + 1) % n];
  const third = items[(i + 2) % n];

  function advance(dir: number) {
    animate(x, dir * 600, { duration: 0.22, ease: [0.4, 0, 1, 1] }).then(() => {
      setI((v) => (v + 1) % n);
      x.set(0);
      sc.set(0.92);
      animate(sc, 1, { type: 'spring', stiffness: 320, damping: 22 });
    });
  }

  // reduced-motion: 정적 단일 카드(스택/3D 없이) — 탭만.
  if (reduce) {
    return (
      <View style={styles.wrap}>
        <View style={[styles.card, styles.staticCard, { height }]} testID="device-deck">
          <CardFace item={front} />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <View style={[styles.deck, { height }]}>
        {n > 2 ? (
          <View style={[styles.card, styles.behind2, { height }]} pointerEvents="none">
            <CardFace item={third} />
          </View>
        ) : null}
        {n > 1 ? (
          <View style={[styles.card, styles.behind1, { height }]} pointerEvents="none">
            <CardFace item={second} />
          </View>
        ) : null}
        <MotionView
          testID="device-deck"
          style={
            {
              ...StyleSheet.flatten(styles.card),
              height,
              // 톤 컬러 글로우 — 카드가 떠 보이게
              shadowColor: TONE[front.tone].solid,
              shadowOpacity: 0.4,
              shadowRadius: 30,
              shadowOffset: { width: 0, height: 16 },
              x,
              scale: sc,
              rotateY,
              rotateZ,
              opacity,
              transformPerspective: 1100,
              cursor: 'grab',
            } as any
          }
          drag="x"
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.7}
          onDragEnd={(_e: any, info: any) => {
            if (Math.abs(info.offset.x) > 100) advance(info.offset.x > 0 ? 1 : -1);
            else animate(x, 0, { type: 'spring', stiffness: 400, damping: 30 });
          }}
          onClick={() => {
            if (Math.abs(x.get()) < 6) onPick?.(front.ask);
          }}
        >
          <CardFace item={front} />
        </MotionView>
      </View>
      {n > 1 ? (
        <View style={styles.dots}>
          {items.map((_, k) => (
            <View key={k} style={[styles.dot, k === i && styles.dotOn]} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: space.sm },
  deck: { position: 'relative' },
  card: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    borderRadius: 24,
    overflow: 'hidden',
    backgroundColor: color.primaryDark,
    ...(shadow.elevated as any),
  },
  staticCard: { position: 'relative' },
  behind1: { transform: [{ scale: 0.95 }, { translateY: -14 }] as any, opacity: 0.92 },
  behind2: { transform: [{ scale: 0.9 }, { translateY: -28 }] as any, opacity: 0.78 },
  photo: { ...StyleSheet.absoluteFillObject, width: '100%', height: '100%' },
  fill: { ...StyleSheet.absoluteFillObject },
  faceContent: { flex: 1, padding: space.xl },
  topRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  tag: {
    backgroundColor: 'rgba(255,255,255,0.22)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.pill,
    // @ts-expect-error web-only: 글래스 블러
    backdropFilter: 'blur(8px)',
  },
  tagText: { color: '#fff', fontSize: font.size.xs, fontWeight: font.weight.bold as any },
  glassBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.22)',
    // @ts-expect-error web-only: 글래스 블러
    backdropFilter: 'blur(8px)',
  },
  glassEmoji: { fontSize: 20 },
  title: {
    color: '#fff',
    fontSize: font.size.xxl,
    fontWeight: font.weight.bold as any,
    lineHeight: 32,
    // @ts-expect-error web-only: 텍스트 가독성 그림자
    textShadow: '0 1px 12px rgba(0,0,0,0.25)',
  },
  desc: { color: 'rgba(255,255,255,0.95)', fontSize: font.size.md, lineHeight: 22, marginTop: 6 },
  ctaPill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: '#fff',
    borderRadius: radius.pill,
    paddingHorizontal: space.lg,
    paddingVertical: 9,
    marginTop: space.lg,
  },
  ctaPillText: { fontSize: font.size.sm, fontWeight: font.weight.bold as any },
  ctaPillChev: { fontSize: 17, fontWeight: font.weight.bold as any, marginLeft: 3 },
  dots: { flexDirection: 'row', gap: 6, justifyContent: 'center', marginTop: space.md },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: color.border },
  dotOn: { width: 20, backgroundColor: color.primary },
});
