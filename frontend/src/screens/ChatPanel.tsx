/** S3 채팅 — 멀티턴 대화(유저/어시스턴트 말풍선) + 자연어 텍스트·리치 섹션(R7).
 *
 * wsUrl 이 있으면 실 서버(BFF /chat)에 WebSocket으로 붙어 입력→스트림을 렌더하고,
 * 없으면 MockTransport로 스크립트 응답을 재생한다(정적 배포·테스트). 입력창은 항상 떠 있다.
 * 첫 질문은 마운트 시 자동 전송하고, 입력창·추천 칩으로 대화를 이어간다.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SectionView } from '../components/message';
import { ResumeCard } from '../components/ResumeCard';
import { ReEngagementBanner } from '../components/ReEngagementBanner';
import { StreamingMessage } from '../components/StreamingMessage';
import { ConfirmDialog, LoginWall } from '../components/CommitGate';
import { MockTransport, ResilientTransport } from '../transport';
import { isCommitCta } from '../transport/commit';
import { respond } from '../mock/respond';
import { streamDelayMs } from '../mock/mode';
import { useChat } from '../state/useChat';
import { useCommit } from '../state/useCommit';
import { track } from '../analytics/track';
import { useResume } from '../state/useResume';
import { useOpenLoops } from '../state/useOpenLoops';
import { useReEngagement } from '../state/useReEngagement';
import { companionStore } from '../state/companionStore';
import { color, font, radius, shadow, space } from '../design/tokens';
import type { Chunk, ClientMessage, Cta, MessageSection } from '../types/contract';

/** 데모 응답 — 자연어 인트로(delta) + 섹션 스택(section* → flow → done). */
function toChunks(sections: MessageSection[], flow: string | null): Chunk[] {
  return [
    {
      type: 'delta',
      text: '세탁기 배수 문제(5C)를 확인했어요. 아래에 진단·해결 단계를 정리했고, 필요한 부품도 함께 준비했어요.',
    } as Chunk,
    ...sections.map((section) => ({ type: 'section', section }) as Chunk),
    { type: 'flow', active_flow: flow } as Chunk,
    { type: 'done', message_id: 'msg_demo' } as Chunk,
  ];
}

type ChatMsg =
  | { role: 'user'; text: string }
  | { role: 'assistant'; text: string; sections: MessageSection[]; flow: string | null };

const SUGGESTIONS = [
  '세탁기 배수 오류(5C) 해결',
  '냉장고 정수필터 교체 안내',
  '공기청정기 필터 주문하기',
];

