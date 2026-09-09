# FinAlly — E2E Test Summary

Status: **done, run for real against the real containerized stack.** Plan
published first in `planning/E2E_PLAN.md` — read that for scenario/spec
mapping, selectors, and the mock trigger-phrase grammar. This document
covers what was actually built, what actually ran, and the real results.

## Result

```
33 passed (33 total), 0 failed, 0 skipped, 0 flaky
```

Run twice from a fully clean state (fresh image build, fresh tmpfs DB)
to rule out a fluke — **33/33 both times**, identical durations (~45–56s).
A third run with `npm ci` against the committed `test/package-lock.json`
(rather than the `npm install` used while iterating) also passed 33/33,
confirming the lockfile is real and reproducible.

**No open application defects.** Every failure encountered while building
the suite (5, on the first run) was a bug in my own spec code, not in
`frontend/` or `backend/` — see "What actually broke, and why" below.
This is reported honestly rather than smoothed over, per the working
agreement, even though none of it needed routing to another engineer.

## What was built

```
test/
  docker-compose.test.yml   Two services: app (real Dockerfile, tmpfs /app/db,
                             LLM_MOCK=true, port 8100) + playwright
                             (mcr.microsoft.com/playwright:v1.48.0-jammy)
  package.json               @playwright/test 1.48.0 only
  package-lock.json          committed -- `npm ci` verified against it
  playwright.config.ts       workers: 1 (single-user backend, see E2E_PLAN §2)
  fixtures/reset.ts          resetPortfolio() via POST /api/portfolio/reset
  specs/
    fresh-start.spec.ts             PLAN §12: default watchlist, $10k, streaming
    watchlist.spec.ts               add/remove/idempotent-add/invalid-format
    trade.spec.ts                   buy/sell, full close, insufficient cash/shares
    api-trade-validation.spec.ts    direct-API edge cases (extra rigor)
    concurrency.spec.ts             concurrent trade+snapshot writes (extra rigor)
    portfolio-viz.spec.ts           heatmap + P&L chart rendering
    chat.spec.ts                    mocked trade/failure/watchlist/plain-chat + history reload
    sse-reconnect.spec.ts           real network-level disconnect/recover
    static-fallback.spec.ts         regression: commit d18b778
```

33 tests across 9 spec files.

## Environment / isolation, as actually run

- **Never touched the user's demo container.** Confirmed before starting:
  `docker ps` showed `finally` (image `finally:latest`) bound to host
  port 8000, volume `finally-data`. This suite uses its own image
  (`finally-e2e:latest`, rebuilt fresh every run — never reused a cached
  pull), its own container names (`finally-e2e-app`,
  `finally-e2e-playwright`), its own network (`test_default`), and its
  own host port (**8100**). Verified after every run that `finally` /
  `finally-data` were untouched and still healthy.
