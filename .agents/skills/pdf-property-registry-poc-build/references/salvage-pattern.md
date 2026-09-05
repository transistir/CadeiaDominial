# Salvage pattern: when a subagent hits the iteration cap mid-task

Captured from the 2026-07-30 review cycle. Subagents reliably hit the ~50 tool-call cap mid-task and leave uncommitted code in the working tree. This document describes the orchestrator's recovery procedure.

## Symptoms

A subagent reports back with:
- "Tool-call budget exhausted before X could complete"
- "I have uncommitted changes in [file list]"
- "The change is correct, but I did not run pnpm test / git commit"

The repo shows:
- `git status` lists modified files on the current branch
- `pnpm typecheck && pnpm test` passes (code is sound)
- Working tree is dirty; HEAD is one or more commits behind the subagent's intent

## Triage

```bash
cd /root/dev/pdf-property-registry-poc
git status --short
git diff --stat
git log --oneline | head -5
```

Three cases:

1. **Change is small/mechanical (≤50 lines, no test gaps).** Orchestrator commits directly.
2. **Change is medium (50-200 lines, partial tests, lint debt).** Dispatch a tiny continuation subagent.
3. **Change is large (>200 lines, >1 phase).** Cherry-pick or roll back; the next subagent should start fresh from a known-clean state.

## Case 1: orchestrator commits directly

For 1-file changes where the subagent's diff is verbatim what the orchestrator asked for:

```bash
git add <file>
git commit -m "fix: review R-N — <one-line description from subagent report>"
export PATH=/root/.hermes/node/bin:$PATH
pnpm typecheck && pnpm lint && pnpm test
```

If lint fails, `pnpm lint --write --unsafe` and amend the commit.

## Case 2: tiny continuation subagent

When the subagent's diff is correct but commits/lint/extra-tests were unfinished, dispatch:

```text
You are a [Codex | Sonnet 5] subagent finishing work on `pdf-property-registry-poc`.
Branch `review/fixes-…` is checked out. The previous subagent (deleg_XXX) edited
these files but did not commit:
- <file1>
- <file2>

Your scope: verify the changes are correct, fix any test failures, run
`pnpm typecheck && pnpm lint && pnpm test` (auto-fix lint: `pnpm lint --write --unsafe`),
then commit `fix: review R-N — <one-line>`.

DO NOT make additional changes beyond what's needed to pass checks.
DO NOT merge to master.
```

This pattern works well for 1-2 unfinished risk IDs.

## Case 3: large rollback

When the partial change is wrong or has test gaps, **discard and re-dispatch from scratch**:

```bash
git checkout -- <file>
git status --short
# Re-dispatch with cleaner scope
```

The 2026-07-30 R2 dispatch had this exact pattern: the subagent (deleg_a323bd74) started R2 by editing `src/services/workflow-steps.ts` but didn't commit. The orchestrator (me) used `git checkout -- <file>` to discard, then dispatched a fresh subagent (deleg_3bd1509c) with explicit "you will re-implement R2 from scratch."

**Important:** when you discard, also re-read the spec for the risk — the second subagent may need clearer instructions about what to NOT do (e.g. "do NOT add `void loadResult;` to silence no-unused-vars").

## Branch isolation during parallel dispatches

When two subagents are dispatched in parallel against the same repo, each MUST work on a separate branch:

```bash
# Subagent A
git checkout -b review/fixes-r1-r5-r7-r8
# ... work ...

# Subagent B (parallel)
git checkout -b review/fixes-r2-r4-r9-r10
# ... work ...
```

If both end up on `master`, merge conflicts are inevitable. After both return, the orchestrator merges each branch with `--no-ff`:

```bash
git checkout master
git merge --no-ff review/fixes-r1-r5-r7-r8
git merge --no-ff review/fixes-r2-r4-r9-r10
```

If conflicts arise (rare with the "files-to-NOT-touch" constraint in each prompt), resolve manually or re-dispatch the conflicting subagent with the other's branch as the base.

## "Files to NOT touch" constraint (validated)

When dispatching two parallel fix subagents, each prompt MUST list the files the other owns. Pattern (2026-07-30):

- **Dispatch B (mechanical fixes) owns:** `src/services/file-validation.ts`, `src/services/upload.ts`, `test/unit/file-validation.test.ts`, `test/unit/upload.test.ts`, `scripts/smoke-test.ts`, `src/services/cleanup.ts`, `src/scheduled.ts`
- **Dispatch D (architectural fixes) owns:** `src/services/workflow-steps.ts`, `src/services/extraction.ts`, `src/repositories/jobs.ts`, `src/repositories/records.ts`, `src/services/cleanup.ts` (overlap is OK if no actual conflict), `scripts/setup.ts`, `scripts/provision.ts`

Without this constraint, both subagents edit the same files concurrently, and the orchestrator must resolve merge conflicts at the end (or re-dispatch one of them).
