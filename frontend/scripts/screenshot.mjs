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
  { name: "chat-j1", screen: "chat" },
  { name: "gallery", screen: "gallery" },
];
for (const s of SHOTS) {
  await page.goto(`http://localhost:${PORT}/?screen=${s.screen}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, `${s.name}.png`), fullPage: true });
  console.log("captured", s.name);
}
await browser.close();
server.close();
