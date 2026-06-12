/**
 * Playwright 스크린샷 — 빌드된 웹(react-native-web)을 헤드리스 크로미움으로 캡처.
 * PR 첨부용. 사용: npm run build && npm run screenshots
 */
import { chromium } from "playwright";
import http from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

const DIST = path.resolve("dist");
const OUT = path.resolve("__screenshots__");
const PORT = 4173;
const MIME = {
  ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".map": "application/json",
};

function serve() {
  return http.createServer(async (req, res) => {
    let p = decodeURIComponent((req.url || "/").split("?")[0]);
    if (p === "/") p = "/index.html";
    let file = path.join(DIST, p);
    if (!existsSync(file)) file = path.join(DIST, "index.html"); // SPA 폴백
    try {
      const data = await readFile(file);
      res.writeHead(200, { "content-type": MIME[path.extname(file)] || "application/octet-stream" });
      res.end(data);
    } catch {
      res.writeHead(404); res.end("not found");
    }
  });
}

const server = serve().listen(PORT);
await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });

const SHOTS = [
  { name: "home", screen: "home" },
  { name: "support", screen: "support" },
  { name: "chat-j1", screen: "chat" },
  { name: "gallery", screen: "gallery" },
];
for (const s of SHOTS) {
  await page.goto(`http://localhost:${PORT}/?screen=${s.screen}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, `${s.name}.png`), fullPage: true });
  console.log("captured", s.name);
}

// 요구사항 데모 시나리오(R1~R29) — 트랜스크립트 높이에 맞춰 타이트하게 캡처
const tall = await browser.newPage({ viewport: { width: 400, height: 3600 }, deviceScaleFactor: 2 });
for (const id of ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10"]) {
  await tall.goto(`http://localhost:${PORT}/?screen=scenario&id=${id}`, { waitUntil: "networkidle" });
  await tall.waitForTimeout(400);
  const h = await tall.evaluate(() => {
    const root = document.querySelector('[data-testid="screen-scenario"]');
    const sc = document.querySelector('[data-testid="scenario-scroll"]');
    const headerH = root ? root.children[0].getBoundingClientRect().height : 0;
    // ScrollView 내부 콘텐츠 컨테이너(첫 자식)의 실제 높이로 측정
    const inner = sc && sc.firstElementChild ? sc.firstElementChild.getBoundingClientRect().height : 0;
    return Math.ceil(headerH + inner + 16);
  });
  await tall.screenshot({ path: path.join(OUT, `scenario-${id}.png`),
    clip: { x: 0, y: 0, width: 400, height: Math.min(h, 3600) } });
  console.log("captured", `scenario-${id}`, h);
}
await tall.close();
await browser.close();
server.close();