export function ChatPanel({
  question,
  sections,
  flow = null,
  wsUrl,
  apiBase,
  token,
  onClose,
}: {
  question: string;
  sections: MessageSection[];
  flow?: string | null;
  wsUrl?: string;
  apiBase?: string;
  token?: string;
  onClose?: () => void;
}) {
  const transport = useMemo(() => {
    // 첫 턴은 큐레이트된 sections(홈 질문의 답), 이후 자유 입력은 mock 라우터(respond)로 응답.
    let first = true;
    const script = (m: ClientMessage) => {
      if (first) {
        first = false;
        return toChunks(sections, flow);
      }
      return respond(m.type === 'user_message' ? m.text : '');
    };
    const opts = { delayMs: streamDelayMs() };
    return wsUrl
      ? new ResilientTransport(wsUrl, script, 3500, opts)
      : new MockTransport(script, opts);
  }, [wsUrl, sections, flow]);
  const { state, send, replyInteraction, resumeFromRef } = useChat(transport);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [text, setText] = useState('');
  const [turnSeq, setTurnSeq] = useState(0);
  const pending = useRef(false);
  const scroller = useRef<ScrollView>(null);

  // 컴패니언 — 패널 open 시 resume·open-loop·선제 배너(요구 1·2·3·6).
  const cfg = useMemo(() => ({ base: apiBase, token }), [apiBase, token]);

  // 커밋 라운드트립(order/booking) + 게이트(409 확인 · 401 로그인) (요구 ⑤⑥).
  const commitCtl = useCommit(cfg, {
    onCommitted: (kind) => {
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: kind === 'booking' ? '방문 예약이 확정되었어요.' : '주문이 확정되었어요.',
          sections: [],
          flow: state.activeFlow,
        },
      ]);
    },
  });
  useEffect(() => {
    companionStore.setPanelOpen(true);
    return () => companionStore.setPanelOpen(false);
  }, []);
  const { resume, hasContext, startFresh, degraded } = useResume(cfg, true);
  const loopsApi = useOpenLoops(cfg, resume?.open_loops);
  const reeng = useReEngagement(cfg, true);

  // open-loop/배너 탭 → 해당 ref 맥락으로 /chat 재진입(요구 2.2·3.3)
  function reenter(ref?: string) {
    if (!ref) return;
    pending.current = true;
    setTurnSeq((s) => s + 1);
    resumeFromRef(ref, companionStore.get().screenContext ?? undefined);
  }

  // 위로 펼쳐지는 진입(오버레이 느낌, wireframes §2 · 3.b)
  const rise = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    Animated.timing(rise, { toValue: 0, duration: 240, useNativeDriver: false }).start();
  }, [rise]);
  const translateY = rise.interpolate({ inputRange: [0, 1], outputRange: [0, 28] });

  const streaming = state.status === 'streaming';
  const empty = messages.length === 0 && !streaming;

  function submit(q: string) {
    const v = q.trim();
    if (!v || streaming) return; // 빈 입력·생성 중 중복 전송 방지
    setMessages((m) => [...m, { role: 'user', text: v }]);
    pending.current = true;
    setTurnSeq((s) => s + 1);
    track('message_sent', { modality: 'text' }); // 턴 전송(요구 ⑨)
    send(v);
    setText('');
  }

  /**
   * CTA 라우터(요구 ⑤⑥·login/select_device) — 모든 섹션 CTA가 여기로 모인다.
   *  - commit(order/booking) → REST 라운드트립(useCommit). 409 확인·401 로그인 게이트.
   *  - login → 로그인 월.
   *  - select_device → payload.device_id로 **바로 질의**(입력창 편집 아님).
   *  - 그 외(explain·restock_alert·compare·booking(chat)·recommend·choices…) → chat 후속(interaction_reply).
   */
  function onCta(cta: Cta) {
    track('cta_clicked', { cta: cta.kind ?? cta.action, action: cta.action }); // (요구 ⑨)
    if (isCommitCta(cta)) {
      void commitCtl.start(cta);
      return;
    }
    if (cta.kind === 'login') {
      commitCtl.openLogin();
      return;
    }
    if (cta.kind === 'select_device') {
      const id = (cta.payload as any)?.device_id;
      if (id) submit(`${id} 기기에 대해 알려주세요`); // 입력창 편집이 아니라 바로 질의
      return;
    }
    replyInteraction(cta); // chat 후속
  }

  // 첫 질문 자동 전송(데모/실서버 공통)
  useEffect(() => {
    if (question?.trim()) submit(question);
  }, []);

  // 턴 완료 시 어시스턴트 응답을 히스토리에 커밋(스트리밍 뷰는 state로만 노출)
  useEffect(() => {
    if (pending.current && (state.status === 'done' || state.status === 'error')) {
      pending.current = false;
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: state.assistantText,
          sections: state.sections,
          flow: state.activeFlow,
        },
      ]);
    }
  }, [turnSeq, state.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // 새 메시지·스트림 변화 시 하단으로 스크롤
  useEffect(() => {
    const id = setTimeout(() => scroller.current?.scrollToEnd({ animated: true }), 50);
    return () => clearTimeout(id);
  }, [messages.length, state.assistantText, state.sections.length, streaming]);

  return (
    <Animated.View
      style={[
        styles.root,
        {
          transform: [{ translateY }],
          opacity: rise.interpolate({ inputRange: [0, 1], outputRange: [1, 0.4] }),
        },
      ]}
      testID="screen-chat"
    >
      <View style={styles.header}>
        {onClose ? (
          <Pressable
            testID="chat-back"
            accessibilityRole="button"
            onPress={onClose}
            style={styles.backBtn}
          >
            <Text style={styles.backIcon}>‹</Text>
          </Pressable>
        ) : null}
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>AI</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>AI 컨시어지</Text>
          <View style={styles.statusRow}>
            <View
              style={[
                styles.statusDot,
                { backgroundColor: wsUrl ? color.success : color.textMuted },
              ]}
            />
            <Text style={styles.statusText}>
              {wsUrl ? '온라인 · 실시간 응답' : '데모 모드 · 예시 응답'}
            </Text>
          </View>
        </View>
      </View>

      <ScrollView
        ref={scroller}
        style={styles.scroll}
        contentContainerStyle={styles.content}
        testID="chat-scroll"
      >
        {/* 선제 재관여 배너(동의·deliver 게이트는 훅에서, 요구 3·6) */}
        {reeng.banner ? (
          <ReEngagementBanner banner={reeng.banner} onOpen={reenter} onDismiss={reeng.dismiss} />
        ) : null}

        {/* 이어가기 카드 — 패널 상단(요구 1). has_context=false면 미표시(빈 상태). */}
        {hasContext && resume ? (
          <ResumeCard
            resume={resume}
            loops={loopsApi.loops}
            degraded={degraded}
            onContinue={() => companionStore.setResumeVisibility('dismissed')}
            onStartFresh={() => {
              startFresh();
              setMessages([]);
            }}
            onOpenLoop={reenter}
            onResolve={loopsApi.resolve}
            onDismiss={loopsApi.dismiss}
            isPending={loopsApi.isPending}
            loopError={loopsApi.error}
            onRetryLoopError={loopsApi.clearError}
          />
        ) : null}

        {empty ? (
          <View style={styles.empty} testID="chat-empty">
            <View style={styles.emptyAvatar}>
              <Text style={styles.avatarText}>AI</Text>
            </View>
            <Text style={styles.emptyTitle}>무엇을 도와드릴까요?</Text>
            <Text style={styles.emptyDesc}>
              가전 문제 진단부터 부품 주문·방문 예약까지 도와드려요.{'\n'}아래 추천을 누르거나 직접
              입력해 보세요.
            </Text>
          </View>
        ) : null}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <UserMessage key={i} text={m.text} />
          ) : (
            <AssistantMessage key={i} text={m.text} sections={m.sections} onCta={onCta} />
          ),
        )}

        {/* 진행 중인 어시스턴트 턴 — 증분 스트리밍(요구 4) */}
        {streaming ? (
          <StreamingMessage
            text={state.assistantText}
            sections={state.sections}
            streaming
            onCta={onCta}
          />
        ) : null}
      </ScrollView>

      {/* 커밋 게이트 — 409 확인 다이얼로그 / 401 로그인 월(요구 ⑤⑥) */}
      {commitCtl.confirmTemplate ? (
        <ConfirmDialog
          template={commitCtl.confirmTemplate}
          busy={commitCtl.busy}
          onConfirm={() => void commitCtl.confirm()}
          onCancel={commitCtl.cancelConfirm}
        />
      ) : null}
      {commitCtl.showLogin ? (
        <LoginWall onLogin={() => void commitCtl.login()} onDismiss={commitCtl.dismissLogin} />
      ) : null}

      {/* 추천 프롬프트 칩 — 항상 접근 가능 */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.chipsBar}
        contentContainerStyle={styles.chipsContent}
      >
        {SUGGESTIONS.map((s) => (
          <Pressable
            key={s}
            testID="chat-chip"
            onPress={() => submit(s)}
            disabled={streaming}
            style={({ pressed }) => [
              styles.chip,
              pressed && { opacity: 0.7 },
              streaming && { opacity: 0.5 },
            ]}
          >
            <Text style={styles.chipText}>{s}</Text>
          </Pressable>
        ))}
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
          onSubmitEditing={() => submit(text)}
        />
        <Pressable
          testID="chat-send"
          accessibilityRole="button"
          onPress={() => submit(text)}
          disabled={streaming || !text.trim()}
          style={({ pressed }) => [
            styles.sendBtn,
            (streaming || !text.trim()) && styles.sendBtnDisabled,
            pressed && { opacity: 0.85 },
          ]}
        >
          <Text style={styles.sendIcon}>↑</Text>
        </Pressable>
      </View>
    </Animated.View>
  );
}

