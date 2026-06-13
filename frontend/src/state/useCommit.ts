/**
 * useCommit — 커밋 라운드트립 상태 관리(SHARED CONTRACT §commit, 요구 ⑤⑥).
 *
 * commit CTA(order/booking) → REST commit. 결과에 따라 게이트 상태를 토글한다:
 *  - confirm(409): pending 확인 템플릿 보관 → 사용자가 confirm()하면 confirmed:true 재제출.
 *  - login(401): 로그인 월 표시 → login()으로 토큰 확보 후 재시도, 또는 dismiss.
 *  - ok: onCommitted 콜백(분석 order_confirmed 등).
 *
 * 토큰은 게스트(없음)→로그인(있음)로 바뀔 수 있어 ref로 동적 주입(BFF가 매핑).
 */
import { useCallback, useRef, useState } from "react";
import type { ApiConfig } from "../transport/api";
import { commit, type CommitKind, type CommitResult } from "../transport/commit";
import { track } from "../analytics/track";
import type { Cta, Template } from "../types/contract";

interface PendingCommit {
  kind: CommitKind;
  payload: Record<string, unknown>;
}

export interface UseCommit {
  /** 확인 다이얼로그(409)에 표시할 템플릿. null이면 미표시. */
  confirmTemplate: Template | null;
  /** 로그인 월(401) 표시 여부. */
  showLogin: boolean;
  /** 커밋 진행 중(중복 탭 방지). */
  busy: boolean;
  /** commit CTA 시작 — kind/payload 추출 후 1차 호출. */
  start(cta: Cta): Promise<void>;
  /** login CTA — 보류 커밋 없이 로그인 월만 연다. */
  openLogin(): void;
  /** 확인 다이얼로그 "확정" — confirmed:true 재제출. */
  confirm(): Promise<void>;
  /** 확인 다이얼로그 "취소". */
  cancelConfirm(): void;
  /** 로그인 월 "로그인" — 토큰 확보(데모: placeholder) 후 보류 커밋 재시도. */
  login(): Promise<void>;
  /** 로그인 월 "게스트로 계속"(닫기). */
  dismissLogin(): void;
}

export function useCommit(
  cfg: ApiConfig,
  opts?: { onCommitted?: (kind: CommitKind, data?: any) => void; onLogin?: () => string | undefined },
): UseCommit {
  const [confirmTemplate, setConfirmTemplate] = useState<Template | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [busy, setBusy] = useState(false);
  const pending = useRef<PendingCommit | null>(null);
  // 토큰은 로그인 시 갱신될 수 있으므로 ref로 최신값 유지(게스트→로그인).
  const tokenRef = useRef<string | undefined>(cfg.token);

  const cfgNow = useCallback((): ApiConfig => ({ base: cfg.base, token: tokenRef.current }), [cfg.base]);

  const apply = useCallback(
    (res: CommitResult, kind: CommitKind) => {
      if (res.status === "confirm") {
        pending.current = { kind, payload: res.payload };
        setConfirmTemplate(res.template);
        track("checkout_shown", { kind });
      } else if (res.status === "login") {
        setConfirmTemplate(null);
        setShowLogin(true);
      } else if (res.status === "ok") {
        setConfirmTemplate(null);
        setShowLogin(false);
        pending.current = null;
        track("order_confirmed", { kind });
        opts?.onCommitted?.(kind, res.data);
      } else {
        // error — 게이트를 닫고 조용히 종료(상위에서 폴백 메시지 가능).
        setConfirmTemplate(null);
        track("error_shown", { code: res.code ?? "commit_failed" });
      }
    },
    [opts],
  );

  const start = useCallback(
    async (cta: Cta) => {
      if (cta.action !== "commit" || (cta.kind !== "order" && cta.kind !== "booking")) return;
      const kind = cta.kind as CommitKind;
      pending.current = { kind, payload: (cta.payload as Record<string, unknown>) ?? {} };
      setBusy(true);
      try {
        const res = await commit(cfgNow(), kind, pending.current.payload, false);
        apply(res, kind);
      } finally {
        setBusy(false);
      }
    },
    [apply, cfgNow],
  );

  const confirm = useCallback(async () => {
    const p = pending.current;
    if (!p) return;
    setBusy(true);
    try {
      const res = await commit(cfgNow(), p.kind, p.payload, true);
      apply(res, p.kind);
    } finally {
      setBusy(false);
    }
  }, [apply, cfgNow]);

  const cancelConfirm = useCallback(() => {
    setConfirmTemplate(null);
    pending.current = null;
  }, []);

  const login = useCallback(async () => {
    // 데모 placeholder — 실제 로그인 플로우(토큰 발급)는 후속. onLogin이 토큰을 주면 주입.
    const tok = opts?.onLogin?.() ?? "demo-user-token";
    tokenRef.current = tok;
    setShowLogin(false);
    // 보류 커밋이 있으면 로그인 후 재시도(다시 1차 호출 — 이번엔 토큰 동반).
    const p = pending.current;
    if (p) {
      setBusy(true);
      try {
        const res = await commit(cfgNow(), p.kind, p.payload, false);
        apply(res, p.kind);
      } finally {
        setBusy(false);
      }
    }
  }, [apply, cfgNow, opts]);

  const dismissLogin = useCallback(() => {
    setShowLogin(false);
    pending.current = null;
  }, []);

  const openLogin = useCallback(() => {
    pending.current = null; // 보류 커밋 없음 — 순수 로그인 트리거
    setShowLogin(true);
  }, []);

  return { confirmTemplate, showLogin, busy, start, openLogin, confirm, cancelConfirm, login, dismissLogin };
}
