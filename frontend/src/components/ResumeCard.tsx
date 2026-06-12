/**
 * ResumeCard — 패널 상단 이어가기 카드(요구 1).
 *
 * summary + elapsed_label(상대시간) + OpenLoopList(우선순위 순) + '이어가기'/'새로 시작'.
 * has_context=false면 렌더 안 함(빈 상태, 요구 1.6) — 가시성 판단은 useResume.hasContext가 한다.
 * degraded(부분 실패)면 요약만/축소 노출(요구 5.4). 동의 게이트는 useResume가 요약을 비운다(요구 6.2).
 */
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Button, Caption, Card, Title } from "./primitives";
import { OpenLoopList } from "./OpenLoopList";
import { color, font, space } from "../design/tokens";
import type { OpenLoop, ResumePayload } from "../types/contract";

export function ResumeCard({
  resume,
  loops,
  onContinue,
  onStartFresh,
  onOpenLoop,
  onResolve,
  onDismiss,
  isPending,
  loopError,
  onRetryLoopError,
  degraded,
}: {
  resume: ResumePayload;
  loops: OpenLoop[];
  onContinue?: () => void;
  onStartFresh?: () => void;
  onOpenLoop?: (ref: string) => void;
  onResolve?: (ref: string) => void;
  onDismiss?: (ref: string) => void;
  isPending?: (ref: string) => boolean;
  loopError?: string | null;
  onRetryLoopError?: () => void;
  degraded?: boolean;
}) {
  return (
    <Card testID="resume-card" style={styles.card}>
      <View style={styles.head}>
        <Title>이어서 도와드릴까요?</Title>
        {resume.elapsed_label ? (
          <View testID="resume-elapsed">
            <Caption>{resume.elapsed_label}</Caption>
          </View>
        ) : null}
      </View>

      {resume.summary ? (
        <Text style={styles.summary} testID="resume-summary">
          {resume.summary}
        </Text>
      ) : (
        <Text style={styles.summaryMuted} testID="resume-summary-empty">
          이전 대화를 이어서 진행할 수 있어요.
        </Text>
      )}

      {degraded ? <Caption>일부 정보를 불러오지 못했어요. 가능한 내용만 보여드려요.</Caption> : null}

      {!degraded ? (
        <OpenLoopList
          loops={loops}
          onOpen={onOpenLoop}
          onResolve={onResolve}
          onDismiss={onDismiss}
          isPending={isPending}
          error={loopError}
          onRetryDismissError={onRetryLoopError}
        />
      ) : null}

      <View style={styles.actions}>
        <Button label="이어가기" testID="resume-continue" variant="primary" onPress={onContinue} />
        <Button label="새로 시작" testID="resume-fresh" variant="secondary" onPress={onStartFresh} />
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginBottom: space.md, gap: space.sm },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  summary: { fontSize: font.size.md, color: color.text, lineHeight: 22 },
  summaryMuted: { fontSize: font.size.md, color: color.textSub, lineHeight: 22 },
  actions: { flexDirection: "row", gap: space.sm, marginTop: space.sm },
});
