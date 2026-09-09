import { test, expect, type Page } from "@playwright/test";
import { resetPortfolio } from "../fixtures/reset";

async function waitForLivePrice(page: Page, ticker: string): Promise<void> {
  const priceCell = page.getByTestId(`watchlist-row-${ticker}`).getByTestId("price-cell");
  await expect(priceCell).not.toHaveText("—", { timeout: 15_000 });
}

async function submitTrade(page: Page, ticker: string, quantity: string, side: "buy" | "sell") {
  await page.getByLabel("Trade ticker").fill(ticker);
  await page.getByLabel("Trade quantity").fill(quantity);
  await page.getByTestId(`${side}-button`).click();
}

// Qty is the 2nd column (index 1) of the positions table's row -- checking
// this exact cell (rather than `toContainText` on the whole row) avoids a
// false-positive match against a digit that happens to appear in the
// price/P&L columns instead.
function qtyCell(page: Page, ticker: string) {
  return page.getByTestId(`position-row-${ticker}`).locator("td").nth(1);
}

test.describe("Buy / sell (PLAN §12)", () => {
  test.beforeEach(async ({ request, page }) => {
    await resetPortfolio(request);
    await page.goto("/");
    await waitForLivePrice(page, "AAPL");
  });

  test("buying decreases cash and the position appears", async ({ page }) => {
    const cashBefore = await page.getByTestId("header-cash-balance").textContent();

    await submitTrade(page, "AAPL", "5", "buy");

    await expect(page.getByRole("status")).toContainText("Bought 5 AAPL @ $");
    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
    await expect(qtyCell(page, "AAPL")).toHaveText("5");

    const cashAfter = await page.getByTestId("header-cash-balance").textContent();
    expect(cashAfter).not.toEqual(cashBefore);
    const parseMoney = (s: string | null) => Number((s ?? "").replace(/[^0-9.-]/g, ""));
    expect(parseMoney(cashAfter)).toBeLessThan(parseMoney(cashBefore));
  });

  test("selling part of a position increases cash and updates the position", async ({ page }) => {
    await submitTrade(page, "AAPL", "10", "buy");
    await expect(qtyCell(page, "AAPL")).toHaveText("10");

    const cashAfterBuy = await page.getByTestId("header-cash-balance").textContent();
    const parseMoney = (s: string | null) => Number((s ?? "").replace(/[^0-9.-]/g, ""));

    await submitTrade(page, "AAPL", "4", "sell");

    await expect(page.getByRole("status")).toContainText("Sold 4 AAPL @ $");
    await expect(qtyCell(page, "AAPL")).toHaveText("6");

    const cashAfterSell = await page.getByTestId("header-cash-balance").textContent();
    expect(parseMoney(cashAfterSell)).toBeGreaterThan(parseMoney(cashAfterBuy));
  });

  test("selling an entire position removes it from the table", async ({ page }) => {
    await submitTrade(page, "AAPL", "3", "buy");
    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();

    await submitTrade(page, "AAPL", "3", "sell");

    await expect(page.getByRole("status")).toContainText("Sold 3 AAPL @ $");
    await expect(page.getByTestId("position-row-AAPL")).not.toBeVisible();
    await expect(page.getByText("No open positions — buy something with the trade bar below.")).toBeVisible();
  });

  test("selling more than held is rejected with a clear error", async ({ page }) => {
    await submitTrade(page, "AAPL", "1000000", "sell");

    await expect(page.getByRole("status")).toContainText("Insufficient shares");
    await expect(page.getByTestId("position-row-AAPL")).not.toBeVisible();
  });

  test("buying beyond available cash is rejected with a clear error", async ({ page }) => {
    await submitTrade(page, "AAPL", "1000000", "buy");

    await expect(page.getByRole("status")).toContainText("Insufficient cash");
    await expect(page.getByTestId("position-row-AAPL")).not.toBeVisible();
  });
});
