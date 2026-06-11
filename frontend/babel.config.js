// Jest 트랜스파일용(런타임). 타입체크는 게이트하지 않는다(esbuild/babel 트랜스파일).
module.exports = {
  presets: [
    ["@babel/preset-env", { targets: { node: "current" } }],
    ["@babel/preset-react", { runtime: "automatic" }],
    "@babel/preset-typescript",
  ],
};
