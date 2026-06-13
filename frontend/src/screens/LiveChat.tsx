/** 라이브 채팅(E2E·실서비스) — WebSocketTransport로 BFF /chat에 연결, 입력→스트림 렌더. */
import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Caption, Title } from "../components/primitives";
import { MessageView } from "../components/message";
import { ConfirmDialog, LoginWall } from "../components/CommitGate";
import { ResilientTransport } from "../transport";
import { isCommitCta } from "../transport/commit";
import { useChat } from "../state/useChat";
import { useCommit } from "../state/useCommit";
import { track } from "../analytics/track";
import { color, radius, space } from "../design/tokens";
import { respond } from "../mock/respond";
import { streamDelayMs } from "../mock/mode";
import type { ClientMessage, Cta } from "../types/contract";

/** BE 미연결 시 폴백 — interaction_reply(비-commit)는 라우터용 텍스트로 변환. */
function msgText(m: ClientMessage): string {
  if (m.type === "user_message") return m.text;
  const k = m.kind;
  return k === "explain" ? "더 알려줘" : k === "recommend" ? "추천해줘" : k === "compare" ? "비교해줘"
    : k === "restock_alert" ? "입고 알림" : k === "booking" ? "예약" : "";
}

export function LiveChat({ wsUrl, apiBase, token }: { wsUrl: string; apiBase?: string; token?: string }) {
  const transport = useMemo(
    () => new ResilientTransport(wsUrl, (m) => respond(msgText(m)), 3500, { delayMs: streamDelayMs() }),
    [wsUrl]);
  const { state, send, replyInteraction } = useChat(transport);
  const [text, setText] = useState("");
  const [sent, setSent] = useState<string | null>(null);

  const cfg = useMemo(() => ({ base: apiBase, token }), [apiBase, token]);
  const commitCtl = useCommit(cfg);

  function sendQuery(q: string) {
    const t = (q || "").trim();
    if (!t) return;
    setSent(t);
    track("message_sent", { modality: "text" }); // (요구 ⑨)
    send(t);
    setText("");
  }
  function onSend() { sendQuery(text); }

  // CTA 라우터 — commit(order/booking) 라운드트립 · login 월 · select_device 즉시 질의 · 그 외 chat 후속(요구 ⑤⑥).
  function onCta(cta: Cta) {
    track("cta_clicked", { cta: cta.kind ?? cta.action, action: cta.action });
    if (isCommitCta(cta)) { void commitCtl.start(cta); return; }
    if (cta.kind === "login") { commitCtl.openLogin(); return; }
    if (cta.kind === "select_device") {
      const id = (cta.payload as any)?.device_id;
      sendQuery(id ? `${id} 기기에 대해 알려주세요` : "");   // 입력창 편집이 아니라 바로 질의
      return;
    }
    replyInteraction(cta);
  }

  return (
    <View style={styles.root} testID="screen-live">
      <View style={styles.header}><Title>AI 컨시어지</Title></View>
      <ScrollView contentContainerStyle={styles.content} testID="chat-scroll">
        {sent ? <View style={styles.userBubble}><Text style={styles.userText}>{sent}</Text></View> : null}
        {state.assistantText ? (
          <View style={styles.assistantBubble} testID="assistant-text">
            <Text style={styles.assistantTextStyle}>{state.assistantText}</Text>
          </View>
        ) : null}
        {state.status === "streaming" && state.sections.length === 0 && !state.assistantText ? (
          <Caption>답변을 작성하고 있어요…</Caption>
        ) : null}
        <MessageView sections={state.sections} onCta={onCta} />
      </ScrollView>

      {/* 커밋 게이트 — 409 확인 / 401 로그인(요구 ⑤⑥) */}
      {commitCtl.confirmTemplate ? (
        <ConfirmDialog template={commitCtl.confirmTemplate} busy={commitCtl.busy}
                       onConfirm={() => void commitCtl.confirm()} onCancel={commitCtl.cancelConfirm} />
      ) : null}
      {commitCtl.showLogin ? (
        <LoginWall onLogin={() => void commitCtl.login()} onDismiss={commitCtl.dismissLogin} />
      ) : null}
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
  sendText: { color: "#fff", fontWeight: "600", fontSize: 15 },
});
