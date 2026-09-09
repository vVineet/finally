import { test, expect } from "@playwright/test";
import { resetPortfolio, DEFAULT_TICKERS } from "../fixtures/reset";

test.describe("Fresh start (PLAN §12)", () => {
  test.beforeEach(async ({ request }) => {
    await resetPortfolio(request);
  });

  test("shows the default 10-ticker watchlist, $10,000 cash, and streaming prices", async ({ page }) => {
    await page.goto("/");

    // Header: cash and total value both read $10,000.00 immediately after
    // a reset with no positions.
    await expect(page.getByTestId("header-cash-balance")).toHaveText("$10,000.00");
    await expect(page.getByTestId("header-total-value")).toHaveText("$10,000.00");

    // All 10 default tickers are present.
    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
    }
    await expect(page.getByText(`${DEFAULT_TICKERS.length} tickers`)).toBeVisible();

    // Connection dot reaches "connected" (green).
    const dot = page.getByTestId("connection-status");
    await expect(dot).toHaveAttribute("data-status", "connected", { timeout: 15_000 });

    // Prices are actually streaming: every default ticker's price cell
    // moves off the null placeholder within a few seconds of the SSE
    // connection opening (simulator ticks ~every 500ms).
    for (const ticker of DEFAULT_TICKERS) {
      const priceCell = page.getByTestId(`watchlist-row-${ticker}`).getByTestId("price-cell");
      await expect(priceCell).not.toHaveText("—", { timeout: 15_000 });
    }

    // Positions table and heatmap correctly render the flat/no-positions
    // empty states -- not an error, not a crash.
    await expect(page.getByText("No open positions — buy something with the trade bar below.")).toBeVisible();
    await expect(page.getByTestId("heatmap-empty")).toBeVisible();
  });
});
