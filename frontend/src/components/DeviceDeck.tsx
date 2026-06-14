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
import { CARD_IMAGE, DEVICE_IMAGE } from '../design/deviceImages';
import { color, font, radius, shadow, space } from '../design/tokens';

const MotionView = motion.create(View as any);

export type DeckItem = {
  palette: string; // PALETTES 키
  tag: string;
  title: string;
  desc: string;
  cta: string;
  ask: string;
  deviceType?: string; // 기기 사진 + 이모지 배지
  img?: string; // CARD_IMAGE 키(주제 사진) — deviceType 사진보다 우선
};

// 다크 엘레강트 팔레트 — 사진은 자연색 그대로(어두운 스크림만), 색은 **작은 액센트**로만.
// accent: 태그 점·글로우. text: 흰 CTA 알약의 글자색. bg: 사진 없는 카드의 깊은(muted) 그라데이션.
type Palette = { accent: string; text: string; bg: string };
const PALETTES: Record<string, Palette> = {
  blue: { accent: '#3E7BFA', text: '#1B64DA', bg: 'linear-gradient(155deg, #243B6B 0%, #0E1730 100%)' },
  teal: { accent: '#12B886', text: '#0B8F6B', bg: 'linear-gradient(155deg, #15463C 0%, #0A201C 100%)' },
  violet: { accent: '#845EF7', text: '#6741D9', bg: 'linear-gradient(155deg, #352453 0%, #170E27 100%)' },
  amber: { accent: '#E8943A', text: '#B5701C', bg: 'linear-gradient(155deg, #3E2E1B 0%, #1F160E 100%)' },
  rose: { accent: '#E8638A', text: '#C24668', bg: 'linear-gradient(155deg, #43253A 0%, #24121F 100%)' },
  indigo: { accent: '#5C7CFA', text: '#3B5BDB', bg: 'linear-gradient(155deg, #262F5A 0%, #121633 100%)' },
  emerald: { accent: '#2BA471', text: '#1B8157', bg: 'linear-gradient(155deg, #143A2A 0%, #0A2018 100%)' },
};

// 중립 다크 스크림 — 사진 카드(자연색 유지)·솔리드 카드용. 위는 투명, 아래로 갈수록 어둡게.
const SCRIM_PHOTO =
  'linear-gradient(180deg, rgba(15,17,22,0) 0%, rgba(15,17,22,0.30) 46%, rgba(11,13,18,0.90) 100%)';
const SCRIM_SOLID =
  'linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.10) 52%, rgba(0,0,0,0.40) 100%)';
const TOP_SCRIM = 'linear-gradient(180deg, rgba(0,0,0,0.22) 0%, rgba(0,0,0,0) 26%)';

const DECK_EMOJI: Record<string, string> = {
  washer: '🧺',
  refrigerator: '❄️',
  air_purifier: '🌀',
};

function CardFace({ item }: { item: DeckItem }) {
  const img =
    (item.img ? CARD_IMAGE[item.img] : undefined) ??
    (item.deviceType ? DEVICE_IMAGE[item.deviceType] : undefined);
  const emoji = item.deviceType ? DECK_EMOJI[item.deviceType] : undefined;
  const p = PALETTES[item.palette] ?? PALETTES.blue;
  return (
    <>
      {img ? (
        <Image source={{ uri: img }} style={styles.photo} resizeMode="cover" />
      ) : (
        <View style={[styles.photo, { backgroundImage: p.bg } as any]} />
      )}
      {img ? <View style={[styles.fill, { backgroundImage: TOP_SCRIM } as any]} pointerEvents="none" /> : null}
      <View
        style={[styles.fill, { backgroundImage: img ? SCRIM_PHOTO : SCRIM_SOLID } as any]}
        pointerEvents="none"
      />
      <View style={styles.faceContent}>
        <View style={styles.topRow}>
          <View style={styles.tag}>
            <View style={[styles.tagDot, { backgroundColor: p.accent }]} />
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
          <Text style={[styles.ctaPillText, { color: p.text }]}>{item.cta}</Text>
          <Text style={[styles.ctaPillChev, { color: p.text }]}>›</Text>
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
              // 은은한 액센트 글로우 — 카드가 떠 보이게(과하지 않게)
              shadowColor: (PALETTES[front.palette] ?? PALETTES.blue).accent,
              shadowOpacity: 0.26,
              shadowRadius: 28,
              shadowOffset: { width: 0, height: 14 },
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
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    backgroundColor: 'rgba(255,255,255,0.18)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.pill,
    // @ts-expect-error web-only: 글래스 블러
    backdropFilter: 'blur(8px)',
  },
  tagDot: { width: 7, height: 7, borderRadius: 4 },
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
