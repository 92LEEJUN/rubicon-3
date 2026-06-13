/**
 * 컴패니언 BFF 클라이언트 — resume·reengagement·open-loop(api-contract §2.2).
 *
 * 홈 데이터(api.ts)와 달리 **조용한 fixture 폴백을 하지 않는다**:
 *  - open-loop 해소/닫기는 `404`/실패를 구분해야 낙관적 갱신을 롤백할 수 있다(요구 2.5).
 *  - reengagement는 `{}`/실패를 미노출로 다뤄야 한다(요구 3.4).
 * 따라서 결과를 명시적 형태({ ok | notFound | error })로 돌려 호출 훅이 분기한다.
 * apiBase 미설정(정적 배포)이면 네트워크를 타지 않고 빈/null 결과를 돌려준다(폴백·게이트는 훅 책임).
 */
import type { ApiConfig } from './api';
import type { OpenLoop, ReEngagement, ResumePayload } from '../types/contract';

export type ActionKind = 'resolve' | 'dismiss';

export interface MutationResult<T> {
  ok: boolean;
  notFound: boolean; // 404 — 항목 이미 없음(롤백 대상)
  data?: T;
}

function headers(cfg: ApiConfig): Record<string, string> {
  return cfg.token ? { Authorization: `Bearer ${cfg.token}` } : {};
}

/**
 * GET /resume(?fresh). 미설정/실패 시 has_context=false(깨끗한 시작)로 정규화.
 * fresh=true면 이전 맥락 비주입(새 흐름) — 빈 컨텍스트를 받는다.
 */
export async function getResume(cfg: ApiConfig, fresh = false): Promise<ResumePayload> {
  const empty: ResumePayload = { has_context: false };
  if (!cfg.base) return empty;
  try {
    const r = await fetch(cfg.base + '/resume' + (fresh ? '?fresh=true' : ''), {
      headers: headers(cfg),
    });
    if (!r.ok) return empty;
    const body = (await r.json()) as ResumePayload;
    return body ?? empty;
  } catch {
    return empty;
  }
}

/**
 * GET /reengagement. `{}`/실패면 null(미노출). deliver=true면 POST /reengagement/deliver로
 * 전달 확정(재노출 억제, 요구 3.2).
 */
export async function getReEngagement(
  cfg: ApiConfig,
  deliver = false,
): Promise<ReEngagement | null> {
  if (!cfg.base) return null;
  const path = deliver ? '/reengagement/deliver' : '/reengagement';
  try {
    const r = await fetch(cfg.base + path, {
      method: deliver ? 'POST' : 'GET',
      headers: headers(cfg),
    });
    if (!r.ok) return null;
    const body = (await r.json()) as ReEngagement | Record<string, never>;
    return isEmpty(body) ? null : (body as ReEngagement);
  } catch {
    return null;
  }
}

/** POST /open-loops/{ref}/{action}. `404`/실패를 구분해 돌려준다(롤백 판단용, 요구 2.5). */
export async function postOpenLoopAction(
  cfg: ApiConfig,
  ref: string,
  action: ActionKind,
): Promise<MutationResult<OpenLoop>> {
  if (!cfg.base) {
    // 정적 배포(BE 미연결) — 낙관적 갱신을 그대로 확정(데모 모드).
    return { ok: true, notFound: false };
  }
  try {
    const r = await fetch(`${cfg.base}/open-loops/${encodeURIComponent(ref)}/${action}`, {
      method: 'POST',
      headers: headers(cfg),
    });
    if (r.status === 404) return { ok: false, notFound: true };
    if (!r.ok) return { ok: false, notFound: false };
    const data = (await r.json().catch(() => undefined)) as OpenLoop | undefined;
    return { ok: true, notFound: false, data };
  } catch {
    return { ok: false, notFound: false };
  }
}

function isEmpty(o: unknown): boolean {
  return !o || (typeof o === 'object' && Object.keys(o as object).length === 0);
}
