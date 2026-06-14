/**
 * 실험 클라이언트(S8, ADR-0064) — 실험 정의·로컬 결정적 할당·BE 할당 조회.
 *
 * 계약 권위는 BE 엔드포인트(`GET /internal/experiments/assign`). 여기 `assignLocal`은
 * 오프라인/mock(BE 미연결)·즉시 렌더용 폴백이다 — BE와 **동형 규칙**(토글·holdout·rollout·
 * 가중 분배)을 따르되, 해시는 경량 FNV-1a(새 의존성 금지). 권위 결과가 필요하면
 * `fetchAssignments`로 BE 값을 받아 우선한다.
 *
 * 토글: FE는 BE처럼 env 토글을 못 보므로, "실험 정의(def)가 주어졌는가"로 활성/비활성을
 * 가른다 — def가 없으면 control(회귀 불변). 실제 on/off 권위는 BE.
 */

export interface VariantDef {
  name: string;
  weight?: number; // 상대 가중치(기본 1.0)
}

export interface ExperimentDef {
  key: string;
  variants: VariantDef[];
  control: string; // 폴백/홀드아웃/롤아웃-외 variant
  rollout?: number; // [0,1] 실험 대상 비율(canary). 기본 1.0
  holdout?: number; // [0,1] 제외(control 고정) 비율. 기본 0.0
  salt?: string; // 키별 독립 버킷 솔트
}

/** 결정적 [0,1) 버킷 — FNV-1a 32bit. 같은 입력 → 같은 값(sticky). */
export function bucket(salt: string, key: string, unit: string): number {
  const s = `${salt}:${key}:${unit}`;
  let h = 0x811c9dc5; // FNV offset basis
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    // FNV prime 16777619, 32bit 곱(부호 없는 산술 유지)
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return (h >>> 0) / 0x100000000; // [0,1)
}

function weightedPick(def: ExperimentDef, b: number): string {
  const variants = def.variants ?? [];
  const total = variants.reduce((acc, v) => acc + Math.max(0, v.weight ?? 1), 0);
  if (total <= 0 || variants.length === 0) return def.control;
  const target = b * total;
  let acc = 0;
  for (const v of variants) {
    acc += Math.max(0, v.weight ?? 1);
    if (target < acc) return v.name;
  }
  return variants[variants.length - 1].name;
}

/**
 * 로컬 결정적 할당(BE 동형 규칙) — def 없음/unit 없음 → control.
 * holdout → control · rollout 밖 → control · 그 외 가중 variant.
 */
export function assignLocal(def: ExperimentDef | null | undefined, unit: string | null | undefined): string {
  if (!def) return 'control';
  if (!unit) return def.control;
  const salt = def.salt ?? '';
  const holdout = def.holdout ?? 0;
  const rollout = def.rollout ?? 1;
  if (holdout > 0 && bucket(`${salt}|holdout`, def.key, unit) < holdout) return def.control;
  if (rollout < 1 && bucket(`${salt}|rollout`, def.key, unit) >= rollout) return def.control;
  return weightedPick(def, bucket(`${salt}|assign`, def.key, unit));
}

export interface ExperimentClientConfig {
  /** BFF/BE 베이스 URL. 없으면 fetch 생략(로컬/mock 폴백). */
  base?: string;
  token?: string;
  /** 신원 헤더(있으면 전달). */
  userId?: string;
  guestToken?: string;
  /** 할당 경로(기본 BE 라우트). */
  path?: string;
}

/**
 * BE 권위 할당 조회 — `GET /internal/experiments/assign?keys=...`. 비차단:
 * 실패 시 빈 맵을 반환(호출측이 로컬/ control 폴백). expose=false로 두어 중복 노출 회피
 * (노출은 FE 훅이 1회 발행).
 */
export async function fetchAssignments(
  cfg: ExperimentClientConfig,
  keys: string[],
): Promise<Record<string, string>> {
  if (!cfg.base || keys.length === 0) return {};
  const url =
    cfg.base +
    (cfg.path ?? '/internal/experiments/assign') +
    `?keys=${encodeURIComponent(keys.join(','))}&expose=false`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        ...(cfg.token ? { Authorization: `Bearer ${cfg.token}` } : {}),
        ...(cfg.userId ? { 'X-User-Id': cfg.userId } : {}),
        ...(cfg.guestToken ? { 'X-Guest-Token': cfg.guestToken } : {}),
      },
    });
    if (!res.ok) return {};
    const body = (await res.json()) as { assignments?: Record<string, string> };
    return body.assignments ?? {};
  } catch {
    return {}; // 비차단 — 실험은 UX를 막지 않는다
  }
}
