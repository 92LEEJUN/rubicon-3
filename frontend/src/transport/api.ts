/**
 * BFF REST 클라이언트 — 실데이터 조회(api-contract §2.2).
 * apiBase 미설정(정적 배포)이거나 호출 실패면 **조용히 fixtures로 폴백**(에러 노출 없음).
 * → BE 미연결에도 화면이 항상 채워진다(graceful degradation).
 */
import { homeSummary, recommendation, statusTracker } from "../fixtures/journeys";

export interface ApiConfig { base?: string; token?: string }

async function get<T>(cfg: ApiConfig, path: string, fallback: T): Promise<T> {
  if (!cfg.base) return fallback;
  try {
    const r = await fetch(cfg.base + path, {
      headers: cfg.token ? { Authorization: `Bearer ${cfg.token}` } : {},
    });
    if (!r.ok) return fallback;
    return (await r.json()) as T;
  } catch {
    return fallback; // 네트워크 실패 → 폴백(에러 숨김)
  }
}

/** 홈 요약(home_summary.data) — 기기·알림·추천. 폴백=fixture. */
export async function getHome(cfg: ApiConfig): Promise<any> {
  const res = await get<any>(cfg, "/home", homeSummary);
  return res?.data ?? res;
}

/** 추천 제품 목록. 폴백=fixture 추천. */
export async function getRecommendations(cfg: ApiConfig): Promise<any[]> {
  const fb = (recommendation.template.data as any).products ?? [];
  return get<any[]>(cfg, "/catalog/recommend", fb);
}

/** 주문 이력. 폴백=fixture status_tracker(데모 진행). */
export async function getOrders(cfg: ApiConfig): Promise<any[]> {
  return get<any[]>(cfg, "/orders", []);
}

/** 예약 이력. */
export async function getBookings(cfg: ApiConfig): Promise<any[]> {
  return get<any[]>(cfg, "/bookings", []);
}

export { statusTracker };
