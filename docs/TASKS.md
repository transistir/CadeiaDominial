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
- **Status:** completed (2026-06-02)
- **Owner:** Luandro (decisor final), Hiure (implementador — respondeu via grupo)
- **Description:** Provide a decision for each of Q1 (cascade on Imovel delete), Q2 (soft vs hard delete), Q3 (OrigemFimCadeia cardinality), Q4 (PII encryption at rest), Q5 (CNPJ/CPF validation location), Q6 (OrigemFimCadeia in React Flow — current vs full provenance).
- **Output:** A `## Decisões` section appended to `docs/db/SCHEMA_DECISOES_PENDENTES.md` with the chosen option for each Q, plus rationale (one paragraph max per Q).
- **Acceptance:** All 6 questions have a chosen option recorded; no "?" or "TBD" remains in the answers section.
- **Decisions summary:** Q1=C, Q2=B, Q3=B, Q4=A, Q5=remove CPF, Q6=A. **Critical context** (Hiure, 2026-06-02): v2 users are grilagem researchers who copy cartório data verbatim including errors (divergences are fraud indicators). This anchored Q2/B, Q3/B, Q4/A, Q5/remove, Q6/A.
- **Side effects:** Created T-XXX (chain visualization controls) and a sub-task of T-300 (discard PII columns from legacy).
- **Blocks (released):** T-100, T-101, T-200, T-201, T-202, T-300 (now unblocked).

---

## Phase 1 — Schema (after decisions)

### T-100 — Re-draw the ERD
- **Status:** open (unblocked after T-001)
- **Worktree branch:** `docs/erd-v2-rev1`
- **Files:** `docs/db/erd-v2.mmd`, `docs/db/erd-v2-legend.md`, `docs/db/erd-v2-rendered.png`
- **Description:** Apply the fixes from §1.2 of the blindspot review (missing FKs, missing columns, OrigemFimCadeia placement, etc.). Reflect the Q1–Q6 decisions **and** the new constraints (cross-chain delete behavior, soft-delete semantics). Re-render the PNG.
- **Acceptance:**
  - ERD matches **v2 design** (NOT Django 1:1 — v2 normalizes `origem` as its own table, drops PII columns, adds `deleted_at` per Q1/Q2)
  - All FKs and unique constraints from §"Database Constraints" present
  - PNG is regenerated and ≤ 1MB
  - Diff is schema-only (no doc tangents)
  - Cross-references to `SCHEMA_DECISOES_PENDENTES.md` (decisions) and `TASKS.md` (T-104, T-105) intact
- **Blocks:** T-101.

### T-101 — Author the Drizzle schema
- **Status:** open (unblocked after T-100)
- **Worktree branch:** `feat/drizzle-schema-v2`
- **Files:** `packages/api/drizzle/schema.ts`, generated `packages/api/drizzle/migrations/*.sql`
- **Description:** Translate the **v2 ERD** (NOT Django 1:1) to Drizzle. 13 tables (or 14 if origem is split out — verify in T-100), all FKs, all `deleted_at` columns from Q1/Q2, `pessoa` with only `id`/`nome`/`deleted_at` (PII dropped per Q5), all unique constraints. **Opt in to FK enforcement** (D1/SQLite requires `PRAGMA foreign_keys = ON` per connection). Cascade strategy per FK: **app-level soft-delete by default; hard-delete CASCADE only via admin route** (Q1/Cascade rephrasing — see `SCHEMA_DECISOES_PENDENTES.md` linha 504).
- **Acceptance:**
  - `pnpm db:generate` produces a clean migration
  - `pnpm db:migrate:local` runs without error on an empty D1
  - All FKs are declared with `references()` and a clear cascade strategy (default: `ON DELETE RESTRICT` for app-level soft-delete; admin purge uses raw SQL with cascade)
  - 100% type-safe (no `any` columns)
- **Blocks:** T-200, T-201, T-300.

---

## Phase 1.5 — Visualization controls (parallelizable with Phase 2+)

> Derived from Q6 (2026-06-02 session). Cadenas com centenas de documentos inviabilizam a visualização sem controles de navegação. Não cabe na Q6 (que era estreita — só "mostrar todos os fins ou não"); precisa ser uma feature própria.

