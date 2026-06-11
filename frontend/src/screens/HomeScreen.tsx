/** S1 홈 (변형 B, wireframes §2) — 브리핑 카드 스택(스와이프) + 2열 작은 카드 + 하단 고정 채팅바.
 *
 * `home_summary`(devices·alerts)에서 브리핑/타일을 파생한다(BFF /home 또는 fixtures).
 * 브리핑 카드·타일 탭 → 맥락 질문으로 채팅 진입, 하단 채팅바 탭 → 빈 채팅 진입(자유 입력).
 */
import React, { useRef, useState } from "react";
import {
  NativeScrollEvent, NativeSyntheticEvent, Pressable, ScrollView,
  StyleSheet, Text, View, useWindowDimensions,
} from "react-native";
import { color, font, gradient, radius, shadow, space } from "../design/tokens";
import { homeSummary } from "../fixtures/journeys";

const DEVICE_KO: Record<string, string> = { washer: "세탁기", refrigerator: "냉장고", air_purifier: "공기청정기" };
const DEVICE_ICON: Record<string, string> = { washer: "🧺", refrigerator: "❄️", air_purifier: "🌀" };
const CONS_KO: Record<string, string> = { drain_filter: "배수 필터", water_filter: "정수필터", hepa_filter: "HEPA 필터" };

type Briefing = { badge: string; title: string; desc: string; cta: string; ask: string };
type Tile = { icon: string; tint: string; title: string; sub: string; ok?: boolean; warn?: boolean; ask: string };

/** home_summary → 브리핑 카드(우선순위: 점검 필요 기기 → 소모품 알림). */
function buildBriefings(data: any): Briefing[] {
  const out: Briefing[] = [];
  for (const d of data.devices ?? []) {
    if (d.status !== "ONLINE") {
      const c = (d.consumables ?? []).find((x: any) => x.life_remaining <= x.threshold) ?? (d.consumables ?? [])[0];
      const pct = c ? Math.round(c.life_remaining * 100) : null;
      out.push({
        badge: "⚠ 점검 필요",
        title: `${DEVICE_KO[d.type] ?? d.type} 배수 이상 (5C)`,
        desc: pct != null
          ? `${CONS_KO[c.name] ?? "소모품"} 수명 ${pct}%. 지금 청소·교체하면 오류를 예방할 수 있어요.`
          : "상태 확인이 필요해요.",
        cta: "해결 방법 보기 →",
        ask: `${DEVICE_KO[d.type] ?? d.type}에서 물이 안 빠져요. 5C 떠요. 해결하고 부품도 주문할래요.`,
      });
    }
  }
  for (const a of data.alerts ?? []) {
    const d = (data.devices ?? []).find((x: any) => x.id === a.device_id);
    const name = d ? DEVICE_KO[d.type] ?? d.type : "기기";
    out.push({
      badge: a.severity === "warning" ? "⚠ 소모품" : "ⓘ 안내",
      title: `${name} 소모품 알림`,
      desc: a.detail,
      cta: "교체·주문 안내 →",
      ask: `${name} 소모품 교체 방법 알려주고 주문도 도와줘`,
    });
  }
  return out;
}

/** home_summary → 2열 작은 카드(기기 2개 + 주문·예약 진입). */
function buildTiles(data: any): Tile[] {
  const tiles: Tile[] = [];
  for (const d of (data.devices ?? []).slice(0, 2)) {
    const ok = d.status === "ONLINE";
    tiles.push({
      icon: DEVICE_ICON[d.type] ?? "📱", tint: ok ? color.successTint : color.warningTint,
      title: `${DEVICE_KO[d.type] ?? d.type} ${ok ? "정상" : "점검"}`,
      sub: d.model, ok, warn: !ok,
      ask: `${DEVICE_KO[d.type] ?? d.type} 상태 확인해줘`,
    });
  }
  tiles.push({ icon: "📦", tint: color.primaryTint, title: "부품 주문", sub: "배수 필터 ₩12,000",
    ask: "세탁기 배수 필터 주문할래요" });
  tiles.push({ icon: "🏠", tint: color.dangerTint, title: "방문 예약", sub: "출장 수리 가능",
    ask: "방문 수리 예약하고 싶어요" });
  return tiles;
}

