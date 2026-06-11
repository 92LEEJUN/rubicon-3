/** S3 전역 채팅 패널 — 사용자 말풍선 + 어시스턴트 섹션 스택(복합 R7). */
import React, { useEffect, useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { Caption, Title } from "../components/primitives";
import { MessageView } from "../components/message";
import { MockTransport } from "../transport";
import { useChat } from "../state/useChat";
import { color, radius, space } from "../design/tokens";
import type { Chunk, ClientMessage, MessageSection } from "../types/contract";

/** 섹션 배열 → 청크 스트림(section* → flow → done). */
function toChunks(sections: MessageSection[], flow: string | null): Chunk[] {
  return [
    ...sections.map((section) => ({ type: "section", section } as Chunk)),
    { type: "flow", active_flow: flow } as Chunk,
    { type: "done", message_id: "msg_demo" } as Chunk,
  ];
}

export function ChatPanel({ question, sections, flow = null }:
  { question: string; sections: MessageSection[]; flow?: string | null }) {
  const transport = useMemo(
    () => new MockTransport((_m: ClientMessage) => toChunks(sections, flow)),
    [sections, flow],
  );
  const { state, send, replyInteraction } = useChat(transport);

  useEffect(() => { send(question); }, []); // 데모: 마운트 시 질문 전송

  return (
    <View style={styles.root} testID="screen-chat">
      <View style={styles.header}><Title>AI 컨시어지</Title></View>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.userBubble}><Text style={styles.userText}>{question}</Text></View>
        {state.status === "streaming" && state.sections.length === 0 ? (
          <Caption>답변을 작성하고 있어요…</Caption>
        ) : null}
        <MessageView sections={state.sections} onCta={replyInteraction} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  header: { padding: space.lg, borderBottomWidth: 1, borderBottomColor: color.border, backgroundColor: color.surface },
  content: { padding: space.lg, maxWidth: 480, width: "100%", alignSelf: "center" },
  userBubble: {
    alignSelf: "flex-end", backgroundColor: color.primary, paddingVertical: space.sm,
    paddingHorizontal: space.lg, borderRadius: radius.lg, marginBottom: space.lg, maxWidth: "85%",
  },
  userText: { color: "#fff", fontSize: 15, lineHeight: 22 },
});
