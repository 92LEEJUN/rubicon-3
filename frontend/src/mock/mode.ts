/** Mock 모드 감지(ADR-0051) — apiBase 없으면 mock. `?mock=1`은 강제(main.tsx에서 apiBase 비움). */

/** apiBase가 없으면 BE 미연결 → mock 모드. */
export function isMock(apiBase?: string): boolean {
  return !apiBase;
}

/** URL 쿼리 플래그(브라우저 전용; 비브라우저/테스트는 빈 값). */
export function readQueryFlags(): { mock: boolean; reset: boolean } {
  try {
    const p = new URLSearchParams(window.location.search);
    return { mock: p.get("mock") === "1", reset: p.get("reset") === "1" };
  } catch {
    return { mock: false, reset: false };
  }
}