### T-104 — Chain visualization controls (toggle de ramos, colapso, filtros, export)
- **Status:** open
- **Blocked on:** T-101 (Drizzle schema)
- **Worktree branch:** `feat/chain-visualization-controls`
- **Files:** `packages/web/src/components/ChainGraph/Controls.tsx`, `packages/web/src/components/ChainGraph/layouts/`, `packages/web/src/utils/exportChain.ts`
- **Description:** Implementar os controles de navegação do React Flow pra cadeias de 100s+ de documentos:
  - **Toggle por ramo:** clicar num Lancamento esconde toda a subárvore abaixo; clicar de novo restaura
  - **Colapso de subárvore:** nó "Pai" com badge `+N descendentes`; clicar expande inline
  - **Filtro por classificação de fim de cadeia** (ancorado em Q3): mostrar só `origem_lidima`, esconder `inconclusa`, etc. — esses são os marcadores de grilagem
  - **Filtro por tipo de documento:** só matrículas, só transcrições
  - **Layouts de export** (PDF retrato, PDF paisagem, PNG alta-res, XLSX tabular): usuário escolhe layout antes de exportar
- **Acceptance:**
  - Cadeia com 500 documentos renderiza em <2s com todos os controles desligados
  - Toggle de ramo é instantâneo (<100ms)
  - Export PDF de um ramo específico cabe em A4 (retrato) ou A3 (paisagem)
  - Filtros combinam (e.g. "só mats + só origens_lidimas")
- **Why own task, not embedded in Q6:** o problema "centenas de docs" é maior que a Q6. Q6 só definia a visibilidade default dos `origem_fim_cadeia`; os controles de navegação são uma camada genérica de UX que serve pra cadeia inteira.

### T-105 — Soft-delete workflow + cross-chain blast radius UI
- **Status:** open
- **Blocked on:** T-101, **Q7-Q12 answered**
- **Worktree branch:** `feat/soft-delete-workflow`
- **Files:** `packages/api/src/services/softDelete.ts`, `packages/web/src/components/DeleteDialog/BlastRadius.tsx`, `packages/web/src/components/DeleteDialog/`
- **Description:** Implementar a camada de aplicação que faz soft-delete + admin-purge (Q1/Cascade) com **confirmação obrigatória** mostrando blast radius cross-chain (Q7/Q12). Componentes:
  - **`softDelete(entity, id)`** — service que seta `deleted_at` em cascata, respeitando compartilhamento cross-chain (Q7b)
  - **`hardPurge(entity, id, adminUser, reason)`** — admin-only; FK CASCADE roda aqui; audit log
  - **`BlastRadius` component** — antes do delete, conta N (imóveis donos) + M (chains referenciando) e mostra ao usuário
  - **Confirmation dialog** — botão padrão "Editar ao invés de apagar"; botão destrutivo "Apagar mesmo assim" (vermelho, dupla confirmação)
- **Acceptance:**
  - Tentar soft-deletar um Documento com N+M>0 mostra dialog com blast radius completo
  - Hard-purge via admin route registra `deleted_by`, `delete_reason`, `purged_at` em audit log
  - Soft-delete cross-chain preserva Documento visível (com badge) nas chains que o referenciam
  - 100% testado com chains sintéticas (T-200/T-202) com cross-references conhecidos
- **Why own task:** Q7 (cross-chain delete behavior) + Q12 (UX confirmation) são decisões de aplicação, não de schema. T-100/T-101 podem começar sem esperar Q7-Q12; T-105 fica bloqueado neles.

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
- **Sub-task (added 2026-06-02, from Q5 decision):** **Discard PII columns from legacy on v2 ingest.** Drop these columns from `Pessoas` when loading: `cpf`, `rg`, `data_nascimento`, `email`, `telefone`. v2 `pessoa` only has `id` + `nome` + `deleted_at`. The legacy-fit script must:
  - **Preserve `Pessoa.id` byte-for-byte** from legacy (no remap) — mantém referências cruzadas
  - **Allow duplicate `nome`** — Q5 remove `cpf`, então homônimos passam a ser legítimos no v2; legacy-fit NÃO pode tentar dedupar
  - **Preserve `lancamento_pessoa.nome_digitado` verbatim** — campo é cartório-verbatim; trim/case/accent/Unicode normalization PROIBIDOS
  - **Migrate legacy `Lancamento.transmitente_id` / `adquirente_id` into `lancamento_pessoa`** — Django tem dois campos FK; v2 normaliza em `lancamento_pessoa` com `papel` (`transmitente` / `adquirente` / `outro`)
  - **Count dropped non-null PII per column** without logging actual values (privacidade): `"cpf: N1, rg: N2, data_nascimento: N3, email: N4, telefone: N5"`
  - **Not fail** when these columns are missing from the target schema
  - **Log a clear summary** at end: `"Discarded PII: X rows had PII fields. Preserved: nome (verbatim, no normalization)"`
  - **Assert no normalization on `nome`** post-load: compare hash of input bytes vs hash of stored bytes (proteção contra sanitização acidental)
