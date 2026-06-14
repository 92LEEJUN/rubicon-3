/** 메인 셸 — 상단 브랜드 + 토글(홈↔고객지원) + 하단 고정 채팅바(전 탭 공통, wireframes §6). */
import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { SegmentedTabs } from '../components/SegmentedTabs';
import { HomeScreen } from './HomeScreen';
import { SupportScreen } from './SupportScreen';
import { useHomeData } from '../state/useHomeData';
import { color, font, gradient, radius, space } from '../design/tokens';

export type MainTab = 'home' | 'support';

export function MainShell({
  initialTab = 'home',
  apiBase,
  token,
  onOpenChat,
  onGallery,
  onDocs,
}: {
  initialTab?: MainTab;
  apiBase?: string;
  token?: string;
  onOpenChat?: (q?: string) => void;
  onGallery?: () => void;
  onDocs?: () => void;
}) {
  const [tab, setTab] = useState<MainTab>(initialTab);
  const [draft, setDraft] = useState('');
  const data = useHomeData({ base: apiBase, token });

  // 전송(또는 엔터) 시에만 채팅을 연다 — 바를 탭하면 그 자리에서 커서만 놓인다.
  function submit() {
    onOpenChat?.(draft.trim());
    setDraft('');
  }

  return (
    <View style={styles.root} testID="screen-main">
      <View style={styles.header}>
        <View style={styles.brandRow}>
          <Text style={styles.brand}>삼성 AI 컨시어지</Text>
          {onDocs && (
            <Pressable onPress={onDocs} testID="open-docs" accessibilityRole="link">
              <Text style={styles.docsLink}>문서 →</Text>
            </Pressable>
          )}
        </View>
        <View style={{ height: space.md }} />
        <SegmentedTabs
          value={tab}
          onChange={setTab}
          options={[
            { key: 'home', label: '홈' },
            { key: 'support', label: '고객지원' },
          ]}
        />
      </View>

      {tab === 'home' ? (
        <HomeScreen data={data} onOpenChat={(q) => onOpenChat?.(q)} onGallery={onGallery} />
      ) : (
        <SupportScreen data={data} onAsk={(q) => onOpenChat?.(q)} />
      )}

      {/* 하단 고정 채팅바(홈·CS 공통) — 그 자리에서 입력, 전송 시에만 채팅 열림 */}
      <View style={styles.chatBar}>
        <TextInput
          testID="chat-bar-input"
          style={styles.chatInput}
          value={draft}
          onChangeText={setDraft}
          placeholder="가전 문제·부품 주문을 물어보세요"
          placeholderTextColor={color.textMuted}
          onSubmitEditing={submit}
          returnKeyType="send"
        />
        <Pressable
          testID="open-chat"
          accessibilityRole="button"
          onPress={submit}
          style={styles.chatSend}
        >
          <Text style={styles.chatSendIcon}>↑</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  header: {
    paddingHorizontal: space.lg,
    paddingTop: space.lg,
    paddingBottom: space.md,
    backgroundColor: color.bg,
    maxWidth: 480,
    width: '100%',
    alignSelf: 'center',
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  brand: { fontSize: font.size.lg, color: color.text, fontWeight: font.weight.bold as any },
  docsLink: { fontSize: font.size.sm, color: color.textMuted, fontWeight: '600' },
  chatBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    paddingHorizontal: space.lg,
    paddingTop: space.sm,
    paddingBottom: space.lg,
    backgroundColor: color.surface,
    borderTopWidth: 1,
    borderTopColor: color.border,
    maxWidth: 480,
    width: '100%',
    alignSelf: 'center',
  },
  chatInput: {
    flex: 1,
    backgroundColor: color.surfaceAlt,
    borderRadius: radius.pill,
    paddingHorizontal: space.lg,
    paddingVertical: 13,
    fontSize: font.size.md,
    color: color.text,
  },
  chatSend: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: color.primary,
    alignItems: 'center',
    justifyContent: 'center',
    ...({ backgroundImage: gradient.brand } as any),
  },
  chatSendIcon: { color: '#fff', fontSize: 20, fontWeight: font.weight.bold as any },
});
