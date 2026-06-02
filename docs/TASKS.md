# CadeiaDominial v2 — Roadmap & Tasks

> **This file is the source of truth for "what we're doing next".** When in doubt, follow the order here. Tasks are written so they can be picked up by any agent or human in any order, but **must not be parallelized past their dependency gate**.

## Context

We are migrating the CadeiaDominial land-registry system from a legacy Django/Postgres stack to a new TypeScript monorepo (Cloudflare Workers + React + Hono + Drizzle ORM on D1/SQLite). The Django models in `docs/legacy-django/03-database-models.md` are the **source of truth** for what the schema must be able to represent. Everything new is built on the `v2` branch — `main` is frozen historical reference.

The full blindspot review of the schema lock-in draft is in `docs/SCHEMA_V2_BLINDSPOT_REVIEW.md` (PR #15). It found **27 issues** (10 P0, 10 P1, 7 P2). The P0 items must be resolved before any schema code lands.

## How to use this file

1. Pick the **lowest-id open task** whose dependencies are all met.
2. Open a new git worktree off `v2` (one worktree per task; never work on `v2` directly).
3. When done, open a PR targeting `v2`. Reference the task ID in the PR body.
4. Update task status here in the same PR (or as a follow-up commit).
5. **A task is not done until its PR is merged AND its acceptance criteria are met.**

## Phases

```
Phase 0: Decisions ──┐
                     ├──> Phase 1: Schema ──> Phase 2: Data ──> Phase 3: Legacy-fit ──> Phase 4: Cleanup
                     │       (Drizzle + ERD)    (faker)         (proof)               (housekeeping)
                     │
       BLOCKING: nothing else starts until this phase closes
```

---

## Phase 0 — Decisions (BLOCKING)

> Nothing in Phase 1 can start until all 6 decisions in `docs/db/SCHEMA_DECISOES_PENDENTES.md` are answered.

### T-000 — Read the pending decisions
- **Status:** open
- **Owner:** anyone (Luandro, Hiure, or reviewer)
- **Description:** Read `docs/db/SCHEMA_DECISOES_PENDENTES.md` end-to-end. For each of the 6 questions (Q1–Q6), understand the trade-offs, especially the visual impact on the React Flow graph.
- **Acceptance:** Decision-maker can articulate each question + at least one option's DB/chain-graph consequence without re-reading the doc.
- **Depends on:** nothing.
- **Blocks:** T-001.

### T-001 — Answer Q1–Q6
- **Status:** blocked on T-000
- **Owner:** Luandro (project lead)
- **Description:** Provide a decision for each of Q1 (cascade on Imovel delete), Q2 (soft vs hard delete), Q3 (OrigemFimCadeia cardinality), Q4 (PII encryption at rest), Q5 (CNPJ/CPF validation location), Q6 (OrigemFimCadeia in React Flow — current vs full provenance).
- **Output:** A `## Decisões` section appended to `docs/db/SCHEMA_DECISOES_PENDENTES.md` with the chosen option for each Q, plus rationale (one paragraph max per Q).
- **Acceptance:** All 6 questions have a chosen option recorded; no "?" or "TBD" remains in the answers section.
- **Blocks:** all of Phase 1.

---

## Phase 1 — Schema (after decisions)

### T-100 — Re-draw the ERD
- **Status:** blocked on T-001
- **Worktree branch:** `docs/erd-v2-rev1`
- **Files:** `docs/ERD_CADEIA_DOMINIAL.md`, `docs/ERD_CADEIA_DOMINIAL.png`
- **Description:** Apply the fixes from §1.2 of the blindspot review (missing FKs, missing columns, OrigemFimCadeia placement, etc.). Reflect the Q1–Q6 decisions. Re-render the PNG.
- **Acceptance:**
  - ERD matches Django `03-database-models.md` 1:1 on every table
  - All FKs and unique constraints from §"Database Constraints" present
  - PNG is regenerated and ≤ 1MB
  - Diff is schema-only (no doc tangents)
- **Blocks:** T-101.

### T-101 — Author the Drizzle schema
- **Status:** blocked on T-100
- **Worktree branch:** `feat/drizzle-schema-v2`
- **Files:** `packages/api/drizzle/schema.ts`, generated `packages/api/drizzle/migrations/*.sql`
- **Description:** Translate the Django models to Drizzle. 13 tables, all FKs, all columns, all unique constraints. **Opt in to FK enforcement** (D1/SQLite requires `PRAGMA foreign_keys = ON` per connection).
- **Acceptance:**
  - `pnpm db:generate` produces a clean migration
  - `pnpm db:migrate:local` runs without error on an empty D1
  - All FKs are declared with `references()` and a clear cascade strategy per Q1
  - 100% type-safe (no `any` columns)
- **Blocks:** T-200, T-201, T-300.

---

## Phase 2 — Data generation

### T-200 — Chain topology generator
- **Status:** blocked on T-101
- **Worktree branch:** `feat/chain-topology-generator`
- **Files:** `scripts/seed/chain-topology.ts`, `scripts/seed/__tests__/chain-topology.test.ts`
- **Description:** Deterministic generator that produces a **valid** chain graph shape: exactly one `inicio_matricula` per chain, every Registro with ≥ 1 origin, every Averbação with no origin, every chain ending in a `FimCadeia` (when Q3 = "many-per-chain"). Pure function: `(seed: number, n: number) => TopologyGraph`.
- **Acceptance:**
  - All invariant tests pass (no orphan edges, no cycles, exactly-one root per chain)
  - Same seed → same graph (reproducible)
  - At least 3 distinct chain shapes generated (linear, branching, with merges)
- **Blocks:** T-202.

### T-201 — Field filler
- **Status:** blocked on T-101 (can run in parallel with T-200)
- **Worktree branch:** `feat/field-filler`
- **Files:** `scripts/seed/field-filler.ts`
- **Description:** Uses `@faker-js/faker` to fill non-deterministic fields (names, dates, document numbers, cartórios, etc.) per the constraints from Q1–Q6 (e.g. CNPJ/CPF format if Q5 = DB-level).
- **Acceptance:**
  - `field-filler(topology)` produces rows that insert without error into the Drizzle schema
  - If Q4 = "encrypt at rest", produces ciphertext + provides decryption key path
- **Blocks:** T-202.

### T-202 — Seed orchestrator
- **Status:** blocked on T-200, T-201
- **Worktree branch:** `feat/seed-orchestrator`
- **Files:** `scripts/seed/seed.ts`, `scripts/seed/__tests__/seed.test.ts`
- **Description:** Combines topology + filler, inserts via Drizzle, asserts invariants post-insert.
- **Acceptance:**
  - `pnpm seed` produces a working local D1 with ≥ 50 properties and ≥ 500 lancamentos
  - `packages/web` can render the React Flow graph against the seed data
- **Blocks:** T-300.

---

## Phase 3 — Legacy-fit proof (the gate before merge)

### T-300 — Legacy-fit script
- **Status:** blocked on T-101, T-202
- **Worktree branch:** `feat/legacy-fit-script`
- **Files:** `scripts/migration/legacy-fit.ts`, `scripts/migration/__tests__/legacy-fit.test.ts`
- **Description:** Loads `old/data.cleaned.core.no-auth.no-unistr.sql` (3.3MB Postgres dump) into the new Drizzle schema, then asserts: row counts match expected per table, no FK violations, no `NOT NULL` failures, no `CHECK` failures (if Q5 = DB-level). Emits a human-readable report.
- **Acceptance:**
  - `pnpm legacy-fit` exits 0 on a clean run
  - Report shows: ✓ row count per table, ✓ FK check, ✓ NOT NULL check, ✓ (optional) CHECK check
  - The legacy data renders in `packages/web` without manual fixing
- **Blocks:** T-101 PR merge, T-200 PR merge, T-201 PR merge, T-202 PR merge.

---

## Phase 4 — Cleanup (parallelizable)

### T-400 — Commit the uncommitted ERD files
- **Status:** open (independent of phases above)
- **Worktree branch:** `chore/commit-erd-files`
- **Files:** `docs/ERD_CADEIA_DOMINIAL.md`, `docs/ERD_CADEIA_DOMINIAL.png` (the two uncommitted files in the main `v2` worktree)
- **Description:** Stage and commit the existing uncommitted ERD files as a `docs:` chore commit on their own.
- **Acceptance:** `git status` on `v2` is clean.

### T-401 — Update BOOTSTRAP_PROGRESS.md
- **Status:** open
- **Worktree branch:** `docs/refresh-bootstrap-progress`
- **Files:** `BOOTSTRAP_PROGRESS.md`
- **Description:** Refresh to reflect the v2 state, link to this TASKS.md, mark completed bootstrap items.
- **Acceptance:** Mentions TASKS.md and the schema decision phase.

### T-402 — Triage stale PRs
- **Status:** open
- **Files:** (no local work; use `gh pr list`)
- **Description:** For each of: #6 (cleanup/clean), #7 (cleanup/unused-python-files), #8 (docker-containerization), decide: merge, close, or rebase onto `v2`. Document decision in PR comments.

---

## Status summary

| Task | Status | Blocker |
|---|---|---|
| T-000 | open | — |
| T-001 | blocked | T-000 |
| T-100 | blocked | T-001 |
| T-101 | blocked | T-100 |
| T-200 | blocked | T-101 |
| T-201 | blocked | T-101 |
| T-202 | blocked | T-200, T-201 |
| T-300 | blocked | T-101, T-202 |
| T-400 | open | — |
| T-401 | open | — |
| T-402 | open | — |

**Current gate: T-000 → T-001.** Nothing else matters until Luandro reads the decision doc and answers Q1–Q6.

---

## Related documents

- `docs/SCHEMA_V2_BLINDSPOT_REVIEW.md` — the 27-issue audit (PR #15)
- `docs/db/SCHEMA_DECISOES_PENDENTES.md` — the 6 blocking decisions (in pt-BR, this PR)
- `docs/ERD_CADEIA_DOMINIAL.md` — the schema draft (target of T-100)
- `docs/legacy-django/03-database-models.md` — Django source of truth
- `docs/MIGRATION_GUIDE.md` — overall migration architecture
- `docs/ARCHITECTURE_DECISIONS.md` — log of past architecture decisions
