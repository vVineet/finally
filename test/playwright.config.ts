import { defineConfig } from "@playwright/test";

// planning/E2E_PLAN.md §2: the backend is single-user (hardcoded
// user_id="default"), so tests run with a single worker rather than
// fighting Playwright's own parallelism with a shared portfolio. Each
// spec resets state itself (POST /api/portfolio/reset) rather than
// relying on isolation the runner can't actually provide here.
export default defineConfig({
  testDir: "./specs",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["json", { outputFile: "test-results/results.json" }],
  ],
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:8100",
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
