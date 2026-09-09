import { test as base, expect, type APIRequestContext } from "@playwright/test";

/**
 * State isolation (planning/E2E_PLAN.md §2): every test starts from a
 * fresh $10,000 / 10-default-ticker account via the real
 * POST /api/portfolio/reset endpoint, using Playwright's `request`
 * fixture directly -- no browser navigation needed, so this is fast and
 * runs before the page ever loads.
 */
export const test = base.extend({});

export async function resetPortfolio(request: APIRequestContext) {
  const res = await request.post("/api/portfolio/reset");
  expect(res.ok(), `POST /api/portfolio/reset failed: ${res.status()} ${await res.text()}`).toBeTruthy();
  return res.json();
}

export { expect };

export const DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"];
