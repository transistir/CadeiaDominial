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
                     ├──> Phase 1: Schema ──> Phase 1.5: Visualization ──> Phase 2: Data ──> Phase 3: Legacy-fit
                     │       (Drizzle + ERD)    (@xyflow/react graph)        (seed/faker)      (proof)
                     │
       BLOCKING: nothing else starts until this phase closes
```

---

## Phase 0 — Decisions (BLOCKING)

> Nothing in Phase 1 can start until all 6 decisions in `docs/db/SCHEMA_DECISOES_PENDENTES.md` are answered.

### T-000 — Read the pending decisions
- **Status:** ✅ done (2026-06-02/03, Luandro + Hiure)
- **Owner:** anyone (Luandro, Hiure, or reviewer)
- **Description:** Read `docs/db/SCHEMA_DECISOES_PENDENTES.md` end-to-end. For each of the 6 questions (Q1–Q6), understand the trade-offs, especially the visual impact on the React Flow graph.
- **Acceptance:** Decision-maker can articulate each question + at least one option's DB/chain-graph consequence without re-reading the doc. ✅
- **Depends on:** nothing.
- **Blocks:** T-001.

### T-001 — Answer Q1–Q6
- **Status:** ✅ done (PR #24 merged). Extended to Q1-Q15 + Q11b.
- **Owner:** Luandro (project lead)
- **Description:** Provide a decision for each of Q1 through Q15 + Q11b. Codex gpt-5.5 xhigh 5/5 APROVA. Opus 4.8 5/5 APROVA.
- **Output:** `docs/db/SCHEMA_DECISOES_PENDENTES.md` with all answers + rationale.
- **Acceptance:** All questions answered, no TBDs remain. ✅
- **Blocks:** all of Phase 1.

---

## Phase 1 — Schema (after decisions)

### T-100 — Re-draw the ERD
- **Status:** ✅ done (PR #26 merged). Codex 5/5 APROVA.
- **Worktree branch:** `docs/erd-v2-rev1` (merged + cleaned)
- **Files:** `docs/db/erd-v2.mmd`, `docs/db/erd-v2-legend.md`
- **Description:** ERD v2 redraw + 1:1 sync com Drizzle schema. `cri.tipo` (CHECK CRI/OUTRO), area columns matching DB names (`valor_transacao_centavos`, `area_centiares`, `area_ha_centiares`), `origem.deleted_at` no inventário.
- **Acceptance:** ✅ All FKs, columns, CHECKs, and soft-delete annotations verified byte-identical between ERD and Drizzle schema files.
- **Blocks:** T-101.

### T-101 — Author the Drizzle schema
- **Status:** ✅ done (PR #25 merged). Codex 5/5 APROVA (round 4).
- **Worktree branch:** `feat/drizzle-schema-v2` (merged + cleaned)
- **Files:** `packages/api/drizzle/schema/` (19 files), `packages/api/drizzle/migrations/0000_real_quentin_quire.sql` (297 linhas, 17 tables + 2 views + 13 indexes)
- **Description:** Translate Django models → Drizzle ORM. All Q1-Q15 decisions implemented. PII removed (Q5), soft-delete on all tables (Q2), `cri` table with `tipo` CHECK (Q11b), N:N junction `imovel_documento` (Q13), `lancamento_move_event` append-only (Q14), `audit_log` (Q9).
- **Acceptance:** ✅ `db:generate` clean, `db:migrate:local` clean, 100% type-safe, CI 4/4 green.
- **Blocks:** T-200, T-201, T-300.

---

## Phase 1.5 — Visualization (@xyflow/react)

> Phase 1 (schema) is done. Before generating seed data, set up the graph visualization layer so we can see what we're building against. Uses **mock data** initially; swaps to real API data once Phase 2 lands.
>
> **Key docs:** `docs/domain/react-flow-quick-reference.md` (canonical mapping), `docs/domain/tree-model.md` (DAG semantics), `docs/domain/fim-de-cadeia.md` (end-of-chain), `docs/domain/lancamento-tipos.md` (lancamento types).
>
> **Current state:** `@xyflow/react ^12.10.0` installed, skeleton `routes/graph.tsx` with 3 hardcoded nodes exists. TanStack Router + React Query wired. No custom nodes, no graph logic, no API endpoint.

### T-500 — Custom node + edge types
- **Status:** 📋 **ready to start**
- **Worktree branch:** `feat/xyflow-custom-nodes`
- **Files:** `packages/web/src/components/graph/`
- **Description:** Design and implement custom React Flow node types for the cadeia dominial graph:
  - `DocumentoNode` — matrícula, transcrição, averbação (card with numero, tipo, cartório, data)
  - `FimCadeiaNode` — synthetic leaf (color-coded: origem lídima green, sem origem red, inconclusa yellow)
  - `OrigemEdge` — edge type with origin label (matrícula/transcrição/fim_cadeia)
  - Styling: type-based color scheme matching legacy D3 (matrícula=blue, transcrição=purple, registro=teal)
- **Acceptance:**
  - Storybook or standalone page renders all 3 node types with sample data
  - Nodes are responsive (readable at 50%-200% zoom)
  - TypeScript: all props fully typed, no `any`
  - Vitest: snapshot tests for each node type
- **Depends on:** T-101 (schema defined for type alignment)
- **Blocks:** T-501

### T-501 — Graph data layer (types + mock builder)
- **Status:** blocked on T-500
- **Worktree branch:** `feat/xyflow-graph-data`
- **Files:** `packages/web/src/lib/graph/`
- **Description:** Pure TypeScript library that builds `{ nodes, edges }` from domain data:
  - `types.ts` — `CadeiaNode`, `CadeiaEdge`, `GraphData`, `ChainShape` types
  - `builder.ts` — `buildGraph(chainData): GraphData` — maps documentos → nodes, origens → edges, adds synthetic fim-cadeia leaves
  - `layout.ts` — `applyLayout(graphData): GraphData` — BFS from root, `x = depth * 300`, `y = indexWithinDepth * 120`. DAG-aware (nodes can have multiple parents)
  - `mock.ts` — `generateMockGraph(shape): GraphData` — produces 3+ chain shapes (linear, branching, with merge) for development without a backend
- **Acceptance:**
  - `buildGraph()` produces valid `{ nodes, edges }` from typed input
  - `applyLayout()` produces non-overlapping positions for graphs up to 100 nodes
  - `generateMockGraph('linear'|'branching'|'merge')` returns deterministic output
  - 100% unit test coverage on pure functions
- **Depends on:** T-500 (node/edge types for type alignment)
- **Blocks:** T-502

### T-502 — Graph page integration
- **Status:** blocked on T-501
- **Worktree branch:** `feat/xyflow-graph-page`
- **Files:** `packages/web/src/routes/graph.tsx` (rewrite), `packages/web/src/components/graph/GraphView.tsx`
- **Description:** Replace the hardcoded skeleton with a full-featured graph page:
  - `<GraphView>` component: `<ReactFlow>` with custom node/edge types, fitView, minimap, controls
  - Mock data toggle: loads from `mock.ts` initially, with a `<select>` to switch chain shapes
  - Interaction: pan, zoom, node click → detail panel (collapsible sidebar or drawer)
  - Fim-de-cadeia: synthetic leaf nodes rendered with classification colors
  - Responsive: works on desktop (1200px+) and tablet (768px+)
- **Acceptance:**
  - `/graph` renders a multi-chain mock graph with 20+ nodes
  - All 3 node types render correctly
  - Pan, zoom, fitView, minimap work
  - Node click opens detail panel with documento info
  - Lighthouse perf ≥ 90 on the graph route
  - E2E test: load graph, zoom, click node, verify detail
- **Depends on:** T-501
- **Blocks:** T-503

### T-503 — Graph API endpoint + data wiring
- **Status:** blocked on T-502, T-202
- **Worktree branch:** `feat/api-graph-endpoint`
- **Files:** `packages/api/src/routes/graph.ts`, `packages/web/src/lib/graph/api.ts`
- **Description:** Add `GET /api/cadeia/:imovelId` API endpoint that queries Drizzle for documento + lancamento + origem data, returns `{ nodes, edges }` JSON. Wire web to fetch from API instead of mock.
- **Acceptance:**
  - API returns valid graph JSON for any imóvel with seed data
  - Web fetches and renders real data
  - Fallback to mock when API returns empty
  - Error handling: loading state, error boundary, retry
- **Depends on:** T-502 (graph page), T-202 (seed data in DB)
- **Blocks:** T-300 (legacy data must render in graph)

---

## Phase 2 — Data generation

### T-200 — Chain topology generator
- **Status:** 📋 **ready to start** (T-101 merged, dependency met)
- **Worktree branch:** `feat/chain-topology-generator`
- **Files:** `scripts/seed/chain-topology.ts`, `scripts/seed/__tests__/chain-topology.test.ts`
- **Description:** Deterministic generator that produces a **valid** chain graph shape: exactly one `inicio_matricula` per chain, every Registro with ≥ 1 origin, every Averbação with no origin, every chain ending in a `FimCadeia` (when Q3 = "many-per-chain"). Pure function: `(seed: number, n: number) => TopologyGraph`.
- **Acceptance:**
  - All invariant tests pass (no orphan edges, no cycles, exactly-one root per chain)
  - Same seed → same graph (reproducible)
  - At least 3 distinct chain shapes generated (linear, branching, with merges)
- **Blocks:** T-202.

### T-201 — Field filler
- **Status:** 📋 **ready to start** (T-101 merged, can run in parallel with T-200)
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
- **Status:** ✅ done (PR #22)

### T-401 — Update BOOTSTRAP_PROGRESS.md
- **Status:** ✅ done — replaced by PROGRESS.md

### T-402 — Triage stale PRs
- **Status:** ✅ done — PRs #7, #10, #11, #12 kept open intentionally (target `main`, content absorbed by v2)

### T-403 — Organize `docs/` structure
- **Status:** ✅ done (PR #17)

---

## Status summary

| Task | Status | PR |
|---|---|---|
| T-000 | ✅ done | — |
| T-001 | ✅ done | #24 |
| T-100 | ✅ done | #26 |
| T-101 | ✅ done | #25 |
| **T-500** | 📋 **ready** | — |
| T-501 | blocked (T-500) | — |
| T-502 | blocked (T-501) | — |
| T-503 | blocked (T-502, T-202) | — |
| T-200 | 📋 ready | — |
| T-201 | 📋 ready | — |
| T-202 | blocked (T-200, T-201) | — |
| T-300 | blocked (T-202, T-503) | — |
| T-400 | ✅ done | #22 |
| T-401 | ✅ done | — |
| T-402 | ✅ done | — |
| T-403 | ✅ done | #17 |

**Current gate: Phase 1.5 — T-500 ready to start.** Custom node/edge types for `@xyflow/react` graph. Phase 2 (T-200, T-201) can run in parallel if desired.

---

## Related documents

- `docs/SCHEMA_V2_BLINDSPOT_REVIEW.md` — the 27-issue audit (PR #15)
- `docs/db/SCHEMA_DECISOES_PENDENTES.md` — the 6 blocking decisions (in pt-BR, this PR)
- `docs/ERD_CADEIA_DOMINIAL.md` — the schema draft (target of T-100). **Note:** as of the docs/ restructure (T-403, PR #17), the v2 ERD is at `docs/db/erd-v2.mmd` and the legacy Django ERD will be moved to `docs/legacy-django/erd-modelo-antigo.md` in a follow-up.
- `docs/legacy-django/03-database-models.md` — Django source of truth
- `docs/MIGRATION_GUIDE.md` — overall migration architecture
- `docs/ARCHITECTURE_DECISIONS.md` — log of past architecture decisions
- PR #17 — `docs(structure): reorganize docs/ for navigation and clarity` (T-403)
