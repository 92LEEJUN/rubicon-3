import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// react-native → react-native-web 별칭(같은 RN 컴포넌트를 웹/스크린샷/E2E에서 렌더).
// base: GitHub Pages는 /rubicon-3/ 하위라 DEPLOY_BASE로 주입(로컬/Vercel/E2E는 "/").
export default defineConfig({
  base: process.env.DEPLOY_BASE || "/",
  plugins: [react()],
  resolve: {
    alias: { "react-native": "react-native-web" },
    extensions: [".web.tsx", ".web.ts", ".tsx", ".ts", ".web.js", ".js"],
  },
  define: { __DEV__: JSON.stringify(false), "process.env.NODE_ENV": JSON.stringify("production") },
});
