import { test, expect, type Page } from "@playwright/test";
import { resetPortfolio } from "../fixtures/reset";

// Scoped alert locator: Next.js always renders a hidden
// `#__next-route-announcer__` div with role="alert" for its own a11y
// route-change announcements, which also matches a bare `getByRole("alert")`
// -- that isn't a product bug, just something a broad role query collides
// with. This app's own error banner additionally carries the `text-negative`
// class (Watchlist.tsx), which the announcer div does not, so scope on that.
function watchlistErrorBanner(page: Page) {
  return page.locator('[role="alert"].text-negative');
}

test.describe("Watchlist add/remove (PLAN §12)", () => {
  test.beforeEach(async ({ request }) => {
    await resetPortfolio(request);
  });

  test("adds a new ticker and it appears in the watchlist", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("10 tickers")).toBeVisible();

    await page.getByLabel("Add ticker to watchlist").fill("pypl");
    await page.getByRole("button", { name: "Add" }).click();

    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
    await expect(page.getByText("11 tickers")).toBeVisible();
    // Input is normalized (uppercased) and cleared on success.
    await expect(page.getByLabel("Add ticker to watchlist")).toHaveValue("");
  });

  test("removes a ticker and it disappears from the watchlist", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("watchlist-row-NFLX")).toBeVisible();

    // Scoped to the row: the row itself is also `role="button"`
    // (click-to-select), so an unscoped `getByRole("button", {name})`
    // matches both the row and the nested remove button (its computed
    // accessible name also picks up the descendant's aria-label).
    await page.getByTestId("watchlist-row-NFLX").getByLabel("Remove NFLX from watchlist").click();

    await expect(page.getByTestId("watchlist-row-NFLX")).not.toBeVisible();
    await expect(page.getByText("9 tickers")).toBeVisible();
  });

  test("adding an already-present ticker is idempotent, not an error", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Add ticker to watchlist").fill("AAPL");
    await page.getByRole("button", { name: "Add" }).click();

    // Still exactly 10 -- no duplicate row, no error banner.
    await expect(page.getByText("10 tickers")).toBeVisible();
    await expect(watchlistErrorBanner(page)).not.toBeVisible();
  });

  test("rejects an invalid ticker format with a visible error", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Add ticker to watchlist").fill("AA PL$");
    await page.getByRole("button", { name: "Add" }).click();

    await expect(watchlistErrorBanner(page)).toBeVisible();
    await expect(watchlistErrorBanner(page)).toContainText("Invalid ticker format");
    await expect(page.getByText("10 tickers")).toBeVisible();
  });
});
