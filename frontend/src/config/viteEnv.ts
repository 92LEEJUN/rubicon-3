/**
 * Vite 빌드 시점 환경 변수 접근을 한 곳에 격리한다(ADR-0056).
 *
 * `import.meta`는 Vite 전용 구문이라 jest(babel CJS 변환)에서 파싱되지 않는다. 그래서 이 파일만
 * `import.meta`를 쓰고, jest는 `moduleNameMapper`로 이 모듈을 스텁(빈 객체)으로 치환한다.
 * 프로덕션(Vite)에선 실제 `import.meta.env`가 주입된다.
 */
export const viteEnv: Record<string, string | undefined> =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env ?? {};
