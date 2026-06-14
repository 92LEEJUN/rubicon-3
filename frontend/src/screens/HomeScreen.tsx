/** S1 홈 — 토스(Toss)st 재설계: 큰 인사 + 퀵액션 + 클린 리스트 카드(ADR-0068).
 *
 * home_summary(devices·alerts·recommendations)에서 콘텐츠를 파생한다(실데이터/fixture 폴백).
 * 하단 채팅바는 MainShell이 고정 렌더. 카드/행 탭 → 맥락 질문으로 채팅 진입.
 * 비주얼: 화이트 표면·토스 블루 단일 액센트·큰 볼드 타이포·아주 부드러운 섀도우·넉넉한 여백.
 */
import React from 'react';
import { Image, ScrollView, StyleSheet, Text, View } from 'react-native';
import { TemplateView } from '../templates';
import { FadeInView, PressableScale, Stagger, StaggerItem } from '../components/motion';
import { DeviceDeck, type DeckItem } from '../components/DeviceDeck';
import { DEVICE_IMAGE } from '../design/deviceImages';
import { color, font, radius, shadow, space } from '../design/tokens';

const DEVICE_KO: Record<string, string> = {
  washer: '세탁기',
  refrigerator: '냉장고',
  air_purifier: '공기청정기',
};
const DEVICE_ICON: Record<string, string> = {
  washer: '🧺',
  refrigerator: '❄️',
  air_purifier: '🌀',
};
const CONS_KO: Record<string, string> = {
  drain_filter: '배수 필터',
  water_filter: '정수필터',
  hepa_filter: 'HEPA 필터',
};

type Tile = { icon: string; type: string; tint: string; title: string; sub: string; ok?: boolean; ask: string };

function buildBriefings(data: any): DeckItem[] {
  const out: DeckItem[] = [];
  for (const d of data.devices ?? []) {
    if (d.status !== 'ONLINE') {
      const c =
        (d.consumables ?? []).find((x: any) => x.life_remaining <= x.threshold) ??
        (d.consumables ?? [])[0];
      const pct = c ? Math.round(c.life_remaining * 100) : null;
      out.push({
        tone: 'danger',
        tag: '⚠ 점검 필요',
        title: `${DEVICE_KO[d.type] ?? d.type} 배수 이상 · 5C`,
        desc:
          pct != null
            ? `${CONS_KO[c.name] ?? '소모품'} 수명 ${pct}%. 지금 청소·교체하면 오류를 예방할 수 있어요.`
            : '상태 확인이 필요해요.',
        cta: '해결 방법 보기',
        ask: `${DEVICE_KO[d.type] ?? d.type}에서 물이 안 빠져요. 5C 떠요. 해결하고 부품도 주문할래요.`,
        deviceType: d.type,
      });
    }
  }
  for (const a of data.alerts ?? []) {
    const d = (data.devices ?? []).find((x: any) => x.id === a.device_id);
    const name = d ? (DEVICE_KO[d.type] ?? d.type) : '기기';
    out.push({
      tone: a.severity === 'warning' ? 'warning' : 'primary',
      tag: a.severity === 'warning' ? '🔧 소모품 알림' : 'ⓘ 안내',
      title: `${name} 소모품 교체 시기`,
      desc: a.detail,
      cta: '교체·주문 안내',
      ask: `${name} 소모품 교체 방법 알려주고 주문도 도와줘`,
      deviceType: d?.type,
    });
  }
  return out;
}

function buildTiles(data: any): Tile[] {
  const tiles: Tile[] = [];
  for (const d of data.devices ?? []) {
    const ok = d.status === 'ONLINE';
    tiles.push({
      icon: DEVICE_ICON[d.type] ?? '📱',
      type: d.type,
      tint: ok ? color.successTint : color.dangerTint,
      title: `${DEVICE_KO[d.type] ?? d.type}`,
      sub: d.model,
      ok,
      ask: `${DEVICE_KO[d.type] ?? d.type} 상태 확인해줘`,
    });
  }
  return tiles;
}

const QUICK = [
  { icon: '🩺', label: '진단', tint: color.primaryTint, ask: '우리집 가전 상태 진단해줘' },
  { icon: '📦', label: '부품주문', tint: '#FFF0E8', ask: '세탁기 배수 필터 주문할래요' },
  { icon: '🏠', label: '방문예약', tint: '#EAF6FF', ask: '방문 수리 예약하고 싶어요' },
  { icon: '✨', label: '추천', tint: '#F1EEFF', ask: '맞춤 제품 추천해줘' },
];