- **State isolation, two layers** (per the non-negotiable):
  1. `/app/db` is a tmpfs mount (long-syntax, `mode: "1777"` — see "What
     actually broke" below for why the mode is required) — every
     `docker compose up` starts from a genuinely empty DB, lazily
     initialized on first request.
  2. Every spec's `beforeEach` calls the real `POST /api/portfolio/reset`
     via Playwright's `request` fixture before the page ever loads —
     confirmed in the app container's logs on every test.
- **`LLM_MOCK=true`** set in the compose file; `OPENROUTER_API_KEY` and
  `MASSIVE_API_KEY` explicitly set to empty strings (not left unset) so
  the stack can never accidentally inherit a real key from the host
  shell. No test depends on a real model response — the coordinator's
  note that the OpenRouter account has no credits doesn't affect this
  suite at all, since mock mode never calls out.
- **Image freshness**: rebuilt `finally-e2e:latest` from current `HEAD`
  on every run (`context: ..` in the compose file, never `context:
  cached`), specifically because the coordinator flagged that a
  pre-`d18b778` cached image would make the regression assertions fail
  for the wrong reason. Manually curl-verified the two regression
  behaviors against a standalone run of this same build before trusting
  Playwright's version of the same assertions (see below).
- **Playwright's browser deps stay out of the production image** — the
  official `mcr.microsoft.com/playwright` image is a separate compose
  service, never added to the root `Dockerfile`.

## What actually broke, and why (first run: 28/33)

All five failures on the very first run were genuine bugs — **in my own
test code**, found by actually running the suite against the real stack,
not hypothetical:

1. **`getByRole('button', { name: 'Remove NFLX from watchlist' })`
   matched two elements.** The watchlist row itself is `role="button"`
   (click-to-select) and contains the actual remove button as a
   descendant; the row's computed accessible name picked up the nested
   button's `aria-label` too, so an unscoped role query hit both.
   Fixed by scoping to `getByTestId('watchlist-row-NFLX').getByLabel(...)`
   so the ancestor row is structurally excluded from the search.
2. **`page.getByRole('alert')` matched two elements everywhere.**
   Next.js always renders a hidden `#__next-route-announcer__` div with
   `role="alert"` for its own accessibility route-change announcements —
   present on every page regardless of application state, and (contrary
   to the "hidden" assumption) it registers as "visible" to Playwright's
   default visibility check. Fixed by scoping to the app's own error
   banner via its `text-negative` class (`[role="alert"].text-negative`),
   which the announcer div doesn't carry.
3. **The B4 ("trade auto-adds an untracked ticker to the watchlist")
   test was constructed to race the market data source.** It deleted a
   ticker from the watchlist (which, per `API_CONTRACT.md`, stops that
   ticker's price tracking immediately once it has no open position) and
   then immediately tried to trade it — legitimately hitting the "No live
   price available" 400 rather than the auto-add success path being
   tested. Redesigned to buy first (guarantees a price via the
   watchlist), then remove from the watchlist *while a position is still
   open* (contract explicitly keeps a held ticker priced after removal),
   then trade again — deterministic, no race, and actually exercises the
   auto-add code path.
4. **The SSE reconnection test's first mechanism, `context.setOffline()`,
   does not interrupt an already-open EventSource connection in this
   environment.** Toggling it around a `connected` stream left the
   connection dot on `"connected"` for the full 15s timeout — it never
   moved. This matches Chrome DevTools Protocol's actual documented
   behavior for `Network.emulateNetworkConditions(offline: true)`: it
   refuses *new* connections but does not terminate or interrupt reads on
   an already-open streaming connection, and SSE frames arrive as reads
   on one long-lived connection rather than as new per-message requests.
   This is a real, reproducible finding about the *test mechanism*
   itself (recorded in `sse-reconnect.spec.ts`'s comment block), not an
   app defect — switched to the task's other suggested mechanism,
   `page.route()`, registered *before* `page.goto()` so it can abort the
   very first connection attempt (a route handler can't reach into a
   connection opened before it was registered, so this had to be the
   design regardless). The dot genuinely renders yellow while blocked
   (`"connecting"` uses the same `accent-yellow` as `"reconnecting"` in
   `ConnectionDot.tsx`'s `STATUS_META`) and genuinely recovers to green
   via the browser's own native `EventSource` retry once unblocked — no
   sleep anywhere in this spec.
5. A cascade of the `getByRole('alert')` issue (item 2) hit a second spec
   in the same file — fixed by the same change.

Two infrastructure issues, fixed while building (not application bugs,
but recorded for whoever maintains this later):
- **`tmpfs: [/app/db]` (short syntax) makes the app container crash-loop
  on startup** — `sqlite3.OperationalError: unable to open database
  file`. A bare tmpfs mount replaces the image's pre-`chown`'d `/app/db`
  (uid 1000, per the Dockerfile) with a fresh **root-owned** mount, and
  the container runs as non-root uid 1000 — so it can't write there.
  Fixed by switching to the long volume syntax with `mode: "1777"`
  (world-writable + sticky bit, mirroring how `/tmp` is normally
  mounted), which is the only way to attach mount options to a compose
  tmpfs entry.
- `npm ci` needs a committed lockfile; generated one for real via `npm
  install` inside the actual Playwright container (not faked/hand-written)
  and committed it, then switched the compose command back to `npm ci`
  and re-ran clean to confirm it installs reproducibly (see "Result").

## The two regression assertions (commit `d18b778`)

Both verified two ways: manually with `curl` against a standalone run of
`finally-e2e:latest` first (to have an independent confirmation
before trusting the Playwright assertion), then via the actual
`static-fallback.spec.ts` spec in the full suite run:

```
$ curl -s -w "\nstatus=%{http_code} type=%{content_type}\n" http://localhost:8100/api/does-not-exist
{"detail":"Not Found"}
status=404 type=application/json

$ curl -s -w "\nstatus=%{http_code} type=%{content_type}\n" http://localhost:8100/deep/spa/route -o /tmp/deep.html
status=200 type=text/html; charset=utf-8
$ grep -o 'data-testid="header-total-value"' /tmp/deep.html
data-testid="header-total-value"
```

Both match exactly what the coordinator confirmed from the demo
container. Note for whoever writes the next regression test in this
area: a naive `expect(body).not.toContain("404")` on the SPA-fallback
body is a **false-positive trap** — Next.js's static export legitimately
embeds the `_not-found` route's flight/prefetch data inside `index.html`
itself, so the literal substring `"404"` appears in a correct
`index.html` too (confirmed by grep: 2 occurrences). The spec instead
asserts the real app shell marker (`data-testid="header-total-value"`)
is present and 404.html's specific `<title>404:` is absent.

## Coverage against `planning/E2E_PLAN.md` §3

Every row in the scenario table has at least one passing spec. Notable
extras beyond the minimum PLAN §12 list, per the coordinator's
highest-risk callouts:
- **Trade validation edge cases**: 11 direct-API tests covering
  zero/negative quantity, invalid ticker format, unknown-ticker-no-price,
  insufficient cash (exact message shape), insufficient shares (exact
  message shape), bad `side` (422), missing field (422), watchlist
  duplicate-add idempotency, watchlist invalid format, watchlist
  404-on-remove, and B4 auto-add-on-trade.
- **Concurrent trade + snapshot writes**: 10 concurrent 1-share buys of
  the same ticker land with no lost update (position quantity and cash
  balance both reconcile exactly against the sum of the individual fill
  prices, and a snapshot exists for every one of them); a mixed 5
  concurrent buys + 5 concurrent sells against an existing position
  nets to the expected quantity with no negative cash/shares.
- **Malformed LLM JSON parsing**: deliberately *not* attempted in E2E —
  documented as out of scope in `E2E_PLAN.md` §5 with the reasoning
  (the mock catalogue can only emit valid JSON, and the real LLM is
  unavailable/mandated-off). This is `backend/tests/llm/test_parser.py`'s
  job, cited in `LLM_DESIGN.md` §6 as already covering exactly this
  (empty string, truncated JSON, wrong types, fenced blocks, etc.).

## Constraints honored

- No files under `backend/`, `frontend/`, `Dockerfile`, or `scripts/`
  touched — everything is under `test/` plus the two planning docs.
- Did not run `git commit`.
- Never used host port 8000 or the `finally`/`finally-data`
  container/volume; confirmed both untouched after every run.
- No sleeps anywhere in any spec — every wait is a Playwright `expect(...)`
  polling assertion with an explicit timeout, or a real network-level
  mechanism (`page.route()` abort/continue for the reconnect test).

## Files touched

- `test/` (new): `docker-compose.test.yml`, `package.json`,
  `package-lock.json`, `playwright.config.ts`, `.gitignore`,
  `fixtures/reset.ts`, 9 files under `specs/`.
- `planning/E2E_PLAN.md`, `planning/E2E_SUMMARY.md` (new, this file).
