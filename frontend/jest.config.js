module.exports = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  // react-native → react-native-web (웹 DOM 렌더로 컴포넌트 검증)
  moduleNameMapper: {
    "^react-native$": "react-native-web",
    "\\.md\\?raw$": "<rootDir>/tests/rawMdStub.js",   // vite ?raw 문서 import 스텁
  },
  transform: { "^.+\\.(t|j)sx?$": "babel-jest" },
  testMatch: ["<rootDir>/tests/**/*.test.tsx", "<rootDir>/src/**/*.test.tsx"],
  moduleFileExtensions: ["tsx", "ts", "js", "jsx", "json"],
};