export function HomeScreen({ onOpenChat }: { onOpenChat?: (q?: string) => void; onGallery?: () => void }) {
  const data = homeSummary.data as any;
  const briefings = buildBriefings(data);
  const tiles = buildTiles(data);
  const { width } = useWindowDimensions();
  const cardW = Math.min(width, 480) - space.lg * 2;
  const [page, setPage] = useState(0);

  function onScroll(e: NativeSyntheticEvent<NativeScrollEvent>) {
    const i = Math.round(e.nativeEvent.contentOffset.x / (cardW + space.md));
    if (i !== page) setPage(i);
  }

  return (
    <View style={styles.root} testID="screen-home">
      <ScrollView contentContainerStyle={styles.content}>
        {/* 브리핑 카드 — 스택 스와이프 */}
        <Text style={styles.label}>오늘의 브리핑</Text>
        <View style={styles.deckWrap}>
          <View style={[styles.behind, styles.behind2]} />
          <View style={styles.behind} />
          <ScrollView
            horizontal pagingEnabled showsHorizontalScrollIndicator={false}
            snapToInterval={cardW + space.md} decelerationRate="fast"
            onMomentumScrollEnd={onScroll} testID="briefing-deck"
            contentContainerStyle={{ gap: space.md }}>
            {briefings.map((b, i) => (
              <Pressable key={i} testID={`briefing-${i}`} onPress={() => onOpenChat?.(b.ask)}
                         style={[styles.briefCard, { width: cardW }]}>
                <Text style={styles.briefBadge}>{b.badge}</Text>
                <Text style={styles.briefTitle}>{b.title}</Text>
                <Text style={styles.briefDesc}>{b.desc}</Text>
                <View style={styles.briefCta}><Text style={styles.briefCtaText}>{b.cta}</Text></View>
              </Pressable>
            ))}
          </ScrollView>
        </View>
        <View style={styles.dots}>
          {briefings.map((_, i) => <View key={i} style={[styles.dot, i === page && styles.dotOn]} />)}
        </View>

        {/* 2열 작은 카드 */}
        <Text style={styles.label}>한눈에 보기</Text>
        <View style={styles.grid}>
          {tiles.map((t, i) => (
            <Pressable key={i} testID={`tile-${i}`} onPress={() => onOpenChat?.(t.ask)}
                       style={({ pressed }) => [styles.tile, pressed && { opacity: 0.85 }]}>
              <View style={[styles.tileChip, { backgroundColor: t.tint }]}><Text style={styles.tileIcon}>{t.icon}</Text></View>
              <Text style={styles.tileTitle}>{t.title}</Text>
              <Text style={styles.tileSub}>{t.sub}</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>

      {/* 하단 고정 채팅바 — 탭하면 채팅으로 펼침(자유 입력) */}
      <Pressable testID="open-chat" accessibilityRole="button" onPress={() => onOpenChat?.()}
                 style={styles.chatBar}>
        <View style={styles.chatStub}><Text style={styles.chatStubText}>가전 문제·부품 주문을 물어보세요</Text></View>
        <View style={styles.chatSend}><Text style={styles.chatSendIcon}>↑</Text></View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  content: { padding: space.lg, paddingBottom: space.xl, maxWidth: 480, width: "100%", alignSelf: "center" },
  label: { fontSize: font.size.xs, color: color.textMuted, fontWeight: font.weight.semibold as any, marginTop: space.md, marginBottom: space.sm },

  deckWrap: { position: "relative", paddingTop: 8 },
  behind: { position: "absolute", left: 8, right: 8, top: 0, height: 168, borderRadius: 22, backgroundColor: "#7FB5FF", opacity: 0.7 },
  behind2: { left: 16, right: 16, top: -8, backgroundColor: "#BBD9FF", opacity: 0.6 },
  briefCard: {
    minHeight: 176, borderRadius: 22, padding: space.lg, justifyContent: "flex-start",
    backgroundColor: color.primary, ...(shadow.card as any), ...( { backgroundImage: gradient.brand } as any ),
  },
  briefBadge: { alignSelf: "flex-start", color: "#fff", fontSize: font.size.xs, fontWeight: font.weight.bold as any,
    backgroundColor: "rgba(255,255,255,0.22)", paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  briefTitle: { color: "#fff", fontSize: font.size.xl, fontWeight: font.weight.bold as any, marginTop: space.md },
  briefDesc: { color: "rgba(255,255,255,0.92)", fontSize: font.size.md, lineHeight: 22, marginTop: space.sm },
  briefCta: { alignSelf: "flex-start", backgroundColor: "#fff", borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: space.sm, marginTop: space.md },
  briefCtaText: { color: color.primaryDark, fontSize: font.size.sm, fontWeight: font.weight.bold as any },

  dots: { flexDirection: "row", gap: 6, justifyContent: "center", marginTop: space.md },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: color.border },
  dotOn: { width: 18, backgroundColor: color.primary },

  grid: { flexDirection: "row", flexWrap: "wrap", gap: space.md },
  tile: { width: "47%", flexGrow: 1, backgroundColor: color.surface, borderRadius: 18, padding: space.lg, ...(shadow.card as any) },
  tileChip: { width: 38, height: 38, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  tileIcon: { fontSize: 18 },
  tileTitle: { fontSize: font.size.md, fontWeight: font.weight.bold as any, color: color.text, marginTop: space.md },
  tileSub: { fontSize: font.size.xs, color: color.textMuted, marginTop: 3 },

  chatBar: {
    flexDirection: "row", alignItems: "center", gap: space.sm,
    paddingHorizontal: space.lg, paddingTop: space.sm, paddingBottom: space.lg,
    backgroundColor: color.surface, borderTopWidth: 1, borderTopColor: color.border,
  },
  chatStub: { flex: 1, backgroundColor: color.surfaceAlt, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: 13 },
  chatStubText: { color: color.textMuted, fontSize: font.size.md },
  chatSend: { width: 46, height: 46, borderRadius: 23, backgroundColor: color.primary, alignItems: "center", justifyContent: "center",
    ...( { backgroundImage: gradient.brand } as any ) },
  chatSendIcon: { color: "#fff", fontSize: 20, fontWeight: font.weight.bold as any },
});
