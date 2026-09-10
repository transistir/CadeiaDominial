# Architectural fix sketches (R2/R4/R6/R9/R10)

Captured from the 2026-07-30 Opus 5 review. Use when a future review cycle re-discovers the same risks, or when onboarding a new subagent to apply the canonical fix set.

## R2 — signed URL must be generated inside step 2 (P0, CONFIRMED)

**Symptom:** `loadAndMarkOcrProcessing` (step 1) returns a `LoadMarkResult` containing `signedSourceUrl`. The Workflow runtime caches the step's return value; on retry/replay, step 2 (`parseDocumentWithPaddle`) consumes the cached URL even if it has expired. Result: Paddle is called with a stale URL → 410 → retry loop wastes 30-min workflow budget.

**Fix shape (concrete):**

1. Remove `signedSourceUrl: string` from `LoadMarkResult` in `src/services/workflow-steps.ts` (the interface around line 113).
2. In `loadAndMarkOcrProcessing`, delete the `signedSourceUrl: signedUrlBuilder(jobId)` lines from both the idempotent-return branch and the transition branch.
3. At the top of `parseDocumentWithPaddle` (around line 257, before `deps.ocrProvider.parseDocument`):
   ```ts
   const signedSourceUrl = await deps.signedUrlBuilder(jobId);
   ```
4. Pass `signedSourceUrl` to the OCR call.
5. Update any existing tests that asserted on the old `loadResult.signedSourceUrl` shape (search `test/` for `signedSourceUrl`).
6. Add a regression test in `test/unit/workflow-steps.test.ts`:
   - Spy on `deps.signedUrlBuilder` to return a URL with a short TTL.
   - Replay the workflow step.
   - Assert that `parseDocumentWithPaddle` calls `signedUrlBuilder` again on every replay (not just once).

**Why this matters:** SPEC §24 says "Generate signed source URL from PUBLIC_BASE_URL" inside the OCR step. Building it in step 1 violates the spec AND causes silent 30-min retry loops.

## R4 — write `.dev.vars` with mode 0600 (P1, PARTIAL → real bug found)

**Symptom:** `scripts/setup.ts` writes `.dev.vars` without file mode restriction. Anyone who can read the repo directory can read `APP_API_KEY` and `SOURCE_URL_SIGNING_SECRET`.

**First attempt (INCOMPLETE):** `writeFileSync(path, body, { encoding: "utf-8", mode: 0o600 })` — the `mode` option is ONLY honored on file *creation*. If the file already exists with looser perms (very common: anyone who ran `pnpm setup` before R4), the mode is silently ignored.

**Real fix:**
1. Add `mode: 0o600` to the `writeFileSync` call (for new files).
2. **After the write, force the mode regardless of prior state:** `chmodSync(targetPath, 0o600)`.
3. In `scripts/provision.ts:223-238` (`secureDelete`): add a JSDoc block explaining that the overwrite is best-effort on journaled filesystems (ext4/btrfs/APFS), and the real fix is for the user to rotate the secret after a failed deploy — out of POC scope.
4. Add a unit test in `test/scripts/setup-scripts.test.ts` that:
   - Calls `writeDevVars` on a fresh path → asserts `fs.statSync(path).mode & 0o777 === 0o600`.
   - Calls `writeDevVars` on an existing path with mode 0o644 → asserts the result is still 0o600 (this catches the silent-ignore bug).

**Why this matters:** the R4 subagent that wrote the first version without the `chmodSync` was wrong, and a regression test for the overwrite case exposed it. Always test "overwrite with looser perms" when writing secrets.

## R6 — REFUTED (do NOT implement)

Opus 5 read the actual schema (`schemas/property-registry-record-v1.json`) and found that the top-level `properties.required` array includes `documentType`, `registryOffice`, `registration`, `property`, `initialOwnership`, `acts`, `closure`. Empirically, `compileValidator({}).validate({})` returns 7 errors. Therefore the "empty `{}` proposal persisted as valid" risk is a false positive — `validateAndPersist:421-443` correctly routes to `needs_review/validation_failed` with no record persisted.

**Lesson:** always have Opus verify the schema before dispatching a "fix" for a risk that depends on validator behavior. Don't trust the risk register blindly.

## R9 — upsertByJobId race (P2, CONFIRMED)

