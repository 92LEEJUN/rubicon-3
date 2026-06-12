/**
 * OpenLoopList / OpenLoopItem — 미해결 스레드 목록(요구 2).
 *
 * - kind(issue|order|flow)·요약·우선순위를 구분해 렌더(요구 2.1).
 * - 항목 탭 → onOpen(ref)로 /chat 재진입(요구 2.2).
 * - resolve/dismiss 버튼(요구 2.3) — 낙관적 갱신·실패 롤백은 useOpenLoops가 담당.
 * - 실패 시 에러 안내·재시도(요구 2.5).
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Badge, Caption } from "./primitives";
import { color, font, radius, space } from "../design/tokens";
import type { OpenLoop, OpenLoopKind } from "../types/contract";

const KIND_KO: Record<OpenLoopKind, string> = {
  issue: "미해결 이슈",
  order: "진행 주문",
  flow: "보류 흐름",
};
const KIND_TONE: Record<OpenLoopKind, "danger" | "primary" | "warning"> = {
  issue: "danger",
  order: "primary",
  flow: "warning",
};

export function OpenLoopItem({
  loop,
  onOpen,
  onResolve,
  onDismiss,
  pending,
}: {
  loop: OpenLoop;
  onOpen?: (ref: string) => void;
  onResolve?: (ref: string) => void;
  onDismiss?: (ref: string) => void;
  pending?: boolean;
}) {
  return (
    <View style={styles.item} testID={`open-loop-${loop.ref}`}>
      <Pressable
        testID={`open-loop-tap-${loop.ref}`}
        accessibilityRole="button"
        onPress={() => onOpen?.(loop.ref)}
        style={styles.itemMain}
        disabled={pending}
      >
        <Badge label={KIND_KO[loop.kind] ?? loop.kind} tone={KIND_TONE[loop.kind] ?? "neutral"} />
        <View style={{ flex: 1 }}>
          <Text style={styles.summary}>{loop.summary ?? loop.ref}</Text>
        </View>
        {pending ? <Caption>처리 중…</Caption> : null}
      </Pressable>
      <View style={styles.actions}>
        <Pressable
          testID={`open-loop-resolve-${loop.ref}`}
          accessibilityRole="button"
          onPress={() => onResolve?.(loop.ref)}
          disabled={pending}
          style={({ pressed }) => [styles.actionBtn, pressed && { opacity: 0.7 }]}
        >
          <Text style={[styles.actionText, { color: color.success }]}>해결</Text>
        </Pressable>
        <Pressable
          testID={`open-loop-dismiss-${loop.ref}`}
          accessibilityRole="button"
          onPress={() => onDismiss?.(loop.ref)}
          disabled={pending}
          style={({ pressed }) => [styles.actionBtn, pressed && { opacity: 0.7 }]}
        >
          <Text style={[styles.actionText, { color: color.textMuted }]}>닫기</Text>
        </Pressable>
      </View>
    </View>
  );
}

export function OpenLoopList({
  loops,
  onOpen,
  onResolve,
  onDismiss,
  isPending,
  error,
  onRetryDismissError,
}: {
  loops: OpenLoop[];
  onOpen?: (ref: string) => void;
  onResolve?: (ref: string) => void;
  onDismiss?: (ref: string) => void;
  isPending?: (ref: string) => boolean;
  error?: string | null;
  onRetryDismissError?: () => void;
}) {
  if (!loops.length && !error) return null;
  return (
    <View style={styles.list} testID="open-loop-list">
      {loops.map((l) => (
        <OpenLoopItem
          key={l.id ?? l.ref}
          loop={l}
          onOpen={onOpen}
          onResolve={onResolve}
          onDismiss={onDismiss}
          pending={isPending?.(l.ref)}
        />
      ))}
      {error ? (
        <Pressable testID="open-loop-error" onPress={onRetryDismissError} style={styles.errorBox}>
          <Caption>{error}</Caption>
          <Text style={styles.retry}>다시 시도</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: space.sm, marginTop: space.sm },
  item: {
    backgroundColor: color.surfaceAlt,
    borderRadius: radius.md,
    padding: space.md,
    gap: space.sm,
  },
  itemMain: { flexDirection: "row", alignItems: "center", gap: space.sm },
  summary: { fontSize: font.size.sm, color: color.text, lineHeight: 20 },
  actions: { flexDirection: "row", justifyContent: "flex-end", gap: space.md },
  actionBtn: { paddingVertical: 4, paddingHorizontal: space.sm },
  actionText: { fontSize: font.size.sm, fontWeight: font.weight.semibold as any },
  errorBox: {
    backgroundColor: color.dangerTint,
    borderRadius: radius.md,
    padding: space.sm,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  retry: { fontSize: font.size.sm, color: color.danger, fontWeight: font.weight.semibold as any },
});
