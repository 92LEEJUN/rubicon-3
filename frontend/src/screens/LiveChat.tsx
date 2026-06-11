/** 라이브 채팅(E2E·실서비스) — WebSocketTransport로 BFF /chat에 연결, 입력→스트림 렌더. */
import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Caption, Title } from "../components/primitives";
import { MessageView } from "../components/message";
import { WebSocketTransport } from "../transport";
import { useChat } from "../state/useChat";
import { color, radius, space } from "../design/tokens";

export function LiveChat({ wsUrl }: { wsUrl: string }) {
  const transport = useMemo(() => new WebSocketTransport(wsUrl), [wsUrl]);
  const { state, send } = useChat(transport);
  const [text, setText] = useState("");
  const [sent, setSent] = useState<string | null>(null);

  function onSend() {
    const q = text.trim();
    if (!q) return;
    setSent(q);
    send(q);
    setText("");
  }

  return (
    <View style={styles.root} testID="screen-live">
      <View style={styles.header}><Title>AI 컨시어지</Title></View>
      <ScrollView contentContainerStyle={styles.content} testID="chat-scroll">
        {sent ? <View style={styles.userBubble}><Text style={styles.userText}>{sent}</Text></View> : null}
        {state.status === "streaming" && state.sections.length === 0 ? (
          <Caption>답변을 작성하고 있어요…</Caption>
        ) : null}
        <MessageView sections={state.sections} onCta={() => {}} />
      </ScrollView>
      <View style={styles.inputBar}>
        <TextInput
          testID="chat-input"
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder="가전 문제·부품 주문을 물어보세요"
          placeholderTextColor={color.textMuted}
          onSubmitEditing={onSend}
        />
        <Pressable testID="chat-send" accessibilityRole="button" onPress={onSend} style={styles.sendBtn}>
          <Text style={styles.sendText}>전송</Text>
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
  inputBar: {
    flexDirection: "row", gap: space.sm, padding: space.md, borderTopWidth: 1,
    borderTopColor: color.border, backgroundColor: color.surface,
  },
  input: {
    flex: 1, backgroundColor: color.surfaceAlt, borderRadius: radius.pill,
    paddingHorizontal: space.lg, paddingVertical: space.md, fontSize: 15, color: color.text,
  },
  sendBtn: { backgroundColor: color.primary, borderRadius: radius.pill, paddingHorizontal: space.lg, justifyContent: "center" },
  sendText: { color: "#fff", fontWeight: "600", fontSize: 15 },
});
