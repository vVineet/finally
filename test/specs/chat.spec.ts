import { test, expect, type Page } from "@playwright/test";
import { resetPortfolio } from "../fixtures/reset";

// Mock trigger phrases are used verbatim from planning/LLM_DESIGN.md §7 --
// the mock is deterministic keyword pattern-matching, not NLU, so an
// invented phrasing would silently fall through to the plain-chat branch
// and fail for the wrong reason (per the coordinator's task brief).

async function waitForLivePrice(page: Page, ticker: string): Promise<void> {
  const priceCell = page.getByTestId(`watchlist-row-${ticker}`).getByTestId("price-cell");
  await expect(priceCell).not.toHaveText("—", { timeout: 15_000 });
}

async function sendChat(page: Page, text: string) {
  await page.getByLabel("Chat message").fill(text);
  await page.getByTestId("chat-send-button").click();
}

test.describe("AI chat with a mocked trade (PLAN §12, LLM_MOCK=true)", () => {
  test.beforeEach(async ({ request, page }) => {
    await resetPortfolio(request);
    await page.goto("/");
    await waitForLivePrice(page, "AAPL");
  });

  test("a trade instruction executes and renders a success chip", async ({ page }) => {
    await sendChat(page, "Buy 10 shares of AAPL");

    const assistantMsg = page.getByTestId("chat-message").filter({ hasText: "I'll buy 10 AAPL." }).last();
    await expect(assistantMsg).toBeVisible();
    // The model's prose never claims completion (LLM_DESIGN.md §2) --
    // separate execution chip carries the real outcome.
    await expect(assistantMsg.getByTestId("trade-chip-success")).toContainText("Bought 10 AAPL @ $");

    // Real side effects: position appears, cash decreases.
    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
    await expect(page.getByTestId("position-row-AAPL").locator("td").nth(1)).toHaveText("10");
  });

  test("a trade the account can't afford is executed against real state and reported as a failure chip", async ({ page }) => {
    await sendChat(page, "Buy 100000 AAPL");

    const assistantMsg = page.getByTestId("chat-message").filter({ hasText: "I'll buy 100000 AAPL." }).last();
    await expect(assistantMsg).toBeVisible();
    const chip = assistantMsg.getByTestId("trade-chip-failed");
    await expect(chip).toBeVisible();
    await expect(chip).toContainText("Insufficient cash");

    // No position was created by the failed trade.
    await expect(page.getByTestId("position-row-AAPL")).not.toBeVisible();
  });

  test("a watchlist instruction executes and renders a success chip", async ({ page }) => {
    await sendChat(page, "Add PYPL to my watchlist");

    const assistantMsg = page.getByTestId("chat-message").last();
    await expect(assistantMsg.getByTestId("watchlist-chip-success")).toContainText("added PYPL");
    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
  });

  test("plain chat with no trade/watchlist keywords gets a canned portfolio-derived reply and no chips", async ({ page }) => {
    await sendChat(page, "How is my portfolio doing today?");

    const assistantMsg = page.getByTestId("chat-message").last();
    await expect(assistantMsg).toContainText("in cash");
    await expect(assistantMsg).toContainText("total portfolio value of");
    await expect(assistantMsg.getByTestId("action-chips")).not.toBeVisible();
  });

  test("chat history persists across a reload", async ({ page }) => {
    await sendChat(page, "Add PYPL to my watchlist");
    await expect(page.getByTestId("watchlist-chip-success")).toBeVisible();

    await page.reload();

    await expect(page.getByTestId("chat-loading-history")).toHaveCount(0, { timeout: 10_000 });
    const messages = page.getByTestId("chat-message");
    await expect(messages).toHaveCount(2); // the user turn + the assistant turn, reloaded from GET /api/chat/history
    await expect(messages.filter({ hasText: "Add PYPL to my watchlist" })).toBeVisible();
  });
});
