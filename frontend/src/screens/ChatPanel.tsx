/** S3 채팅 패널 — 사용자 말풍선 + 어시스턴트(자연어/섹션 스택, 복합 R7).
 *
 * wsUrl 이 있으면 실 서버(BFF /chat)에 WebSocket으로 붙어 입력→스트림을 렌더하고,
 * 없으면 기존 데모처럼 MockTransport로 스크립트 섹션을 재생한다(정적 배포·테스트).
 * 첫 질문은 마운트 시 자동 전송하고, 입력창으로 후속 질문을 이어갈 수 있다.
 */
import React, { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Caption, Title } from "../components/primitives";
import { MessageView } from "../components/message";
import { MockTransport, WebSocketTransport } from "../transport";
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

export function ChatPanel({ question, sections, flow = null, wsUrl }:
  { question: string; sections: MessageSection[]; flow?: string | null; wsUrl?: string }) {
  const transport = useMemo(
    () => (wsUrl
      ? new WebSocketTransport(wsUrl)
      : new MockTransport((_m: ClientMessage) => toChunks(sections, flow))),
    [wsUrl, sections, flow],
  );
  const { state, send, replyInteraction } = useChat(transport);
  const [lastUser, setLastUser] = useState(question);
  const [text, setText] = useState("");

  useEffect(() => { send(question); }, []); // 데모/실서버 공통: 마운트 시 첫 질문 전송

  const streaming = state.status === "streaming";

  function onSend() {
    const q = text.trim();
    if (!q || streaming) return; // 빈 입력·생성 중 중복 전송 방지
    setLastUser(q);
    send(q);
    setText("");
  }

  return (
    <View style={styles.root} testID="screen-chat">
      <View style={styles.header}><Title>AI 컨시어지</Title></View>
      <ScrollView contentContainerStyle={styles.content} testID="chat-scroll">
        <View style={styles.userBubble}><Text style={styles.userText}>{lastUser}</Text></View>
        {state.assistantText ? (
          <View style={styles.assistantBubble} testID="assistant-text">
            <Text style={styles.assistantTextStyle}>{state.assistantText}</Text>
          </View>
        ) : null}
        {streaming && state.sections.length === 0 && !state.assistantText ? (
          <Caption>답변을 작성하고 있어요…</Caption>
        ) : null}
        <MessageView sections={state.sections} onCta={replyInteraction} />
      </ScrollView>
      <View style={styles.inputBar}>
        <TextInput
          testID="chat-input"
          style={styles.input}
          value={text}
          onChangeText={setText}
          editable={!streaming}
          placeholder="가전 문제·부품 주문을 물어보세요"
          placeholderTextColor={color.textMuted}
          onSubmitEditing={onSend}
        />
        <Pressable testID="chat-send" accessibilityRole="button" onPress={onSend}
                   disabled={streaming} style={[styles.sendBtn, streaming && styles.sendBtnDisabled]}>
          <Text style={styles.sendText}>{streaming ? "전송 중…" : "전송"}</Text>
        </Pressable>
      </View>
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
  assistantBubble: {
    alignSelf: "flex-start", backgroundColor: color.surface, borderWidth: 1, borderColor: color.border,
    paddingVertical: space.sm, paddingHorizontal: space.lg, borderRadius: radius.lg, marginBottom: space.lg, maxWidth: "90%",
  },
  assistantTextStyle: { color: color.text, fontSize: 15, lineHeight: 22 },
  inputBar: {
    flexDirection: "row", gap: space.sm, padding: space.md, borderTopWidth: 1,
    borderTopColor: color.border, backgroundColor: color.surface,
  },
  input: {
    flex: 1, backgroundColor: color.surfaceAlt, borderRadius: radius.pill,
    paddingHorizontal: space.lg, paddingVertical: space.md, fontSize: 15, color: color.text,
  },
  sendBtn: { backgroundColor: color.primary, borderRadius: radius.pill, paddingHorizontal: space.lg, justifyContent: "center" },
  sendBtnDisabled: { opacity: 0.5 },
  sendText: { color: "#fff", fontWeight: "600", fontSize: 15 },
});