/** 유저 말풍선 — 우측 정렬 프라이머리. */
function UserMessage({ text }: { text: string }) {
  return (
    <View style={styles.userRow}>
      <View style={styles.userBubble}>
        <Text style={styles.userText}>{text}</Text>
      </View>
    </View>
  );
}

/** 어시스턴트 메시지 — 아바타 + 자연어 텍스트 말풍선 + 리치 섹션 카드. */
function AssistantMessage({
  text,
  sections,
  onCta,
  typing,
}: {
  text: string;
  sections: MessageSection[];
  onCta?: (c: Cta) => void;
  typing?: boolean;
}) {
  return (
    <View style={styles.assistantRow}>
      <View style={styles.smallAvatar}>
        <Text style={styles.smallAvatarText}>AI</Text>
      </View>
      <View style={styles.assistantCol}>
        {typing ? (
          <View style={styles.textBubble}>
            <TypingDots />
          </View>
        ) : null}
        {text ? (
          <View style={styles.textBubble} testID="assistant-text">
            <Text style={styles.assistantText}>{text}</Text>
          </View>
        ) : null}
        {sections.map((s, i) => (
          <SectionView key={i} section={s} onCta={onCta} />
        ))}
      </View>
    </View>
  );
}

/** 타이핑 인디케이터 — 점 3개 페이드 루프. */
function TypingDots() {
  const a = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(a, { toValue: 1, duration: 500, useNativeDriver: false }),
        Animated.timing(a, { toValue: 0, duration: 500, useNativeDriver: false }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [a]);
  const op = (lo: number) => a.interpolate({ inputRange: [0, 1], outputRange: [lo, 1] });
  return (
    <View style={styles.typing}>
      {[0.3, 0.5, 0.7].map((lo, i) => (
        <Animated.View key={i} style={[styles.typingDot, { opacity: op(lo) }]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    borderBottomWidth: 1,
    borderBottomColor: color.border,
    backgroundColor: color.surface,
  },
  backBtn: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: -space.sm,
  },
  backIcon: { fontSize: 28, color: color.text, lineHeight: 30 },

  empty: { alignItems: 'center', paddingVertical: space.xl, gap: space.sm },
  emptyAvatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: color.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: space.sm,
  },
  emptyTitle: { fontSize: font.size.lg, fontWeight: font.weight.bold as any, color: color.text },
  emptyDesc: { fontSize: font.size.sm, color: color.textSub, textAlign: 'center', lineHeight: 20 },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: color.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { color: '#fff', fontWeight: font.weight.bold as any, fontSize: font.size.sm },
  headerTitle: {
    fontSize: font.size.lg,
    fontWeight: font.weight.semibold as any,
    color: color.text,
  },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: space.xs, marginTop: 2 },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  statusText: { fontSize: font.size.xs, color: color.textSub },

  scroll: { flex: 1 },
  content: { padding: space.lg, gap: space.sm, maxWidth: 560, width: '100%', alignSelf: 'center' },

  userRow: { alignItems: 'flex-end', marginBottom: space.sm },
  userBubble: {
    backgroundColor: color.primary,
    paddingVertical: space.sm,
    paddingHorizontal: space.lg,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    borderBottomLeftRadius: radius.lg,
    borderBottomRightRadius: radius.sm,
    maxWidth: '85%',
    ...shadow.card,
  },
  userText: { color: '#fff', fontSize: font.size.md, lineHeight: 22 },

  assistantRow: {
    flexDirection: 'row',
    gap: space.sm,
    marginBottom: space.sm,
    alignItems: 'flex-start',
  },
  smallAvatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: color.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  smallAvatarText: { color: color.primaryDark, fontWeight: font.weight.bold as any, fontSize: 11 },
  assistantCol: { flex: 1, gap: space.sm, alignItems: 'flex-start' },
  textBubble: {
    backgroundColor: color.surface,
    borderWidth: 1,
    borderColor: color.border,
    paddingVertical: space.sm,
    paddingHorizontal: space.lg,
    borderTopLeftRadius: radius.sm,
    borderTopRightRadius: radius.lg,
    borderBottomLeftRadius: radius.lg,
    borderBottomRightRadius: radius.lg,
    maxWidth: '92%',
  },
  assistantText: { color: color.text, fontSize: font.size.md, lineHeight: 22 },

  typing: { flexDirection: 'row', gap: 5, paddingVertical: 4 },
  typingDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: color.textMuted },

  chipsBar: { maxHeight: 44, backgroundColor: color.bg },
  chipsContent: { paddingHorizontal: space.lg, paddingVertical: space.sm, gap: space.sm },
  chip: {
    backgroundColor: color.surface,
    borderWidth: 1,
    borderColor: color.border,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
    paddingVertical: 6,
  },
  chipText: { fontSize: font.size.sm, color: color.textSub },

  inputBar: {
    flexDirection: 'row',
    gap: space.sm,
    paddingHorizontal: space.lg,
    paddingTop: space.sm,
    paddingBottom: space.lg,
    borderTopWidth: 1,
    borderTopColor: color.border,
    backgroundColor: color.surface,
    alignItems: 'center',
  },
  input: {
    flex: 1,
    backgroundColor: color.surfaceAlt,
    borderRadius: radius.pill,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    fontSize: font.size.md,
    color: color.text,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: color.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: { backgroundColor: color.textMuted, opacity: 0.5 },
  sendIcon: { color: '#fff', fontSize: 20, fontWeight: font.weight.bold as any, lineHeight: 22 },
});
