import { test, expect } from "@playwright/test";
import { resetPortfolio } from "../fixtures/reset";

// Direct API coverage of planning/API_CONTRACT.md's trade/watchlist
// validation table -- the coordinator flagged trade validation edge
// cases as a highest-risk area deserving extra rigor beyond the UI flows
// in trade.spec.ts / watchlist.spec.ts. Hits /api/* directly (no page
// navigation) for speed and precision about status codes/detail text.

test.describe("Trade validation edge cases (API_CONTRACT.md)", () => {
  test.beforeEach(async ({ request }) => {
    await resetPortfolio(request);
  });

  test("quantity <= 0 is rejected with 400", async ({ request }) => {
    const zero = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 0 } });
    expect(zero.status()).toBe(400);
    expect((await zero.json()).detail).toContain("positive, finite number");

    const negative = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: -5 } });
    expect(negative.status()).toBe(400);
    expect((await negative.json()).detail).toContain("positive, finite number");
  });

  test("invalid ticker format is rejected with 400, not 500", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "AA PL$", side: "buy", quantity: 1 } });
    expect(res.status()).toBe(400);
    expect((await res.json()).detail).toContain("Invalid ticker format");
  });

  test("an invalid side value is rejected with 422", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "hold", quantity: 1 } });
    expect(res.status()).toBe(422);
  });

  test("a missing field is rejected with 422", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy" } });
    expect(res.status()).toBe(422);
  });

  test("trading a ticker with no cached price yet is rejected with a clear 400, not a fill at 0", async ({ request }) => {
    // A well-formed, never-tracked, never-seeded ticker: no watchlist
    // entry and no position exists for it in a freshly-reset account, so
    // the price cache has no entry -- must reject, not execute at $0.
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "ZZZZ", side: "buy", quantity: 1 } });
    expect(res.status()).toBe(400);
    expect((await res.json()).detail).toContain("No live price available for ZZZZ");
  });

  test("buying beyond available cash is rejected with the exact required/available message shape", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 1_000_000 } });
    expect(res.status()).toBe(400);
    expect((await res.json()).detail).toMatch(/^Insufficient cash: required .+, available .+/);
  });

  test("selling shares never bought is rejected with the exact requested/held message shape", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "sell", quantity: 1 } });
    expect(res.status()).toBe(400);
    expect((await res.json()).detail).toMatch(/^Insufficient shares: requested .+, held .+/);
  });

  test("a successful trade auto-adds the ticker to the watchlist (B4)", async ({ request }) => {
    // Getting a ticker into the state the auto-add path actually exercises
    // (priced, but NOT on the watchlist) is race-free only one way: per
    // A4, a ticker with an open position keeps being priced even after
    // it's removed from the watchlist. So: buy it while it's still
    // watchlisted (guaranteed priced), remove it from the watchlist
    // (position keeps it tracked -- API_CONTRACT.md's DELETE section says
    // so explicitly), confirm it's really gone from the list, then trade
    // it again and confirm the trade both succeeds (proving the price
    // survived the removal) and re-adds it to the watchlist.
    const seed = await request.post("/api/portfolio/trade", { data: { ticker: "NFLX", side: "buy", quantity: 1 } });
    expect(seed.ok(), `seed buy failed: ${seed.status()} ${await seed.text()}`).toBeTruthy();

    await request.delete("/api/watchlist/NFLX");
    let list = await (await request.get("/api/watchlist")).json();
    expect(list.watchlist.map((w: { ticker: string }) => w.ticker)).not.toContain("NFLX");

    const trade = await request.post("/api/portfolio/trade", { data: { ticker: "NFLX", side: "buy", quantity: 1 } });
    expect(trade.ok(), `trade failed: ${trade.status()} ${await trade.text()}`).toBeTruthy();

    list = await (await request.get("/api/watchlist")).json();
    expect(list.watchlist.map((w: { ticker: string }) => w.ticker)).toContain("NFLX");
  });
});

test.describe("Watchlist validation edge cases (API_CONTRACT.md)", () => {
  test.beforeEach(async ({ request }) => {
    await resetPortfolio(request);
  });

  test("adding an already-present ticker is idempotent (200, not 409)", async ({ request }) => {
    const res = await request.post("/api/watchlist", { data: { ticker: "AAPL" } });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.watchlist.filter((w: { ticker: string }) => w.ticker === "AAPL")).toHaveLength(1);
  });

  test("adding an invalid-format ticker is rejected with 400", async ({ request }) => {
    const res = await request.post("/api/watchlist", { data: { ticker: "$$$" } });
    expect(res.status()).toBe(400);
  });

  test("removing a ticker not on the watchlist returns 404 with the exact message shape", async ({ request }) => {
    await request.delete("/api/watchlist/PYPL"); // ensure absent
    const res = await request.delete("/api/watchlist/PYPL");
    expect(res.status()).toBe(404);
    expect((await res.json()).detail).toBe("PYPL is not on the watchlist");
  });
});
