/** S1 홈 — 개인화 요약(home_summary) + 전역 채팅 진입(R9, wireframes S1). */
import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Button, Caption, Card, Heading } from "../components/primitives";
import { TemplateView } from "../templates";
import { color, space } from "../design/tokens";
import { homeSummary } from "../fixtures/journeys";

export function HomeScreen({ onOpenChat }: { onOpenChat?: () => void }) {
  return (
    <View style={styles.root} testID="screen-home">
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Caption>Samsung</Caption>
          <Heading>AI 컨시어지</Heading>
        </View>
        <Card><TemplateView template={homeSummary} /></Card>
        <Card style={styles.cta}>
          <Caption>무엇이든 물어보세요</Caption>
          <View style={{ height: space.sm }} />
          <Button label="AI 컨시어지에게 물어보기" testID="open-chat" onPress={onOpenChat} />
        </Card>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  content: { padding: space.lg, gap: space.md, maxWidth: 480, width: "100%", alignSelf: "center" },
  header: { marginBottom: space.sm },
  cta: { backgroundColor: color.primaryTint, borderColor: "transparent" },
});
