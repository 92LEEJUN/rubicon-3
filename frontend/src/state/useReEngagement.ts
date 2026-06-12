/**
 * useReEngagement — GET /reengagement 조회·배너 노출·deliver·dismiss(요구 3·6).
 *
 * 동의 게이트(요구 6.1) — 미동의면 **조회 자체를 수행하지 않는다**(no-op, 네트워크·노출 원천 차단).
 * 노출 시 POST /reengagement/deliver로 재노출 억제(요구 3.2). `{}`/실패면 미노출(요구 3.4).
 * 동의가 철회되면 노출 중 배너도 즉시 제거(요구 6.3).
 */
import { useCallback, useEffect, useState } from "react";
import { getReEngagement } from "../transport/companion";
import type { ApiConfig } from "../transport/api";
import type { ReEngagement } from "../types/contract";
import { companionStore, useCompanionStore } from "./companionStore";
import { useConsent } from "./useConsent";

export function useReEngagement(cfg: ApiConfig, enabled = true) {
  const { optedIn } = useConsent();
  const { bannerState } = useCompanionStore();
  const [banner, setBanner] = useState<ReEngagement | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // 미동의면 조회를 게이트하고, 노출 중이던 배너도 제거(요구 6.1·6.3)
  useEffect(() => {
    if (!enabled || !optedIn) {
      setBanner(null);
      companionStore.setBannerState("hidden");
      return;
    }
    if (dismissed) return;
    let alive = true;
    // 노출 = 전달 확정(deliver)으로 조회 → 재노출 억제(요구 3.2)
    getReEngagement(cfg, /* deliver */ true).then((re) => {
      if (!alive) return;
      if (re) {
        setBanner(re);
        companionStore.setBannerState("shown");
      } else {
        setBanner(null);
        companionStore.setBannerState("hidden"); // {} → 미노출(요구 3.4)
      }
    });
    return () => {
      alive = false;
    };
  }, [cfg.base, cfg.token, enabled, optedIn, dismissed]); // eslint-disable-line react-hooks/exhaustive-deps

  const dismiss = useCallback(() => {
    setDismissed(true);
    setBanner(null);
    companionStore.setBannerState("dismissed"); // 숨김 + 재노출 안 함(요구 3.5)
  }, []);

  // 노출 여부 — 미동의/닫힘/빈 응답이면 노출 안 함
  const visible = !!banner && optedIn && !dismissed && bannerState === "shown";

  return {
    banner: visible ? banner : null,
    primaryRef: banner?.primary_ref ?? null,
    dismiss,
  };
}