**Symptom:** `src/repositories/records.ts:60-78` `upsertByJobId` is check-then-act: `getByJobId` → `INSERT` or `UPDATE` → `getByJobId` again. Two concurrent workflow replays for the same `jobId` race: one inserts, the other throws UNIQUE constraint or no-ops, and the final state is non-deterministic.

**Fix shape:**
```sql
INSERT INTO extracted_records (id, job_id, schema_id, schema_version, data_json, created_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6)
ON CONFLICT(job_id) DO UPDATE SET
  data_json = excluded.data_json,
  schema_id = excluded.schema_id,
  schema_version = excluded.schema_version
```

D1/SQLite supports this. The `excluded.col` references the new value. Preserves first writer's `id` and `created_at` on conflict.

**Fake D1 gotcha:** `test/support/fake-d1.ts:147-154` originally didn't parse `ON CONFLICT` clauses. The 2026-07-30 R9 dispatch hit this and had to add a parser branch. The parser must handle `excluded.col` references on the RHS — `parseAssignments()` returns `[]` if it doesn't recognize the pattern, and the conflict path becomes a no-op. **Implementation pattern:** in `runUpsert`, regex-extract assignment pairs directly from the `setClause` and handle `excluded.col` inline (bypassing `parseAssignments` for the upsert path).

**Test:** call `upsertByJobId(db, record1)`, then `upsertByJobId(db, record2)` with the same `jobId` but different data, assert that querying by jobId returns `record2.data_json`. Use a spy on `db.prepare()` to assert the SQL emitted is the ON CONFLICT upsert (not the read-then-write pair).

## R10 — review_kind written atomically with status (P1, CONFIRMED)

**Symptom:** `src/services/workflow-steps.ts:430-437, 473-477` writes `review_kind` via a separate `UPDATE` after `transition(... "needs_review")`. Between the two, `GET /api/extractions/:id` could return `status='needs_review', review_kind=null`. The real consumer is `src/routes/extractions.ts:337-376` (NOT `public/app.js` — the risk register's original UI consumer was wrong).

**Fix shape:**
1. In `src/repositories/jobs.ts:354-392`, add a new `setReviewKind(db, jobId, reviewKind)` helper (separate from `setResult` for cleaner atomicity).
2. In `src/services/workflow-steps.ts:430-437, 473-477`, replace the two raw `UPDATE ... SET review_kind = ?2` calls with `setReviewKind(db, jobId, "model_flagged")` and `setReviewKind(db, jobId, "validation_failed")` respectively.
3. Add a regression test: set up a job with `status='needs_review'` and a `review_kind` value, assert both fields are set in the row (convergence criterion #6 from the review plan).

**Fake D1 gotcha (discovered during R10 test):** `test/support/fake-d1.ts` `first()` returned the live row object. When the second `setReviewKind` call mutated the row in-place, the previously-returned `after2` reference was retroactively changed — so `expect(after3.updated_at).not.toBe(after2.updated_at)` failed because both pointed to the same mutated object. **Fix:** `first()` must return `{ ...r }` (shallow copy), matching real D1 semantics. Full debugging story in `subagent-driven-development/references/in-memory-db-mock-mutation-aliasing.md`.

**Why this matters:** the API envelope shape (§25) branches on `review_kind` to return either the valid record (`model_flagged`) or the error envelope (`validation_failed`). If the column is null at read time, the route mis-renders the response.

## Bonus: R1 = canonical P0 surprise

`playwright.config.ts` invokes a `webServer.command: "tsx e2e/server.ts"` but no one wrote `e2e/server.ts` until the e2e spec was actually run. Same pattern with `scripts/build.ts` for `pnpm build` (wrangler.jsonc is gitignored). **Pattern:** when a config or script references a generated/bootstrapped file, write the bootstrap first, then run the test that uses it.

**Resolution (2026-07-30):** `e2e/server.ts` created in commit `66b9891`, but had TWO latent bugs: (1) `new URL(reqUrl)` without a base threw `ERR_INVALID_URL` on relative pathnames, (2) the static handler returned `null` for `/`, serving the JSON health route instead of `index.html`. Both fixed in commit `a3c5c5b` after the orchestrator ran `pnpm test:e2e` end-to-end. 4/4 Playwright tests now pass. See `subagent-driven-development/references/playwright-hono-e2e-server.md` for the full reusable recipe including both pitfalls.
