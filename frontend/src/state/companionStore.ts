/**
 * companion 가시성 스토어 — 화면 간 공유되는 경량 UI 상태(frontend-architecture §11, design §상태 환원).
 *
 * ADR-0023은 zustand를 권하지만 이 코드베이스는 plain React를 쓰므로(zustand 미설치),
 * 동일 역할을 하는 경량 모듈 스토어 + 구독 훅으로 둔다. 패널/배너/resume 노출 여부만 담는다.
 */
import { useEffect, useState } from "react";

export type ResumeVisibility = "shown" | "dismissed";
export type BannerState = "hidden" | "shown" | "dismissed";

export interface CompanionState {
  panelOpen: boolean;
  resumeVisibility: ResumeVisibility;
  bannerState: BannerState;
  screenContext: Record<string, unknown> | null; // 현재 화면 맥락(재진입 시 주입)
}

const initial: CompanionState = {
  panelOpen: false,
  resumeVisibility: "shown",
  bannerState: "hidden",
  screenContext: null,
};

type Listener = (s: CompanionState) => void;

let state: CompanionState = initial;
const listeners = new Set<Listener>();

function set(patch: Partial<CompanionState>): void {
  state = { ...state, ...patch };
  for (const l of listeners) l(state);
}

export const companionStore = {
  get: () => state,
  setPanelOpen: (open: boolean) => set({ panelOpen: open }),
  setResumeVisibility: (v: ResumeVisibility) => set({ resumeVisibility: v }),
  setBannerState: (b: BannerState) => set({ bannerState: b }),
  setScreenContext: (ctx: Record<string, unknown> | null) => set({ screenContext: ctx }),
  /** 테스트 격리용 — 초기 상태로 되돌린다. */
  reset: () => {
    state = initial;
    for (const l of listeners) l(state);
  },
};

/** 컴패니언 가시성 상태 구독 훅. */
export function useCompanionStore(): CompanionState {
  const [snap, setSnap] = useState<CompanionState>(state);
  useEffect(() => {
    setSnap(state);
    listeners.add(setSnap);
    return () => {
      listeners.delete(setSnap);
    };
  }, []);
  return snap;
}
