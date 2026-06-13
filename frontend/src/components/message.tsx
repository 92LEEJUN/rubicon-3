/**
 * 섹션/메시지 렌더 — 복합 응답(R7)을 섹션별로 세로 스택, 미처리(handled:false) 표시.
 * frontend-architecture §4: Message = sections[] 합성, 각 섹션 label·template·ctas.
 */
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { color, font, space } from "../design/tokens";
import type { Cta, MessageSection } from "../types/contract";
import { Badge, Button, Caption, Card } from "./primitives";
import { TemplateView } from "../templates";

export function CtaRow({ ctas, onCta }: { ctas: Cta[]; onCta?: (c: Cta) => void }) {
  if (!ctas?.length) return null;
  return (
    <View style={styles.ctaRow}>
      {ctas.map((c, i) => (
        <Button key={i} label={c.label} testID={`cta-${c.kind ?? c.action}`}
                variant={c.action === "commit" ? "primary" : "secondary"}
                onPress={() => onCta?.(c)} />
      ))}
    </View>
  );
}

export function SectionView({ section, onCta }: { section: MessageSection; onCta?: (c: Cta) => void }) {
  // 미처리(handled:false) — 일반 답변처럼 보이지 않게 낮은 채도의 비활성 스타일로(요구 ⑦).
  if (!section.handled) return <UnhandledSection section={section} onCta={onCta} />;
  return (
    <Card testID={`section-${section.intent}`} style={styles.section}>
      <View style={styles.head}>
        <Caption>{section.label}</Caption>
      </View>
      <TemplateView template={section.template} />
      <CtaRow ctas={section.ctas} onCta={onCta} />
    </Card>
  );
}

/**
 * 미처리 섹션 — "이건 아직 도와드리기 어려워요" 톤다운 표현(요구 ⑦).
 * 정상 답변 카드와 시각적으로 구분(점선 테두리·뮤트 배경·작은 안내). 원문 메시지는 보조로 노출,
 * CTA(예: 입고 알림·대체 추천)는 남겨 대안 행동을 유지한다.
 */
function UnhandledSection({ section, onCta }: { section: MessageSection; onCta?: (c: Cta) => void }) {
  const detail =
    (section.template?.data as any)?.message ??
    (section.template?.data as any)?.detail ??
    null;
  return (
    <View testID={`section-${section.intent}`} style={styles.unhandled}>
      <View style={styles.head}>
        <Caption>{section.label}</Caption>
        <Badge label="처리 보류" tone="neutral" />
      </View>
      <Text style={styles.unhandledLead}>이건 아직 도와드리기 어려워요.</Text>
      {detail ? <Text style={styles.unhandledDetail}>{detail}</Text> : null}
      <CtaRow ctas={section.ctas} onCta={onCta} />
    </View>
  );
}

/** 한 어시스턴트 응답의 섹션들을 우선순위 순서대로 세로 스택(R7). */
export function MessageView({ sections, onCta }: { sections: MessageSection[]; onCta?: (c: Cta) => void }) {
  return (
    <View testID="assistant-message">
      {sections.map((s, i) => <SectionView key={i} section={s} onCta={onCta} />)}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: space.md },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: space.sm },
  ctaRow: { flexDirection: "row", gap: space.sm, marginTop: space.md, flexWrap: "wrap" },
  // 미처리 — 톤다운(점선 테두리·뮤트 배경), 정상 카드와 시각적으로 구분(요구 ⑦).
  unhandled: {
    marginBottom: space.md,
    backgroundColor: color.surfaceAlt,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: color.border,
    borderRadius: space.md,
    padding: space.lg,
    opacity: 0.92,
  },
  unhandledLead: { fontSize: font.size.md, color: color.textSub, fontWeight: font.weight.medium as any },
  unhandledDetail: { fontSize: font.size.sm, color: color.textMuted, lineHeight: 20, marginTop: space.xs },
});
