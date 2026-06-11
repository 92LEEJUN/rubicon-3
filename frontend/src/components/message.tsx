/**
 * 섹션/메시지 렌더 — 복합 응답(R7)을 섹션별로 세로 스택, 미처리(handled:false) 표시.
 * frontend-architecture §4: Message = sections[] 합성, 각 섹션 label·template·ctas.
 */
import React from "react";
import { StyleSheet, View } from "react-native";
import { color, space } from "../design/tokens";
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
  return (
    <Card testID={`section-${section.intent}`} style={styles.section}>
      <View style={styles.head}>
        <Caption>{section.label}</Caption>
        {!section.handled ? <Badge label="미처리" tone="danger" /> : null}
      </View>
      <TemplateView template={section.template} />
      <CtaRow ctas={section.ctas} onCta={onCta} />
    </Card>
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
});
