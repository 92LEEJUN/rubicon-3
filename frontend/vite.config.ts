import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// react-native → react-native-web 별칭(같은 RN 컴포넌트를 웹/스크린샷/E2E에서 렌더).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "react-native": "react-native-web" },
    extensions: [".web.tsx", ".web.ts", ".tsx", ".ts", ".web.js", ".js"],
  },
  define: { __DEV__: JSON.stringify(false), "process.env.NODE_ENV": JSON.stringify("production") },
});
