/** S2 고객지원(CS) — 증상 해결·부품 주문·방문/상담 진입 허브(wireframes S2). */
import React from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Badge, Body, Caption, Card, Title } from "../components/primitives";
import { TemplateView } from "../templates";
import { color, radius, space } from "../design/tokens";
import { homeSummary, statusTracker } from "../fixtures/journeys";

const DEVICE_KO: Record<string, string> = { washer: "세탁기", refrigerator: "냉장고", air_purifier: "공기청정기" };

// 빠른 진입(탭하면 채팅으로 해당 질문 전송)
const QUICK_ACTIONS = [
  { key: "troubleshoot", icon: "🛠", label: "문제 해결", desc: "증상·오류코드 진단" },
  { key: "order", icon: "📦", label: "부품 주문", desc: "호환 부품·소모품" },
  { key: "visit", icon: "🏠", label: "방문 예약", desc: "출장 수리 신청" },
  { key: "consult", icon: "💬", label: "상담 연결", desc: "전문 상담사" },
];

const FAQ = [
  { q: "세탁기 배수가 안 돼요 (5C)", tone: "warning" as const },
  { q: "냉장고 정수필터 교체 방법", tone: "neutral" as const },
  { q: "공기청정기 HEPA 필터 교체", tone: "neutral" as const },
];

export function SupportScreen({ onAsk, data }: { onAsk?: (q: string) => void; data?: any }) {
  const d0 = data ?? (homeSummary.data as any);
  const devices = d0.devices ?? [];
  const recs: any[] = d0.recommendations ?? [];
  return (
    <View style={styles.root} testID="screen-support">
      <ScrollView contentContainerStyle={styles.content}>
        <Title>무엇을 도와드릴까요?</Title>
        <View style={styles.grid}>
          {QUICK_ACTIONS.map((a) => (
            <Pressable key={a.key} testID={`cs-${a.key}`} onPress={() => onAsk?.(a.label)}
                       style={({ pressed }) => [styles.action, pressed && { opacity: 0.85 }]}>
              <Body>{a.icon}</Body>
              <Title>{a.label}</Title>
              <Caption>{a.desc}</Caption>
            </Pressable>
          ))}
        </View>

        <Caption>내 기기 빠른 점검</Caption>
        <Card>
          {devices.map((d: any, i: number) => (
            <View key={i} style={[styles.deviceRow, i < devices.length - 1 && styles.rowDivider]}>
              <View style={{ flex: 1 }}>
                <Body>{DEVICE_KO[d.type] ?? d.type}</Body>
                <Caption>{d.model}</Caption>
              </View>
              <Badge label={d.status === "ONLINE" ? "정상" : "점검 필요"} tone={d.status === "ONLINE" ? "success" : "warning"} />
              <Pressable testID={`cs-fix-${d.type}`} onPress={() => onAsk?.(`${DEVICE_KO[d.type] ?? d.type} 문제 해결`)}
                         style={styles.fixBtn}>
                <Caption>해결</Caption>
              </Pressable>
            </View>
          ))}
        </Card>

        <Caption>자주 찾는 해결</Caption>
        <Card>
          {FAQ.map((f, i) => (
            <Pressable key={i} testID={`cs-faq-${i}`} onPress={() => onAsk?.(f.q)}
                       style={[styles.faqRow, i < FAQ.length - 1 && styles.rowDivider]}>
              <View style={{ flex: 1 }}><Body>{f.q}</Body></View>
              <Caption>›</Caption>
            </Pressable>
          ))}
        </Card>

        <Caption>진행 중 · 최근 활동</Caption>
        <Pressable testID="cs-activity" onPress={() => onAsk?.("내 주문 진행 상태 알려줘")}>
          <Card><TemplateView template={statusTracker} /></Card>
        </Pressable>

        {recs.length ? (
          <>
            <Caption>맞춤 추천</Caption>
            <Pressable testID="cs-recommend" onPress={() => onAsk?.("추천 제품 자세히 알려줘")}>
              <Card><TemplateView template={{ kind: "recommendation_list", data: { products: recs } }} /></Card>
            </Pressable>
          </>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  content: { padding: space.lg, gap: space.md, maxWidth: 480, width: "100%", alignSelf: "center" },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: space.md },
  action: {
    width: "47%", flexGrow: 1, backgroundColor: color.surface, borderRadius: radius.lg,
    borderWidth: 1, borderColor: color.border, padding: space.lg, gap: 2,
  },
  deviceRow: { flexDirection: "row", alignItems: "center", gap: space.sm, paddingVertical: space.sm },
  faqRow: { flexDirection: "row", alignItems: "center", paddingVertical: space.md },
  rowDivider: { borderBottomWidth: 1, borderBottomColor: color.border },
  fixBtn: { backgroundColor: color.primaryTint, borderRadius: radius.pill, paddingHorizontal: space.md, paddingVertical: space.xs },
});