export function HomeScreen({
  data,
  onOpenChat,
}: {
  data: any;
  onOpenChat?: (q?: string) => void;
  onGallery?: () => void;
}) {
  const briefings = buildBriefings(data);
  const tiles = buildTiles(data);
  const recs: any[] = data.recommendations ?? [];

  return (
    <View style={styles.root} testID="screen-home">
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* 큰 인사 */}
        <FadeInView>
          <Text style={styles.greeting}>안녕하세요, 준희님 👋</Text>
          <Text style={styles.greetingSub}>오늘 챙기면 좋을 것들을 모았어요</Text>
        </FadeInView>

        {/* 퀵 액션 — 둥근 아이콘 4개 */}
        <Stagger style={styles.quickRow} testID="quick-actions">
          {QUICK.map((q, i) => (
            <StaggerItem key={i} style={styles.quickItemWrap}>
              <PressableScale
                testID={`quick-${i}`}
                onPress={() => onOpenChat?.(q.ask)}
                style={styles.quickItem}
                lift={false}
              >
                <View style={[styles.quickChip, { backgroundColor: q.tint }]}>
                  <Text style={styles.quickIcon}>{q.icon}</Text>
                </View>
                <Text style={styles.quickLabel}>{q.label}</Text>
              </PressableScale>
            </StaggerItem>
          ))}
        </Stagger>

        {/* 오늘 챙길 것 — 3D 스택 스와이프 덱(실사진 + 틸트) */}
        {briefings.length ? (
          <>
            <Text style={styles.section}>오늘 챙길 것</Text>
            <DeviceDeck items={briefings} onPick={(ask) => onOpenChat?.(ask)} />
          </>
        ) : null}

        {/* 내 기기 — 한 카드 안 행 리스트 */}
        {tiles.length ? (
          <FadeInView delay={0.05}>
            <Text style={styles.section}>내 기기</Text>
            <View style={styles.listCard}>
              {tiles.map((t, i) => (
                <PressableScale
                  key={i}
                  testID={`tile-${i}`}
                  onPress={() => onOpenChat?.(t.ask)}
                  style={[styles.row, i < tiles.length - 1 && styles.rowDivider]}
                  lift={false}
                >
                  {DEVICE_IMAGE[t.type] ? (
                    <Image source={{ uri: DEVICE_IMAGE[t.type] }} style={styles.rowThumb} resizeMode="cover" />
                  ) : (
                    <View style={[styles.rowChip, { backgroundColor: t.tint }]}>
                      <Text style={styles.rowIcon}>{t.icon}</Text>
                    </View>
                  )}
                  <View style={styles.rowBody}>
                    <Text style={styles.rowTitle}>{t.title}</Text>
                    <Text style={styles.rowSub}>{t.sub}</Text>
                  </View>
                  <View
                    style={[
                      styles.statusPill,
                      { backgroundColor: t.ok ? color.successTint : color.dangerTint },
                    ]}
                  >
                    <Text
                      style={[
                        styles.statusText,
                        { color: t.ok ? color.success : color.danger },
                      ]}
                    >
                      {t.ok ? '정상' : '점검'}
                    </Text>
                  </View>
                  <Text style={styles.chevronMuted}>›</Text>
                </PressableScale>
              ))}
            </View>
          </FadeInView>
        ) : null}

        {/* 맞춤 추천 */}
        {recs.length ? (
          <FadeInView testID="home-recommend" delay={0.08}>
            <Text style={styles.section}>맞춤 추천</Text>
            <PressableScale
              onPress={() => onOpenChat?.('추천 제품 자세히 알려줘')}
              style={styles.recCard}
            >
              <TemplateView template={{ kind: 'recommendation_list', data: { products: recs } }} />
            </PressableScale>
          </FadeInView>
        ) : null}

        <View style={{ height: space.xl }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  content: {
    paddingHorizontal: space.lg,
    paddingTop: space.sm,
    paddingBottom: space.xl,
    maxWidth: 480,
    width: '100%',
    alignSelf: 'center',
  },

  greeting: {
    fontSize: font.size.display,
    fontWeight: font.weight.bold as any,
    color: color.text,
    lineHeight: 40,
  },
  greetingSub: { fontSize: font.size.md, color: color.textSub, marginTop: 6 },

  // 퀵 액션
  quickRow: { flexDirection: 'row', marginTop: space.xl, gap: space.sm },
  quickItemWrap: { flex: 1 },
  quickItem: { alignItems: 'center', gap: space.sm, paddingVertical: space.xs },
  quickChip: {
    width: 58,
    height: 58,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  quickIcon: { fontSize: 26 },
  quickLabel: { fontSize: font.size.sm, color: color.textSub, fontWeight: font.weight.semibold as any },

  section: {
    fontSize: font.size.lg,
    color: color.text,
    fontWeight: font.weight.bold as any,
    marginTop: space.xxl,
    marginBottom: space.md,
  },

  // 챙길 것 카드
  deck: { gap: space.md },
  briefCard: {
    backgroundColor: color.surface,
    borderRadius: radius.xl,
    padding: space.xl,
    ...(shadow.card as any),
  },
  tag: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  tagText: { fontSize: font.size.xs, fontWeight: font.weight.bold as any },
  briefTitle: {
    fontSize: font.size.xl,
    fontWeight: font.weight.bold as any,
    color: color.text,
    marginTop: space.md,
  },
  briefDesc: { fontSize: font.size.md, color: color.textSub, lineHeight: 23, marginTop: 6 },
  briefCtaRow: { flexDirection: 'row', alignItems: 'center', marginTop: space.lg },
  briefCta: { fontSize: font.size.md, color: color.primary, fontWeight: font.weight.bold as any },
  chevron: { fontSize: 20, color: color.primary, fontWeight: font.weight.bold as any, marginLeft: 2 },

  // 기기 리스트 카드
  listCard: {
    backgroundColor: color.surface,
    borderRadius: radius.xl,
    paddingHorizontal: space.lg,
    ...(shadow.card as any),
  },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: space.lg, gap: space.md },
  rowDivider: { borderBottomWidth: 1, borderBottomColor: color.surfaceAlt },
  rowChip: {
    width: 44,
    height: 44,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowThumb: { width: 44, height: 44, borderRadius: 14, backgroundColor: color.surfaceAlt },
  rowIcon: { fontSize: 20 },
  rowBody: { flex: 1 },
  rowTitle: { fontSize: font.size.md, fontWeight: font.weight.bold as any, color: color.text },
  rowSub: { fontSize: font.size.xs, color: color.textMuted, marginTop: 2 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  statusText: { fontSize: font.size.xs, fontWeight: font.weight.bold as any },
  chevronMuted: { fontSize: 18, color: color.textMuted, marginLeft: 2 },

  recCard: {
    backgroundColor: color.surface,
    borderRadius: radius.xl,
    padding: space.lg,
    ...(shadow.card as any),
  },
});
