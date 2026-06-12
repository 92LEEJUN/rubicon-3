/** 요구사항 데모 — 시나리오 트랜스크립트(채팅 흐름 + R# 배지). 스크린샷/검수용. */
import React from "react";
import { Image, ScrollView, StyleSheet, Text, View } from "react-native";
import { SectionView } from "../components/message";
import { color, font, radius, space } from "../design/tokens";
import { getScenario, type ScenarioMsg } from "../fixtures/scenarios";

function ReqBadges({ reqs }: { reqs?: string[] }) {
  if (!reqs?.length) return null;
  return (
    <View style={styles.reqRow}>
      {reqs.map((r) => <View key={r} style={styles.reqBadge}><Text style={styles.reqText}>{r}</Text></View>)}
    </View>
  );
}

function MsgView({ m }: { m: ScenarioMsg }) {
  if (m.role === "system") {
    return (
      <View style={styles.sysWrap}>
        <View style={styles.sysCard}>
          <Text style={styles.sysText}>{m.note}</Text>
          <ReqBadges reqs={m.reqs} />
        </View>
      </View>
    );
  }
  if (m.role === "user") {
    return (
      <View style={styles.userRow}>
        <View style={styles.userBubble}>
          {m.image ? <Image source={{ uri: m.image }} style={styles.photo} resizeMode="cover" /> : null}
          {m.text ? <Text style={styles.userText}>{m.text}</Text> : null}
          <ReqBadges reqs={m.reqs} />
        </View>
      </View>
    );
  }
  return (
    <View style={styles.aRow}>
      <View style={styles.avatar}><Text style={styles.avatarText}>AI</Text></View>
      <View style={styles.aCol}>
        <ReqBadges reqs={m.reqs} />
        {m.text ? <View style={styles.aBubble}><Text style={styles.aText}>{m.text}</Text></View> : null}
        {(m.sections ?? []).map((s, i) => <SectionView key={i} section={s} />)}
      </View>
    </View>
  );
}

export function Scenario({ id }: { id?: string }) {
  const sc = getScenario(id);
  return (
    <View style={styles.root} testID="screen-scenario">
      <View style={styles.header}>
        <Text style={styles.title}>{sc.title}</Text>
        <View style={{ height: space.xs }} />
        <ReqBadges reqs={sc.reqs} />
      </View>
      <ScrollView contentContainerStyle={styles.content} testID="scenario-scroll">
        {sc.messages.map((m, i) => <MsgView key={i} m={m} />)}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  header: { padding: space.lg, backgroundColor: color.surface, borderBottomWidth: 1, borderBottomColor: color.border },
  title: { fontSize: font.size.lg, fontWeight: font.weight.bold as any, color: color.text },
  content: { padding: space.lg, gap: space.sm, maxWidth: 520, width: "100%", alignSelf: "center" },

  reqRow: { flexDirection: "row", flexWrap: "wrap", gap: 4, marginTop: 4 },
  reqBadge: { backgroundColor: color.primaryDark, borderRadius: radius.pill, paddingHorizontal: 7, paddingVertical: 2 },
  reqText: { color: "#fff", fontSize: 11, fontWeight: font.weight.bold as any },

  sysWrap: { alignItems: "center", marginVertical: space.sm },
  sysCard: { backgroundColor: color.surfaceAlt, borderRadius: radius.md, paddingHorizontal: space.lg, paddingVertical: space.sm, maxWidth: "92%", alignItems: "center" },
  sysText: { color: color.textSub, fontSize: font.size.sm, textAlign: "center" },

  userRow: { alignItems: "flex-end", marginBottom: space.xs },
  userBubble: { backgroundColor: color.primary, paddingVertical: space.sm, paddingHorizontal: space.lg, borderRadius: radius.lg, maxWidth: "85%" },
  userText: { color: "#fff", fontSize: font.size.md, lineHeight: 22 },
  photo: { width: 120, height: 90, borderRadius: 10, marginBottom: space.xs },

  aRow: { flexDirection: "row", gap: space.sm, marginBottom: space.sm, alignItems: "flex-start" },
  avatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: color.primaryTint, alignItems: "center", justifyContent: "center", marginTop: 2 },
  avatarText: { color: color.primaryDark, fontWeight: font.weight.bold as any, fontSize: 11 },
  aCol: { flex: 1, gap: space.xs, alignItems: "flex-start" },
  aBubble: { backgroundColor: color.surface, borderWidth: 1, borderColor: color.border, paddingVertical: space.sm, paddingHorizontal: space.lg, borderRadius: radius.lg, maxWidth: "94%" },
  aText: { color: color.text, fontSize: font.size.md, lineHeight: 22 },
});
