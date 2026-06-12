/**
 * useResume — 패널 open 시 GET /resume 조회·노출(요구 1·5·6).
 *
 * - has_context=false면 카드 미표시(빈 상태, 요구 1.6).
 * - startFresh(): fresh=true 재호출 + resume 가시성 dismissed(이전 요약 제거, 요구 1.5).
 * - 동의(opted_in) 없으면 개인화 요약(personalized) 제한/비노출(요구 6.2).
 * - 부분 실패는 companion.ts에서 has_context 기준으로 정규화 → 요약만 degraded 노출(요구 5.4).
 *
 * React Query 미설치라 동일 역할(패칭·캐시·무효화)을 경량 훅으로 구현(코드베이스 관례, useHomeData 류).
 */
import { useCallback, useEffect, useState } from "react";
import { getResume } from "../transport/companion";
import type { ApiConfig } from "../transport/api";
import type { ResumePayload } from "../types/contract";
import { companionStore, useCompanionStore } from "./companionStore";
import { useConsent } from "./useConsent";

export type FetchStatus = "idle" | "loading" | "success" | "error";

export function useResume(cfg: ApiConfig, panelOpen: boolean) {
  const { optedIn } = useConsent();
  const { resumeVisibility } = useCompanionStore();
  const [resume, setResume] = useState<ResumePayload | null>(null);
  const [status, setStatus] = useState<FetchStatus>("idle");
  const [fresh, setFresh] = useState(false);

  const fetchResume = useCallback(
    (asFresh: boolean) => {
      let alive = true;
      setStatus("loading");
      getResume(cfg, asFresh)
        .then((p) => {
          if (!alive) return;
          setResume(p);
          setStatus("success");
        })
        .catch(() => {
          if (alive) setStatus("error");
        });
      return () => {
        alive = false;
      };
    },
    [cfg.base, cfg.token], // eslint-disable-line react-hooks/exhaustive-deps
  );

  // 패널 open 시(또는 fresh 변경 시) 조회
  useEffect(() => {
    if (!panelOpen) return;
    return fetchResume(fresh);
  }, [panelOpen, fresh, fetchResume]);

  const startFresh = useCallback(() => {
    companionStore.setResumeVisibility("dismissed"); // 이전 요약 화면 제거(요구 1.5)
    setFresh(true);
    setResume(null);
  }, []);

  // 동의 게이트 — 미동의면 개인화 요약 필드를 비노출/제한(요구 6.2)
  const gated = applyConsentGate(resume, optedIn);

  // has_context=false거나 사용자가 '새로 시작'으로 닫았으면 카드 미표시(요구 1.6)
  const hasContext = !!gated?.has_context && resumeVisibility === "shown" && !fresh;

  return {
    resume: gated,
    hasContext,
    startFresh,
    status,
    /** 부분 실패(요약만 있고 open_loops 누락)면 degraded(요구 5.4). */
    degraded: !!gated?.has_context && (gated.open_loops === undefined),
  };
}

/** 미동의 시 개인화 요약(personalized) 비노출/제한. open-loop는 비개인화로 유지. */
function applyConsentGate(p: ResumePayload | null, optedIn: boolean): ResumePayload | null {
  if (!p) return p;
  if (optedIn) return p;
  if (p.personalized) {
    // 개인화 요약·facts 제거, 미해결 목록·시간감만 남긴다(중립 정보).
    const { summary: _s, facts: _f, ...rest } = p;
    return { ...rest };
  }
  return p;
}
