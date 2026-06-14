/** FE 환경 설정(ADR-0056) — resolveAppEnv 우선순위 검증(주입형 env). */
import { resolveAppEnv } from './index';

describe('resolveAppEnv', () => {
  it('VITE_APP_ENV를 최우선으로 본다', () => {
    expect(resolveAppEnv({ VITE_APP_ENV: 'stg', MODE: 'production' })).toBe('stg');
  });

  it('VITE_APP_ENV 없으면 빌드 MODE로 추론한다', () => {
    expect(resolveAppEnv({ MODE: 'production' })).toBe('prd');
    expect(resolveAppEnv({ MODE: 'staging' })).toBe('stg');
  });

  it('미지값/미지정이면 dev로 폴백한다', () => {
    expect(resolveAppEnv({ VITE_APP_ENV: 'qa', MODE: 'development' })).toBe('dev');
    expect(resolveAppEnv({})).toBe('dev');
  });
});
