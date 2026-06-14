/**
 * FE 환경 설정 — 환경 계층(dev/stg/prd) 단일 소스(ADR-0056, 12-Factor III·X).
 *
 * 명시 `VITE_APP_ENV`가 있으면 우선, 없으면 빌드 모드(`MODE`: production→prd, staging→stg, 그 외 dev)로
 * 추론한다. Vite 전용 `import.meta`는 `viteEnv`로 격리(jest는 스텁). `apiBase`/mock 감지(ADR-0051)는 유지.
 */
import { viteEnv } from './viteEnv';

export type AppEnv = 'dev' | 'stg' | 'prd';

const ENVS: AppEnv[] = ['dev', 'stg', 'prd'];

/** APP_ENV 정규화 — VITE_APP_ENV 우선, 없으면 빌드 모드로 추론, 미지값은 dev. */
export function resolveAppEnv(env: Record<string, string | undefined> = viteEnv): AppEnv {
  const explicit = (env.VITE_APP_ENV || '').toLowerCase();
  if (ENVS.includes(explicit as AppEnv)) return explicit as AppEnv;
  const mode = (env.MODE || '').toLowerCase();
  if (mode === 'production') return 'prd';
  if (mode === 'staging') return 'stg';
  return 'dev';
}

export const APP_ENV: AppEnv = resolveAppEnv();
export const IS_PROD = APP_ENV === 'prd';
export const IS_DEV = APP_ENV === 'dev';

/** 환경 메타(디버그·분기용). apiBase는 호출측(main.tsx)이 주입하던 방식을 유지한다. */
export const config = {
  appEnv: APP_ENV,
  isProd: IS_PROD,
  isDev: IS_DEV,
} as const;
