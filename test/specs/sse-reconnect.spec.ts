import { test, expect } from "@playwright/test";
import { resetPortfolio } from "../fixtures/reset";

// SSE resilience (PLAN §12 / coordinator's non-negotiable): a real network
// mechanism, not a sleep.
//
// `context.setOffline(true)` was tried first (it's the task's first
// suggested mechanism) and does NOT work for this: against the real
// running stack, toggling it around an already-`connected` EventSource
// left the connection dot on "connected" for the full 15s timeout --
// never transitioning at all. This matches Chrome DevTools Protocol's
// actual documented behavior for `Network.emulateNetworkConditions`
// (offline: true): it refuses *new* connections but does not terminate
// or interrupt reads on an already-open streaming connection, and an
// EventSource's SSE frames arrive as reads on one long-lived connection,
// not as new per-message requests. Recorded here as a real finding about
// the test mechanism, not a workaround -- switched to `page.route()`
// instead (the task's other suggested mechanism), which reliably
// intercepts and aborts the underlying HTTP request instead.
//
// `page.route()` registered on an already-open connection has the same
// problem in reverse (Playwright only intercepts requests made *after*
// the handler is registered, so it can't reach into an existing one
// either) -- so the block is registered *before* `page.goto`, forcing
// the very first connection attempt to fail. `usePriceStream`'s status
// state machine (frontend/src/hooks/usePriceStream.ts) maps this to
// "connecting" while never-yet-connected, which STATUS_META
// (ConnectionDot.tsx) renders in the same accent-yellow as "reconnecting"
// -- i.e. the dot genuinely goes yellow, which is what's being asserted.
// Unblocking then lets the browser's native EventSource retry (driven by
// the server's `retry: 1000` directive, PLAN §6) succeed on its own,
// with no app code involved in the recovery.

test.describe("SSE reconnection (PLAN §12)", () => {
  test.beforeEach(async ({ request }) => {
    await resetPortfolio(request);
  });

  test("the connection dot goes yellow while the stream is unreachable and recovers to green once it's restored", async ({
    page,
  }) => {
    let blocked = true;
    await page.route("**/api/stream/prices", (route) => {
      if (blocked) {
        route.abort("connectionfailed");
      } else {
        route.continue();
      }
    });

    await page.goto("/");
    const dot = page.getByTestId("connection-status");

    // Every connection attempt is failing -- the dot must never reach
    // "connected" while blocked (same yellow render as "reconnecting":
    // STATUS_META maps both "connecting" and "reconnecting" to
    // accent-yellow).
    await expect(dot).toHaveAttribute("data-status", "connecting", { timeout: 15_000 });

    blocked = false;

    await expect(dot).toHaveAttribute("data-status", "connected", { timeout: 15_000 });

    // Prices resume flowing post-recovery -- not just a status flip with
    // a stalled stream underneath it.
    const priceCell = page.getByTestId("watchlist-row-AAPL").getByTestId("price-cell");
    await expect(priceCell).not.toHaveText("—", { timeout: 15_000 });
  });
});
