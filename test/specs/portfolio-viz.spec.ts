import { test, expect, type Page } from "@playwright/test";
import { resetPortfolio } from "../fixtures/reset";

async function waitForLivePrice(page: Page, ticker: string): Promise<void> {
  const priceCell = page.getByTestId(`watchlist-row-${ticker}`).getByTestId("price-cell");
  await expect(priceCell).not.toHaveText("—", { timeout: 15_000 });
}

test.describe("Heatmap and P&L chart rendering (PLAN §12)", () => {
  test.beforeEach(async ({ request, page }) => {
    await resetPortfolio(request);
    await page.goto("/");
  });

  test("both render an empty state with no positions/history", async ({ page }) => {
    await expect(page.getByTestId("heatmap-empty")).toBeVisible();
    // A reset itself records one snapshot (API_CONTRACT.md), so the P&L
    // chart should NOT be in its empty state -- it has at least one point.
    await expect(page.getByTestId("pnl-chart")).toBeVisible({ timeout: 10_000 });
  });

  test("after a trade, the heatmap renders a position and the P&L chart updates", async ({ page }) => {
    await waitForLivePrice(page, "AAPL");
    await page.getByLabel("Trade ticker").fill("AAPL");
    await page.getByLabel("Trade quantity").fill("5");
    await page.getByTestId("buy-button").click();
    await expect(page.getByRole("status")).toContainText("Bought 5 AAPL @ $");

    // Heatmap: no longer the empty state, and a real treemap rect is drawn
    // (colored by P&L, per PLAN §10) -- more reliable than asserting the
    // ticker label text, which the component only renders above a pixel
    // size threshold that depends on viewport/layout.
    await expect(page.getByTestId("heatmap-empty")).not.toBeVisible();
    await expect(page.getByTestId("heatmap")).toBeVisible();
    const heatmapRects = page.getByTestId("heatmap").locator("svg rect");
    await expect(heatmapRects.first()).toBeVisible();

    // P&L chart: the trade records an immediate snapshot and the UI
    // refetches via `tradeVersion` -- assert the chart is rendered (not
    // the empty state) with real chart markup (an SVG path from recharts'
    // Area).
    await expect(page.getByTestId("pnl-chart")).toBeVisible();
    const svgPaths = page.getByTestId("pnl-chart").locator("svg path");
    await expect(svgPaths.first()).toBeVisible();
  });
});
