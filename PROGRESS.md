# CadeiaDominial v2 — Progress

> Source of truth for task definitions: `docs/TASKS.md`.

## Merged PRs (v2)

- **PR #15** — Blindspot review (27 issues: 10 P0, 10 P1, 7 P2)
- **PR #16** — TASKS.md roadmap + SCHEMA\_DECISOES\_PENDENTES.md
- **PR #17** — docs/ restructure (T-403)
- **PR #18** — decisions branch sync
- **PR #19** — commit ERD files (T-400)
- **PR #20** — AGENTS.md development workflow
- **PR #21** — stale path reference fixes
- **PR #22** — ERD\_CADEIA\_DOMINIAL.md sync to v2 design
- **PR #24** — T-001 schema decisions Q1-Q15 + ERD v2 final ✅ MERGED
- **PR #25** — T-101 Drizzle v2 schema (19 files, 17 tables + 2 views). Codex 5/5 R4 ✅ MERGED
- **PR #26** — T-100 ERD v2 rev1 (schema drift fixes). Codex 5/5 R1 ✅ MERGED
- **PR #27** — CI fix: pnpm v9→v10, frozen-lockfile, composite action, shared Vitest suite ✅ MERGED
- **PR #28** — feat(web): minimal React Flow screenshot harness (3-node demo, `pnpm graph:screenshot`, e2e baseline PNG). Codex 5/5 R2 ✅ MERGED
- **PR #29** — chore(graph): post-merge polish (end-to-end verified, golden positions, fixture happy-path, docu...[truncated]

## Task Status

### Phase 0 — Decisions ✅ DONE

- **T-000** ✅ done — Decisions read and understood (Luandro + Hiure, 02-03/06/2026)
- **T-001** ✅ done — Q1-Q15 + Q11b answered with rationale. Codex gpt-5.5 xhigh 5/5 APROVA

### Phase 1 — Schema ✅ DONE

- **T-100** ✅ done — ERD v2 redraw + 1:1 sync. Codex 5/5 APROVA. Branch `docs/erd-v2-rev1` (merged + cleaned)
- **T-101** ✅ done — Drizzle v2 schema. 19 arquivos em `packages/api/drizzle/schema/` + migration. Codex 5/5 APROVA (round 4). Branch `feat/drizzle-schema-v2` (merged + cleaned)

### Phase 1.5 — Visualization (in progress)

- **T-500** 📋 ready — Custom node + edge types for `@xyflow/react` graph. **Ready to start** (no custom components shipped yet — current demo uses the default node type)
- **T-501** 🔧 in-progress — Graph data layer partially shipped (PR #28+#29). `types.ts`, `validateGraph` (shape + integrity), `layoutGraph` (dagre LR), `basic-graph.json` fixture, golden positions test, fixture happy-path test. **Still to do:** `generateMockGraph('linear'|'branching'|'merge')`, 100% unit test coverage
- **T-502** 🔧 in-progress — Graph page partially wired (PR #28+#29). `/graph` route → `GraphPreview` → `validateGraph` → `layoutGraph` → React Flow. **Still to do:** multi-chain mock, node selection, pan/zoom polish, detail panel, Lighthouse ≥ 90
- **T-503** 📋 planned — API endpoint + real data wiring (blocked on T-202)

### Phase 2 — Data

- **T-200** 📋 planned — Chain topology generator. **Ready to start** (parallel com T-500)
- **T-201** 📋 planned — Field filler (faker). **Ready to start** (T-101 merged, parallel com T-200)
- **T-202** 📋 planned — Seed orchestrator

### Phase 3 — Legacy-fit

- **T-300** 📋 planned — Load legacy Postgres dump into v2 schema, validate integrity. Blocked on T-202 + T-503 (graph must render legacy data). **Sub-task:** drop PII columns (cpf, rg, data\_nascimento, email, telefone) — Q5 decision

### Phase 4 — Cleanup ✅ DONE

- **T-400** ✅ done (PR #22) — ERD files committed
- **T-401** ✅ done — PROGRESS.md replaces BOOTSTRAP\_PROGRESS.md
- **T-402** ✅ done — Stale PRs triaged. PRs #7, #10, #11, #12 mantidos abertos intencionalmente (target `main`, conteúdo absorvido pelo v2)
- **T-403** ✅ done (PR #17) — docs/ restructure

## Active Worktrees

| Worktree | Branch | Status |
|---|---|---|
| `CadeiaDominial/` | `v2` | Main checkout (clean) |
| `worktrees/decisions/` | `docs/roadmap-and-pending-decisions` | Long-lived decisions branch (1f69d94) |
| `worktrees/t-001-v2/` | `feat/t-001-schema-decisions-v2` | T-001 follow-up: 3 unpushed commits (rounds 4-6 review fixes) — out of scope here, owned by Hiure |

Graph-harness worktree (PR #28+#29) merged and cleaned up.

## Key Decisions Summary (Q1-Q15)

| Q | Topic | Choice |
|---|---|---|
| Q1 | Cascade on Imovel delete | C: soft-delete + CASCADE admin-only |
| Q2 | Soft-delete vs hard-delete | B: `deleted_at` on all tables |
| Q3 | OrigemFimCadeia cardinality | B: 1:N (as Django) |
| Q4 | PII encryption | A: plaintext (Pessoa only has `nome`) |
| Q5 | CPF/CNPJ validation | REMOVE PII fields from v2 |
| Q6 | React Flow: all vs current | A: show all chain ends always |
| Q7a | Delete menu UX | B: Edit / Move / Soft-delete |
| Q7b | Cascade scope | B: conservative (I+junctions, L preserved) |
| Q8 | Restore semantics | A: symmetric to Q7b |
| Q9 | Analysis trail | C: history + creation provenance |
| Q10 | Raw vs normalized | A: raw verbatim + FTS5 fuzzy search |
| Q11b | CRI table design | `cri` table, `documento.cri_id` FK direct |
| Q12 | Delete confirmation | D: preview + dialog |
| Q13 | Chain membership | B: N:N junction `imovel_documento` |
| Q14 | MOVE cross-chain | B: append-only event, Lancamento not mutated |
| Q15 | Delete shared Document | D: unlink from chain; admin-only global delete |

## CI Status

- **`ci-validate.yml`**: ✅ green (4/4: install-build, lint-typecheck, test-unit, test-e2e)
- Composite action `.github/actions/setup-pnpm-node/` reusável
- `packages/shared` tem suite Vitest (16 testes, PDF rendering + Zod schemas)

## PR Salvage Plan

- **PR #12** (Drizzle ORM scaffolding) — ✅ DONE em T-101. SQLite schema reaproveitado como estrutura, reescrito para Q1-Q15.
