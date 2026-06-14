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

// 톤별 오버레이 그라데이션(사진 위에 깔아 가독성·통일감 확보).
const OVERLAY: Record<string, string> = {
  danger: 'linear-gradient(155deg, rgba(240,68,82,0.82) 0%, rgba(189,33,48,0.94) 100%)',
  warning: 'linear-gradient(155deg, rgba(255,138,0,0.82) 0%, rgba(214,104,0,0.94) 100%)',
  primary: 'linear-gradient(155deg, rgba(49,130,246,0.82) 0%, rgba(20,86,196,0.95) 100%)',
};

function CardFace({ item }: { item: DeckItem }) {
  const img = item.deviceType ? DEVICE_IMAGE[item.deviceType] : undefined;
  return (
    <>
      {img ? <Image source={{ uri: img }} style={styles.photo} resizeMode="cover" /> : null}
      <View style={[styles.overlay, { backgroundImage: OVERLAY[item.tone] } as any]} />
      <View style={styles.faceContent}>
        <View style={styles.tag}>
          <Text style={styles.tagText}>{item.tag}</Text>
        </View>
        <View style={{ flex: 1 }} />
        <Text style={styles.title} numberOfLines={2}>
          {item.title}
        </Text>
        <Text style={styles.desc} numberOfLines={2}>
          {item.desc}
        </Text>
        <View style={styles.ctaRow}>
          <Text style={styles.cta}>{item.cta}</Text>
          <Text style={styles.chev}>›</Text>
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
    borderRadius: radius.xl,
    overflow: 'hidden',
    backgroundColor: color.primaryDark,
    ...(shadow.elevated as any),
  },
  staticCard: { position: 'relative' },
  behind1: { transform: [{ scale: 0.95 }, { translateY: -14 }] as any, opacity: 0.92 },
  behind2: { transform: [{ scale: 0.9 }, { translateY: -28 }] as any, opacity: 0.78 },
  photo: { ...StyleSheet.absoluteFillObject, width: '100%', height: '100%' },
  overlay: { ...StyleSheet.absoluteFillObject },
  faceContent: { flex: 1, padding: space.xl },
  tag: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.24)',
    paddingHorizontal: 11,
    paddingVertical: 5,
    borderRadius: radius.pill,
  },
  tagText: { color: '#fff', fontSize: font.size.xs, fontWeight: font.weight.bold as any },
  title: {
    color: '#fff',
    fontSize: font.size.xxl,
    fontWeight: font.weight.bold as any,
    lineHeight: 32,
  },
  desc: { color: 'rgba(255,255,255,0.92)', fontSize: font.size.md, lineHeight: 22, marginTop: 6 },
  ctaRow: { flexDirection: 'row', alignItems: 'center', marginTop: space.md },
  cta: { color: '#fff', fontSize: font.size.md, fontWeight: font.weight.bold as any },
  chev: { color: '#fff', fontSize: 20, fontWeight: font.weight.bold as any, marginLeft: 2 },
  dots: { flexDirection: 'row', gap: 6, justifyContent: 'center', marginTop: space.md },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: color.border },
  dotOn: { width: 20, backgroundColor: color.primary },
});
