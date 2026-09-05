# Cross-validation report (2026-07-30, post-review + R1 final fix)

## Convergence checks (7/7 pass)

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | `pnpm check` exits 0 | **PASS** | 269/269 tests across 21 files |
| 2 | `pnpm test:e2e` exits 0 | **PASS** | 4/4 Playwright (chromium) tests pass in 1.2s |
| 3 | `grep -rn "durationMs: 0" src/ scripts/` | **PASS** | Exit code 1 (no matches) |
| 4 | Signed-URL replay test exists | **PASS** | test/unit/workflow-steps.test.ts (4 tests) |
| 5 | Schema top-level `required` array | **PASS** | property-registry-record-v1.json:547, 7 required fields |
| 6 | `setReviewKind` test exists | **PASS** | test/integration/repositories.test.ts:153 |
| 7 | `/api/schemas/:schemaId` route | **PASS** | src/routes/schemas.ts:7 |

## Risk audit (final)

| Risk | Status | Commit SHA | Notes |
|---|---|---|---|
| R1 | **FIXED** | `66b9891` + `a3c5c5b` | e2e/server.ts created, then 2 bugs fixed: URL base + serve index.html at `/` |
| R2 | **FIXED** | `eae2d3f` | Signed URL moved to step 2 |
| R3 | **DEFERRED** | — | Needs live GLM-4.7-Flash creds |
| R4 | **FIXED** | `4e687ff` | .dev.vars mode 0o600 + chmodSync |
| R5 | **FIXED** | `3b2f964` | application/octet-stream accepted with magic check |
| R6 | **REFUTED** | — | Schema has top-level `required` with 7 fields |
| R7 | **FIXED** | `5697b0e` | assertionsRun tracked |
| R8 | **FIXED** | `1107f93` | Real durationMs, itemsProcessed field |
| R9 | **FIXED** | `2b2d3e7` | Single INSERT ... ON CONFLICT |
| R10 | **FIXED** | `c194a6f` | setReviewKind() helper, atomic write + fake D1 snapshot fix |

## The e2e/server.ts bugs (both fixed in commit `a3c5c5b`)

### Bug 1: URL constructor missing base

**File:** `e2e/server.ts:88`
**Code:** `const path = new URL(reqUrl).pathname;`
**Input:** `/api/health` (Node's `req.url` is pathname-only)
**Error:** `TypeError: Invalid URL`
**Impact:** Every request returns 500. Playwright webServer health check at `http://127.0.0.1:8787/api/health` times out after 30s.
**Fix:** `const path = new URL(reqUrl, \`http://${HOST}:${PORT}\`).pathname;`

### Bug 2: static handler returned null for `/`

**File:** `e2e/server.ts:91`
**Code:** `if (path === "/") return null;`
**Impact:** `curl http://localhost:8787/` returned `{"status":"ok"}` (the Hono JSON health route) instead of `public/index.html`. Playwright test for `getByTestId("privacy")` failed with "element not found" because the HTML was never served.
**Fix:** Map `/` to `index.html`: `const filename = path === "/" ? "index.html" : path.replace(/^\/+/, "");`

### Why both bugs survived 9 review commits

Nobody ran `pnpm test:e2e` end-to-end until the final cross-validation. The R1 fix (commit `66b9891`) created the file and verified typecheck/test, but Playwright was never executed. All subsequent review commits inherited the bugs.

**Lesson for future review cycles:** Convergence check 2 (`pnpm test:e2e`) must be run during Phase 2.5 (salvage + merge), not deferred to Phase 4 (final cross-validation). A one-line bug discovered at the end costs 30 minutes of Playwright timeout; discovered at merge time, it costs 30 seconds.

## §37 Acceptance checklist

37 of 39 items ✓. The two remaining ✗ explicitly require live credentials + private fixture (§38 items 6-7). All code-level items pass.
