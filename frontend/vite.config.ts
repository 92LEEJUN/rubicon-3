import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// react-native → react-native-web 별칭(같은 RN 컴포넌트를 웹/스크린샷/E2E에서 렌더).
// base: GitHub Pages는 /rubicon-3/ 하위라 DEPLOY_BASE로 주입(로컬/Vercel/E2E는 "/").
export default defineConfig({
  base: process.env.DEPLOY_BASE || "/",
  plugins: [react()],
  // 아키텍처 문서(../docs/*.md)를 ?raw로 번들 — dev 서버도 레포 루트 상위 접근 허용.
  server: { fs: { allow: [".."] } },
  resolve: {
    alias: { "react-native": "react-native-web" },
    extensions: [".web.tsx", ".web.ts", ".tsx", ".ts", ".web.js", ".js"],
  },
  // react-native-web의 Animated 등이 `global`을 참조한다 — 브라우저 번들에선 globalThis로 매핑
  // (없으면 프로덕션 빌드에서 ReferenceError: global is not defined). 표준 RNW×Vite 설정.
  define: {
    __DEV__: JSON.stringify(false),
    "process.env.NODE_ENV": JSON.stringify("production"),
    global: "globalThis",
  },
});
