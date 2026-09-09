import { test, expect } from "@playwright/test";

// Regression coverage for the StaticFiles(html=True) bug fixed in commit
// d18b778 (planning/DEVOPS_SUMMARY.md "3. SPA fallback / /api 404 shape").
// The backend unit test's fixture didn't include a 404.html, which is why
// this reached a built image undetected -- asserted here against the
// real container with the real Next.js static export (which always emits
// 404.html), so this can't pass for the same reason it passed before.
// No portfolio state involved, so no reset needed.

test.describe("Static mount / SPA fallback regression (commit d18b778)", () => {
  test("an unmatched /api/* path returns JSON, not an HTML error page", async ({ request }) => {
    const res = await request.get("/api/does-not-exist");
    expect(res.status()).toBe(404);
    expect(res.headers()["content-type"]).toContain("application/json");

    const body = await res.json(); // throws if this were HTML -- itself part of the assertion
    expect(typeof body.detail).toBe("string");
  });

  test("a deep non-/api route serves index.html at 200, not 404.html at 404", async ({ request }) => {
    const res = await request.get("/deep/spa/route");
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("text/html");

    const body = await res.text();
    // index.html (the real Next.js export), not 404.html -- both are
    // valid HTML documents with the same <head>/layout, and Next.js
    // embeds the not-found route's flight data inside index.html too
    // (so a naive `not.toContain("404")` check is a false positive trap:
    // index.html legitimately contains the substring "404" twice). The
    // real distinguishing signal is the actual app shell markup, which
    // only index.html renders server-side; 404.html's own <title> is the
    // negative check.
    expect(body).toContain('data-testid="header-total-value"');
    expect(body).not.toContain("<title>404:");
  });
});
