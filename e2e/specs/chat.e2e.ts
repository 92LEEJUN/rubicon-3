/**
 * 브라우저 E2E — 라이브 채팅(FE 웹 → BFF WS → BE 오케스트레이터)으로 대화형 저니 검증.
 * 실제 WebSocket 스트림으로 섹션이 렌더되는지 확인(J1·J5·J3).
 */
import { expect, test } from "@playwright/test";

const WS = "ws://127.0.0.1:8000/chat?token=demo";
const liveUrl = `/?screen=live&ws=${encodeURIComponent(WS)}`;

async function ask(page: any, question: string) {
  await page.goto(liveUrl);
  await expect(page.getByTestId("screen-live")).toBeVisible();
  await page.getByTestId("chat-input").fill(question);
  await page.getByTestId("chat-send").click();
}

test("J1 — 세탁기 5C: 해결 가이드 + 부품 주문 섹션 스트림", async ({ page }) => {
  await ask(page, "세탁기에서 물이 안 빠져요. 해결하고 부품도 주문할래요.");
  await expect(page.getByTestId("section-troubleshoot")).toBeVisible();
  await expect(page.getByText(/배수 호스가 꺾이거나/)).toBeVisible();  // 해결 단계
  await expect(page.getByText("₩12,000")).toBeVisible();        // 배수필터 주문 카드
  await expect(page.getByText("재고 있음")).toBeVisible();
  await page.screenshot({ path: "__screenshots__/e2e-j1-live.png", fullPage: true });
});

test("J5 — 복합: 정수필터 처리 + HEPA 품절 미처리", async ({ page }) => {
  await ask(page, "세탁기 물 안 빠지는 거 해결법 알려주고, 냉장고 정수필터랑 공기청정기 HEPA 필터도 주문해줘");
  await expect(page.getByTestId("section-troubleshoot")).toBeVisible();
  await expect(page.getByText("₩38,000")).toBeVisible();        // 정수필터(재고) 카드
  await expect(page.getByText("미처리")).toBeVisible();          // HEPA 품절
});

test("J3 — HEPA 품절 → 대체 추천", async ({ page }) => {
  await ask(page, "공기청정기 HEPA 필터 주문하고, 새 공기청정기도 추천해줘");
  await expect(page.getByText("미처리")).toBeVisible();          // HEPA 품절 미처리
  await expect(page.getByText("비스포크 큐브 에어 공기청정기")).toBeVisible();  // 추천
});