- **Acceptance:**
  - `pnpm legacy-fit` exits 0 on a clean run
  - Report shows: ✓ row count per table, ✓ FK check, ✓ NOT NULL check, ✓ (optional) CHECK check, ✓ "PII fields discarded: N (cpf: N1, rg: N2, …)"
  - The legacy data renders in `packages/web` without manual fixing
  - **NEW (2026-06-02):** PII columns are dropped on ingest; the `nome` strings that came from cartório are preserved byte-for-byte
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

### T-403 — Organize `docs/` structure
- **Status:** in-progress (PR #17)
- **Worktree branch:** `docs/organize-docs-structure`
- **Files:** `docs/README.md` (new), `docs/domain/` (renamed from `docs/cadeia-dominial/`), `docs/db/README.md` (new), `docs/prd/README.md` (new), `docs/db/erd-v2.{mmd,-legend.md}` (renamed), `docs/domain/react-flow-quick-reference.md` (moved from root)
- **Description:** Reorganize `docs/` to fix navigation, naming, and discoverability. No content or schemas changed.
- **Scope:**
  - Rename `docs/cadeia-dominial/` → `docs/domain/` (English, cleaner)
  - 7 internal files to kebab-case
  - Move `docs/react-flow.md` → `docs/domain/react-flow-quick-reference.md`
  - Rename `docs/db/SCHEMA_CONSOLIDATED_ERD.mmd` → `erd-v2.mmd` and its legend
  - Add 4 index files (root + domain + db + prd)
  - Cross-link `MIGRATION_GUIDE.md` ↔ `MIGRATION_CHECKLIST.md`
  - Fix 3 broken internal cross-references
- **Acceptance:**
  - All cross-references verified — zero broken links after renames
  - Git history preserved (used `git mv` for all renames)
  - No source code or schema changes
  - PR opened against `v2`
- **Out of scope:** untracked `docs/ERD_CADEIA_DOMINIAL.{md,png}` (handled separately — see related documents), `db/legacy/`, `legacy-django/`, PRD JSON filenames.

---

## Status summary

| Task | Status | Blocker |
|---|---|---|
| T-000 | open | — |
| T-001 | **completed (2026-06-02)** | was: T-000 |
| T-100 | open (unblocked after T-001) | was: T-001 |
| T-101 | open (unblocked after T-001) | was: T-100 |
| T-104 | open (NEW 2026-06-02, Phase 1.5) | T-101 |
| T-105 | open (NEW 2026-06-02, from Q7-Q12) | T-101, Q7-Q12 answered |
| T-200 | open (unblocked after T-001) | was: T-101 |
| T-201 | open (unblocked after T-001) | was: T-101 |
| T-202 | open (unblocked after T-001) | was: T-200, T-201 |
| T-300 | open (unblocked after T-001) | was: T-101, T-202 |
| T-400 | open | — |
| T-401 | open | — |
| T-402 | open | — |
| T-403 | in-progress (PR #17) | — |

**Current gate: T-001 done. Next priority: T-100 (re-draw ERD) and T-101 (Drizzle schema) can both start.** T-104 (visualization controls) is parallelizable with Phase 2/3 work.

---

## Related documents

- `docs/SCHEMA_V2_BLINDSPOT_REVIEW.md` — the 27-issue audit (PR #15)
- `docs/db/SCHEMA_DECISOES_PENDENTES.md` — the 6 blocking decisions (in pt-BR, this PR)
- `docs/ERD_CADEIA_DOMINIAL.md` — the schema draft (target of T-100). **Note:** as of the docs/ restructure (T-403, PR #17), the v2 ERD is at `docs/db/erd-v2.mmd` and the legacy Django ERD will be moved to `docs/legacy-django/erd-modelo-antigo.md` in a follow-up.
- `docs/legacy-django/03-database-models.md` — Django source of truth
- `docs/MIGRATION_GUIDE.md` — overall migration architecture
- `docs/ARCHITECTURE_DECISIONS.md` — log of past architecture decisions
- PR #17 — `docs(structure): reorganize docs/ for navigation and clarity` (T-403)
