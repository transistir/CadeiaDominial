# CadeiaDominial v2 — Progress

> Replaces `BOOTSTRAP_PROGRESS.md` (jan 2026 PRD tracker). This file tracks the real project status.
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
- **PR #24** — T-001 schema decisions Q1-Q15 + ERD v2 final (ready to merge)
- **PR #27** — CI fix: pnpm v9→v10, frozen-lockfile, composite action, shared Vitest suite (MERGED)

## Task Status

### Phase 0 — Decisions

- **T-000** ✅ done — Decisions read and understood (Luandro + Hiure, 02-03/06/2026)
- **T-001** ✅ done (PR #24 pending merge) — Q1-Q15 + Q11b answered with rationale. Codex gpt-5.5 xhigh + Opus 4.8 APROVA 5/5

### Phase 1 — Schema

- **T-100** ✅ done (commit `d56053a`) — ERD v2 redraw + 1:1 sync. `docs/db/erd-v2.mmd` add `cri.tipo` (CHECK CRI/OUTRO) para paridade com Django Cartorios. PNG re-renderizada (gitignored per `AGENTS.md`). Branch `docs/erd-v2-rev1`
- **T-101** ✅ done (commit `a269dcc`) — Drizzle v2 schema. 19 arquivos em `packages/api/drizzle/schema/` + migration `0000_real_quentin_quire.sql` (297 linhas, 17 tables + 2 views + 13 indexes). Aplica limpa via `better-sqlite3`. **Salvou scaffolding de PR #12** (estrutura sqlite-core, relations) e reescreveu para Q1-Q15. Branch `feat/drizzle-schema-v2`. **Follow-ups:** T-201 (seed), T-202 (FTS5), T-301 (query layer), T-401 (typecheck em `src/index.ts` tem 2 erros pré-existentes não relacionados)
- **T-104** 📋 planned — Visualization controls (toggle branches, collapse, filters). Blocked on T-100 + T-101

### Phase 2 — Data

- **T-200** 📋 planned — Chain topology generator
- **T-201** 📋 planned — Field filler (faker)
- **T-202** 📋 planned — Seed orchestrator

### Phase 3 — Legacy-fit

- **T-300** 📋 planned — Load legacy Postgres dump into v2 schema, validate integrity. **Sub-task:** drop PII columns (cpf, rg, data\_nascimento, email, telefone) — Q5 decision

### Phase 4 — Cleanup

- **T-400** ✅ done (PR #22) — ERD files committed
- **T-401** ✅ done — This file replaces BOOTSTRAP\_PROGRESS.md
- **T-402** ✅ done — Stale PRs triaged. **Decision 04/06/2026: do NOT close** PRs #7, #10, #11, #12 (Luandro) — all target `main` (frozen) and content is absorbed by v2
- **T-403** ✅ done (PR #17) — docs/ restructure

## Active Worktrees

| Worktree | Branch | Purpose |
|---|---|---|
| `CadeiaDominial/` | `v2` | Main checkout |
| `worktrees/decisions/` | `docs/roadmap-and-pending-decisions` | Long-lived decisions branch |
| `worktrees/ci-pnpm-baseline/` | `fix/ci-pnpm-baseline` | ✅ MERGED PR #27 (cleaned up) |
| `worktrees/t-001-v2/` | `feat/t-001-schema-decisions-v2` | PR #24 source. Merge candidate |
| `worktrees/t-100-erd/` | `docs/erd-v2-rev1` | T-100 ERD redraw. Rebased on `feat/t-001-schema-decisions-v2` (05eeee9) |
| `worktrees/t-101-drizzle/` | `feat/drizzle-schema-v2` | T-101 Drizzle schema. Rebased on `feat/t-001-schema-decisions-v2` (05eeee9) |
| `worktrees/t-001-schema-decisions/` | `feat/t-001-schema-decisions-q1-q6` | Orphan — superseded by `t-001-v2`. Cleanup after PR #24 merges |

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

<<<<<<< HEAD
- **`ci-validate.yml`**: ✅ fixed in PR #27 (pnpm v9→v10 via `packageManager`, `--frozen-lockfile` enforced, scoped `rm -rf` for `ci-validate.sh`, `test:unit` isolated from e2e chain).

## Recently Resolved (2026-06-04)

- **GH_TOKEN renewal** — `gh` CLI auth restored; pushes to `fix/ci-pnpm-baseline` and other branches now work.
- **CI pnpm v9/v10 mismatch** — root cause was hardcoded `version: 9` in three `pnpm/action-setup@v4` calls; removed in favour of `packageManager: pnpm@10.28.2` in root `package.json` (already set in PR #24).
- **`test:unit` was running the wrong turbo task** — root `test:unit` invoked `turbo run test` (which runs ALL test variants including e2e + Playwright). Fixed to `turbo run test:unit`, with the new task defined in `turbo.json` and a `test:unit` script added to each workspace that has unit tests. `packages/shared` has only types — added an intentional no-op `test:unit` script that documents the absence.
- **`ci-validate.sh` broad `find` was dangerous** — `find ... -name node_modules -exec rm -rf` would nuke sibling repos checked out alongside this one. Replaced with scoped `rm -rf node_modules packages/*/node_modules`.
=======
- **`ci-validate.yml`**: broken (pnpm v9 vs v10 mismatch). Fix ready in `fix/ci-pnpm-baseline` worktree. Blocked on GH\_TOKEN renewal.

## Blockers

- **GH_TOKEN expired** — cannot push, open PRs, or close PRs until renewed. Generate new PAT at https://github.com/settings/tokens/new (`repo` scope, no expiration). Once restored:
  1. Merge PR #24 (T-001)
  2. Merge `ci-pnpm-baseline` (CI fix)
  3. Rebase T-100 + T-101 worktrees onto merged `v2`
  4. Open PRs for T-100 (`docs/erd-v2-rev1`) + T-101 (`feat/drizzle-schema-v2`)
>>>>>>> 2594205 (docs(progress): mark T-100 + T-101 done, PR #12 salvaged (2026-06-04))

## PR Salvage Plan

- **PR #12** (Drizzle ORM scaffolding) — ✅ **DONE** em T-101 (commit `a269dcc`). 7 arquivos SQLite schema em `drizzle-sqlite/` foram reaproveitados como estrutura (sqlite-core syntax, relations, FK patterns). Reescritos para Q1-Q15: PII removida de pessoa, single `cri_id` FK (Q11b), N:N junction `imovel_documento` (Q13), `lancamento_move_event` append-only (Q14), soft-delete `deleted_at` (Q2), `audit_log` (Q9), TypeScript-native naming (sem `*IdId`).
