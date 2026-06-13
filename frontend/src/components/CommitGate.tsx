/**
 * 커밋 게이트 UI — 확인(409)·로그인(401) 오버레이(SHARED CONTRACT §commit).
 *
 *  - ConfirmDialog: 409 ConfirmationRequired → 확인 템플릿을 보여주고 "확정"하면 confirmed:true 재제출.
 *  - LoginWall: 401 LoginRequired → 로그인 월(게스트는 commit만 게이트). 데모에선 placeholder.
 *
 * 두 컴포넌트 모두 self-contained 오버레이 — ChatPanel/LiveChat에서 상태로 토글한다.
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { color, font, radius, space } from "../design/tokens";
import { Button } from "./primitives";
import { TemplateView } from "../templates";
import type { Template } from "../types/contract";

/** 반투명 백드롭 + 하단/중앙 카드 공통 셸. */
function Overlay({ children, testID }: { children: React.ReactNode; testID?: string }) {
  return (
    <View style={styles.backdrop} testID={testID}>
      <View style={styles.sheet}>{children}</View>
    </View>
  );
}

/** 409 확인 다이얼로그 — 확정/취소. confirm 시 onConfirm(2-step 재제출). */
export function ConfirmDialog({
  template,
  onConfirm,
  onCancel,
  busy,
}: {
  template: Template;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  return (
    <Overlay testID="commit-confirm">
      <Text style={styles.title}>한 번 더 확인해 주세요</Text>
      <View style={styles.body}>
        <TemplateView template={template} />
      </View>
      <View style={styles.actions}>
        <Button label="취소" variant="secondary" testID="confirm-cancel" onPress={onCancel} />
        <Button label={busy ? "확정 중…" : "확정"} variant="primary" testID="confirm-ok"
                onPress={busy ? undefined : onConfirm} />
      </View>
    </Overlay>
  );
}

/**
 * 401 로그인 월 — placeholder(실 로그인 플로우는 후속). "로그인"하면 데모상 로그인 처리(onLogin),
 * "게스트로 계속"은 월을 닫는다(advisory는 게스트로 가능, commit만 막힘).
 */
export function LoginWall({
  onLogin,
  onDismiss,
}: {
  onLogin: () => void;
  onDismiss: () => void;
}) {
  return (
    <Overlay testID="login-wall">
      <Text style={styles.title}>로그인이 필요해요</Text>
      <Text style={styles.desc}>
        주문·예약을 확정하려면 로그인이 필요합니다.{"\n"}
        둘러보기·상담은 로그인 없이 이용할 수 있어요.
      </Text>
      <View style={styles.actions}>
        <Pressable testID="login-dismiss" onPress={onDismiss} style={styles.ghostBtn}>
          <Text style={styles.ghostText}>게스트로 계속</Text>
        </Pressable>
        <Button label="로그인" variant="primary" testID="login-cta" onPress={onLogin} />
      </View>
      <Text style={styles.note}>* 데모 placeholder — 실제 로그인 연동은 후속 작업입니다.</Text>
    </Overlay>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.35)", alignItems: "center", justifyContent: "center",
    padding: space.lg, zIndex: 10,
  },
  sheet: {
    backgroundColor: color.surface, borderRadius: radius.lg, padding: space.lg,
    width: "100%", maxWidth: 420, gap: space.md,
  },
  title: { fontSize: font.size.lg, fontWeight: font.weight.semibold as any, color: color.text },
  desc: { fontSize: font.size.md, color: color.textSub, lineHeight: 22 },
  body: { marginVertical: space.xs },
  actions: { flexDirection: "row", justifyContent: "flex-end", gap: space.sm, marginTop: space.sm },
  ghostBtn: { borderRadius: radius.pill, paddingVertical: space.md, paddingHorizontal: space.lg, justifyContent: "center" },
  ghostText: { fontSize: font.size.md, color: color.textSub, fontWeight: font.weight.medium as any },
  note: { fontSize: font.size.xs, color: color.textMuted },
});
