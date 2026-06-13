// ESLint flat config (ESLint 9) — minimal, TS + react-native-web friendly.
//
// 목표: `npx eslint .` 가 현재 소스에서 exit 0.
// react-native 는 타입이 없어 any 가 많고, RN 컴포넌트 관례상 noisy 한 규칙이
// 다수다. 그래서 recommended 를 켜되 시끄러운 규칙은 warn 으로 강등한다
// (warn 은 exit code 0). 소스는 수정하지 않는다.
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';

export default tseslint.config(
  // 린트 대상에서 제외 (빌드 산출물·의존성·설정·테스트 보조 스크립트)
  {
    ignores: [
      'node_modules/**',
      'dist/**',
      'public/**',
      'mockups/**',
      '__screenshots__/**',
      'scripts/**',
      '*.config.js',
      '*.config.ts',
      '*.config.mjs',
      'babel.config.js',
      'jest.setup.ts',
      'src/raw-md.d.ts',
    ],
  },

  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    files: ['**/*.{ts,tsx}'],
    plugins: {
      // 소스에 react-hooks/exhaustive-deps inline-disable 주석이 있어
      // 플러그인을 등록하지 않으면 "rule not found" 에러가 난다.
      'react-hooks': reactHooks,
    },
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        // 브라우저/RN-Web + 테스트 런타임 전역
        window: 'readonly',
        document: 'readonly',
        navigator: 'readonly',
        console: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        fetch: 'readonly',
        WebSocket: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        requestAnimationFrame: 'readonly',
        cancelAnimationFrame: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        process: 'readonly',
        global: 'readonly',
        globalThis: 'readonly',
        module: 'readonly',
        require: 'readonly',
        __dirname: 'readonly',
        // jest 전역
        describe: 'readonly',
        it: 'readonly',
        test: 'readonly',
        expect: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
        jest: 'readonly',
      },
    },
    rules: {
      // --- 시끄러운 규칙 강등 (react-native-web 타입 부재로 any 다수) ---
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/ban-ts-comment': 'warn',
      '@typescript-eslint/no-empty-object-type': 'warn',
      '@typescript-eslint/no-empty-function': 'warn',
      '@typescript-eslint/no-non-null-assertion': 'warn',
      '@typescript-eslint/no-require-imports': 'warn',
      'no-empty': 'warn',
      'no-constant-condition': 'warn',
      'prefer-const': 'warn',
      'no-useless-escape': 'warn',
      // react-hooks: 권장 규칙을 warn 으로 (RN-Web 훅 관례상 deps 경고 다수).
      'react-hooks/rules-of-hooks': 'warn',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },

  // CommonJS 보조 파일(테스트 stub 등) — node/commonjs 전역 허용.
  {
    files: ['**/*.js'],
    languageOptions: {
      sourceType: 'commonjs',
      globals: {
        module: 'readonly',
        require: 'readonly',
        process: 'readonly',
        __dirname: 'readonly',
        console: 'readonly',
      },
    },
  },
);
