import { test, expect } from "@playwright/test";
import { resetPortfolio } from "../fixtures/reset";

// Coordinator-flagged high-risk area: concurrent trade + snapshot writes
// (PLAN §13.B9 — SQLite concurrency). Fires N buy requests for the same
// ticker concurrently and asserts no fill was lost to a check-then-act
// race on cash/position (i.e. the DB write path serializes correctly
// under concurrent load, not just under this suite's own serial tests).

test.describe("Concurrent trade writes (PLAN §13.B9)", () => {
  test.beforeEach(async ({ request }) => {
    await resetPortfolio(request);
  });

  test("N concurrent 1-share buys of the same ticker all land (no lost update)", async ({ request }) => {
    const N = 10;
    const results = await Promise.all(
      Array.from({ length: N }, () => request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 1 } }))
    );

    const okResults = results.filter((r) => r.ok());
    expect(okResults, `expected all ${N} concurrent buys to succeed (plenty of cash for N shares of AAPL)`).toHaveLength(N);

    const bodies = await Promise.all(okResults.map((r) => r.json()));
    const executedPrices = bodies.map((b) => b.trade.price as number);
    const expectedCashSpent = executedPrices.reduce((sum, p) => sum + p, 0);

    const portfolio = await (await request.get("/api/portfolio")).json();
    const aapl = portfolio.positions.find((p: { ticker: string }) => p.ticker === "AAPL");

    expect(aapl, "AAPL position should exist after N concurrent buys").toBeTruthy();
    expect(aapl.quantity).toBeCloseTo(N, 6);

    const expectedCash = 10_000 - expectedCashSpent;
    expect(portfolio.cash_balance).toBeCloseTo(expectedCash, 2);

    // A snapshot must exist for each successful trade (recorded
    // synchronously per API_CONTRACT.md's "always on success" side
    // effects) -- not silently dropped/coalesced by the concurrent writes.
    const history = await (await request.get("/api/portfolio/history?limit=2000")).json();
    expect(history.snapshots.length).toBeGreaterThanOrEqual(N);
  });

  test("concurrent buy+sell against the same ticker never produces negative cash or negative shares", async ({ request }) => {
    // Seed a position first so the sells have something to race against.
    const seed = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 20 } });
    expect(seed.ok()).toBeTruthy();

    const requests = [
      ...Array.from({ length: 5 }, () => request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 1 } })),
      ...Array.from({ length: 5 }, () => request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "sell", quantity: 1 } })),
    ];
    const results = await Promise.all(requests);

    // Every one of these should individually succeed (20 shares held is
    // plenty of headroom for 5 concurrent -1s, and cash is plenty for 5
    // concurrent +1s) -- the risk here isn't validation, it's a lost or
    // corrupted write under concurrency.
    for (const r of results) {
      expect(r.ok(), `trade failed unexpectedly: ${r.status()} ${await r.text()}`).toBeTruthy();
    }

    const portfolio = await (await request.get("/api/portfolio")).json();
    expect(portfolio.cash_balance).toBeGreaterThanOrEqual(0);
    const aapl = portfolio.positions.find((p: { ticker: string }) => p.ticker === "AAPL");
    expect(aapl.quantity).toBeCloseTo(20, 6); // +5 -5 net zero change from the seed
    expect(aapl.quantity).toBeGreaterThanOrEqual(0);
  });
});
