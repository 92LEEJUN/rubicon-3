// jest는 vite의 `?raw` import를 모르므로 문서 텍스트를 스텁으로 대체(빌드는 vite가 번들).
module.exports = "(architecture doc text — bundled at build via vite ?raw)";
