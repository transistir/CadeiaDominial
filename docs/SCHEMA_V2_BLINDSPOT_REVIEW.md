# Blindspot Review: CadeiaDominial v2 DB Schema Lock-in

> Reviewed against: `docs/ERD_CADEIA_DOMINIAL.md` (the v2 draft ERD), `docs/legacy-django/03-database-models.md` (the Django source of truth, 688 lines), `packages/api/drizzle/schema.ts` (current Drizzle — only `health_checks` and `users`), `docs/react-flow.md` (React Flow conventions), `docs/D1_IMPORT.md` + `D1_LOCAL_DEV.md` (D1 quirks), `docs/MIGRATION_GUIDE.md` (architecture), `docs/MIGRATION_CHECKLIST.md` (plan), `packages/web/e2e/graph.spec.ts` (existing E2E), `packages/api/drizzle.config.ts` (Drizzle config), `packages/api/src/index.ts` (Hono entry).

---

## 1. Schema blindspots

### 1.1 [P0] The current Drizzle schema is empty for this domain

`packages/api/drizzle/schema.ts` contains **only** `health_checks` and `users`. The `users` table is auth (PRD-005, in progress). There is **no Drizzle code for any CadeiaDominial table** today. The ERD in `docs/ERD_CADEIA_DOMINIAL.md` is a **draft** sitting in `untracked` files; it has never been compiled or migrated. So "lock the schema" is really "**author the schema from scratch**" — the PR is going to be much larger than "single epic" implies unless it's broken up.

### 1.2 [P0] The ERD has substantial drift from the actual Django models

`docs/ERD_CADEIA_DOMINIAL.md` (269 lines, mermaid) was authored from a high-level pass and **drops or mis-models** several Django fields. Specific gaps vs `docs/legacy-django/03-database-models.md`:

| Entity | Missing in ERD | Django source line |
|---|---|---|
| `Imovel` | `cartorio` (FK → Cartorios) | `docs/legacy-django/03-database-models.md:244` — referenced by `Documento.cartorio` lineage but the ERD shows only `Imovel }o--|| TIs` and `Imovel }o--|| Pessoas` |
| `Documento` | `imovel` (FK → Imovel), `tipo` (FK → DocumentoTipo), `cartorio` (FK → Cartorios) columns | `:334-340` — ERD has these only as relationships, not as column list entries |
| `Lancamento` | `documento` (FK, the parent doc, distinct from `documento_origem`), `transmitente` (FK → Pessoas), `adquirente` (FK → Pessoas), `cartorio_origem`/`cartorio_transmissao`/`cartorio_transacao` (3x FKs to Cartorios), `tipo` (FK → LancamentoTipo) columns | `:411-448` |
| `LancamentoPessoa` | `lancamento` (FK), `pessoa` (FK → Pessoas) columns — ERD shows **only** `id, tipo, nome_digitado` | `:475-479` |
| `OrigemFimCadeia` | `lancamento` (FK → Lancamento) column | `:497` |
| `TIs_Imovel` | `tis_codigo` (FK → TIs) and `imovel` (FK → Imovel) — ERD shows just `id PK` | `:194-196` |
| `DocumentoImportado` | `documento` (FK → Documento), `imovel_origem` (FK → Imovel) | ERD shows only `id PK, data_importacao` |
| `Alteracoes` | `imovel` (FK), `tipo_alteracao`/`tipo_registro`/`tipo_averbacao` (3x FKs), `transmitente_alt`/`adquirente_alt` (FK → Pessoas), `cartorio_responsavel` (FK → Cartorios) | ERD column list is incomplete |
| `TerraIndigenaReferencia` | Missing phase dates mentioned in Django doc: `data_homologada`, `data_declarada`, `data_delimitada`, `data_em_estudo` plus `coordenacao_regional` | `:178-179` |

**Action:** Treat `docs/legacy-django/03-database-models.md` as the canonical source. The ERD needs a regeneration pass **before** code is written.

### 1.3 [P0] The ERD column lists vs relationship lists disagree

The mermaid diagram declares relationships that don't exist as columns. E.g. `Documento ||--o{ Lancamento : lancamentos` requires a `documento` FK column in `Lancamento`, but the column list under `Lancamento` only has `id, numero_lancamento, data, ...` — no `documento` column. **Mermaid validates syntax but not semantic coherence**; this slipped through.

### 1.4 [P0] Composite unique constraints are missing in the ERD

The Django models declare three `unique_together` constraints that the ERD never mentions:

- `Documento`: `unique_together = ('numero', 'cartorio')` — `03-database-models.md:357`
- `LancamentoPessoa`: `unique_together = ('lancamento', 'pessoa', 'tipo')` — `:482`
- `OrigemFimCadeia`: `unique_together = ['lancamento', 'indice_origem']` — `:511`

**For D1:** a composite unique index is just `UNIQUE (col_a, col_b)` and is supported. **Action:** declare these as `uniqueIndexes` in the Drizzle table definitions, not as runtime validation.

### 1.5 [P1] `TerraIndigenaReferencia` is read-only reference data — model it differently

This is a FUNAI-imported lookup table (`03-database-models.md:165-185`) that should not be subject to FK CASCADE/PROTECT the same way user-edited tables are. It has no upstream FKs and is consumed via `TIs.terra_referencia` (nullable). **Action:** call this out in the schema comment block; consider seeding it via a separate fixture file (`fixtures/funai-tis.json`) so it's clear it's reference data.

### 1.6 [P1] `Lancamento` has 8+ FKs — the busiest table

`Lancamento` references: `Documento` (parent), `Documento` (origin, self-ref), `LancamentoTipo`, `Pessoas` (transmitente), `Pessoas` (adquirente), `Cartorios` (origem), `Cartorios` (transmissao), `Cartorios` (transacao). Plus 10 boolean `requer_*` flags on `LancamentoTipo` driving validation.

**Action:** Plan the fixtures to exercise each FK independently and in combination. `cartorio_transacao` is "legacy — being phased out" per `:438`. Decide now whether to drop it (and write a data migration that nulls it) or keep it. **Recommend drop it in v2** — the legacy field is documented as deprecated, and dropping now is cheaper than later.

### 1.7 [P1] `LancamentoTipo` boolean flags as a config table

Ten `requer_*` boolean flags per `LancamentoTipo` is unusual. This is a config/lookup table that should probably become a **Zod schema in TypeScript** for v2 (validation at the API layer, not data layer). But that's a refactor of the existing pattern. **Action:** keep the booleans for parity with Django in this PR; flag a follow-up PRD to move to Zod schemas. Don't try to fix it here.

### 1.8 [P2] The `dominial_` table prefix in the SQL dump vs no prefix in the ERD

The dump uses `dominial_documento`, `dominial_lancamento`, etc. The ERD uses unprefixed names. **Action:** decide now. Recommendation: **drop the `dominial_` prefix** in v2 — it's a Django app-prefix artifact, and the Drizzle table names will be cleaner (`documento`, `lancamento`). Add a `dominio` schema in D1 if you want namespacing (D1 supports `ATTACH DATABASE` but not real schemas; just use the prefix or live with it).

---

## 2. Fixture design blindspots

### 2.1 [P0] Faker (option B) loses real chain topology

`@faker-js/faker` produces realistic names/CPFs but **no structural correctness**. Real cadeia dominial chains have these non-obvious invariants that random Faker data will not produce:

- `Documento.eh_inicio_matricula` Lancamentos must have `cartorio_origem` set (`:458`).
- The root `Documento` of a chain is the one with `data` closest to "now" tied to the `Imovel.matricula` (per `react-flow.md`).
- A `Lancamento` of type `inicio_matricula` always has one or more origins (`react-flow.md`).
- A `Lancamento` of type `averbacao` typically has no `documento_origem` (it's an annotation, not a transfer).
- A `Lancamento` of type `registro` typically has exactly one `documento_origem`.

**Action:** Faker handles the *data values* (names, dates, numbers), but a **chain topology generator** (not Faker) is what builds the graph. Split `scripts/fixtures/generate.ts` into two parts:
1. `chain-topology.ts` — builds the graph shape (deterministic, given seed). Controls how many Imóveis, how deep each chain, branching factor, fim-de-cadeia placements.
2. `field-filler.ts` — uses Faker to fill non-relationship fields (names, dates, areas, valores).

### 2.2 [P0] Required-fixture scenarios

The plan mentions `minimal.json`, `realistic.json`, `edge-cases.json` but doesn't enumerate which **chain shapes** must exist in fixtures:

- **Linear chain**: A → B → C → D (current). Standard.
- **Multi-origin**: A → B (where B's Lancamento has 2 origem docs: X and Y). Tests the multi-edge case in React Flow.
- **Branching convergence**: A → C, B → C (two origins for C, both real). Tests the DAG.
- **Fim de cadeia with classification**: A → B (with OrigemFimCadeia pointing to FimCadeia 'INCRA', classificação `origem_lidima`).
- **Averbação without origin**: B has a Lancamento of type `averbacao` with `documento_origem` null.
- **Documento with self-ref via Lancamento**: rare, but Django models allow it.
- **Multi-pessoa Lancamento**: a Lancamento with 3 transmitentes (LancamentoPessoa rows). Tests the M:N person/transaction relationship.
- **Multiple cartórios across states**: Documento.cri_origem in MT, cri_atual in MS (the cartório-migration case).
- **Empty/new imovel**: an Imovel with 0 Documentos (should be allowed but flagged as data quality issue).

**Action:** define each scenario as a deterministic generator function in `chain-topology.ts` and run all of them in the fixture bundle.

### 2.3 [P1] Cycle detection: allow or reject?

`react-flow.md` says "the chain is a DAG, not a strict tree." But the Django model allows `Lancamento.documento_origem` to point to **any** Documento, including one that transitively points back. So the data model permits cycles; the rendering library (React Flow) does not (it'll error or lay out weirdly).

**Action:** the fixture generator should produce **both**:
- Valid DAG fixtures (the happy path).
- Cycle fixtures (deliberately broken) so the validator can detect them and the React Flow export can either skip them or render a warning node.

This is the most important edge case to invest in.

### 2.4 [P1] CPF/CNPJ generation: format, not validity

Faker's Brazilian CPF generator produces **invalid** CPFs (it doesn't compute check digits). For fixtures, that's fine. But if any test ever validates a CPF check digit, it will fail. **Action:** add a small `validCpf()` helper in `field-filler.ts` that produces a check-digit-valid CPF, used by default; expose a `--invalid-cpf` flag for negative tests.

### 2.5 [P1] Date logic must be consistent

`Documento.data` (the document date) must be before any `Lancamento.data` on that Documento. `Lancamento.data_transacao` ≤ `Documento.data_cadastro` is not required but `data_cadastro` ≥ all related Lancamento dates is. **Action:** generate dates top-down: Documento.data first, then chain back from there.

### 2.6 [P2] `data_cadastro` audit columns

The Django models have `data_cadastro` on most entities but no `data_atualizacao` (except FimCadeia, TerraIndigenaReferencia). **Action:** add `updated_at` to every v2 table for free. SQLite timestamps work in milliseconds since epoch in Drizzle (`mode: "timestamp_ms"`) or as ISO strings. Pick one and stick to it.

### 2.7 [P2] The dump's IDs start at 4 (not 1) — fixtures should not

`data.cleaned.core.no-auth.no-unistr.sql` has `INSERT INTO dominial_documento VALUES(4,...)` — first id is 4. This is from auto-increment after deletes in the source DB. **Action:** fixtures should use 1-based PKs so the test data looks fresh and intentional.

---

## 3. React Flow rendering blindspots

### 3.1 [P0] `OrigemFimCadeia` belongs to Lancamento, not Documento — the current convention in `react-flow.md` is wrong

`react-flow.md` says: "Fim de cadeia → Synthetic leaf node, `id: fim-<documento.id>-<indice>`, edge from `doc-<documento.id>` to `fim-...`."

But `OrigemFimCadeia` (per `:494-520`) is a child of `Lancamento`, not `Documento`. The export must:
1. For each Documento, find all its Lancamentos.
2. For each Lancamento, find all its OrigemFimCadeia rows (where `fim_cadeia = true`).
3. For each such row, create a synthetic leaf node.

**Action:** the React Flow export script in §5.4 of the plan must walk `Documento → Lancamento → OrigemFimCadeia`, not `Documento → OrigemFimCadeia` directly. The current `react-flow.md` doc is misleading; update it.

### 3.2 [P0] `inicio_matricula` Lancamentos are the **source** of edges, not the target

`react-flow.md`: "inicio_matricula always has one or more origins and is the primary source of edges."

Reading this literally is wrong: `inicio_matricula` is the **start** of a chain, not a node that other documents originate from. The semantic should be: a `inicio_matricula` Lancamento's `documento_origem` field **does not apply** (or is null) — the chain starts at this Documento and the next Lancamento (of type `registro`) creates an edge FROM this Documento's "inicio" node TO the next Documento.

**Action:** clarify in `react-flow.md` and in the export script. The cleanest representation is: for `inicio_matricula` Lancamentos, **synthesize a virtual origin node** (or use the `FimCadeia` lookup if it links to a public entity like "INCRA"). Otherwise, the chain start has no parent node, and the BFS layout needs a special "level 0" handling.

### 3.3 [P0] Multi-origin edges: how does React Flow render N edges between two nodes?

If Documento C has Lancamento with `documento_origem` pointing to both A and B, the export creates 2 edges. React Flow renders these as **two parallel lines** by default. For dense graphs this gets visually noisy. **Action:** add a layout strategy decision:
- Option A: parallel edges (default, ugly at scale).
- Option B: a single edge with a label `N origens`.
- Option C: one edge, animated, with a count badge.
Pick one before designing fixtures. My recommendation: **B with N≥2 label**, and a unit test that asserts the label.

### 3.4 [P1] Node color is missing from the React Flow conventions

`react-flow.md` doesn't say how to color nodes. The Django `FimCadeia.get_cor_css()` method colors by classification (`origem_lidima` green, `sem_origem` red, `inconclusa` yellow). **Action:** the React Flow export should set `data.classificacao` per node and the React component should map to CSS classes. The current `react-flow.md` should add a "Styling" section.

### 3.5 [P1] `LancamentoPessoa` should be visible in node details, not graph topology

Multi-pessoa Lancamentos affect what's shown in the **node detail panel** (on click), not the graph layout. The current `react-flow.md` doesn't mention this. **Action:** define the `data` payload per node to include `transmitentes: string[]` and `adquirentes: string[]` (concatenated names) so the click-handler can show them.

### 3.6 [P1] Cycle handling in the layout algorithm

The BFS layout (`x = depth * 300`, `y = indexWithinDepth * 120`) assumes a DAG. If there's a cycle, BFS doesn't terminate. **Action:** in the export script, run a cycle detector first; either (a) error out, (b) break the cycle arbitrarily and log, (c) use an iterative DAG layout (e.g. dagre) that handles cycles by virtual nodes. **Recommend (a) for Phase 1** with a clear error message, and (c) as a follow-up.

### 3.7 [P2] `nivel_manual` is set but not used in the layout

`Documento.nivel_manual` (0-10) is a manual override for hierarchy. The BFS layout ignores it. **Action:** if `nivel_manual` is set, use it as the `x` coordinate instead of BFS depth. Document this clearly.

### 3.8 [P2] Cartório cross-state chains

A Documento's `cri_origem` is in MT and `cri_atual` is in MS (after a cartório migration). The graph doesn't currently show cartórios as nodes — they're attributes. **Action:** decide if cartórios are nodes (probably not in Phase 1) or if the `cri_atual` is just a badge on the node.

---

## 4. E2E test blindspots

### 4.1 [P0] The existing `graph.spec.ts` is a smoke test, not a real test

`packages/web/e2e/graph.spec.ts` (572 bytes) just asserts that "Parcel 451" text appears. No structural assertion, no visual snapshot. The plan is essentially "rewrite this from scratch." **Action:** delete it (or rename to `graph.smoke.spec.ts`) and create the new `schema-graph.spec.ts` with the full suite.

### 4.2 [P0] Visual snapshot diff is brittle

Playwright visual snapshot tests fail on:
- Font rendering differences across CI machines (especially headless).
- Sub-pixel anti-aliasing.
- React Flow's default node animation on first render.
- Browser version differences (Chromium updates in CI).

**Action:**
- Use a fixed font stack (e.g. `Inter` via the project; not system fonts).
- Use `animations: 'disabled'` in Playwright config for the visual test.
- Pin the Playwright Chromium version via `package.json#pnpm` or a Dockerfile.
- Allow per-pixel tolerance (e.g. `maxDiffPixels: 500` and `threshold: 0.2`).
- Re-record snapshots on a specific machine, document the procedure.

### 4.3 [P0] Where does the React Flow viewer get data?

The plan says "Playwright opens the React Flow viewer in `packages/web`." But the current `packages/web/src/index.ts` is a Vite/React entry; there's no `/graph` page implementation yet (just a route in the smoke test). **Action:** Phase 1 must include a minimal React Flow viewer component that reads from an injected JSON (not the API) so the test doesn't depend on the Hono API. Use Vite's `import.meta.glob` or a static asset for the JSON.

### 4.4 [P0] Tests must run against fixture-populated D1, not real D1

The plan says this. Make sure the Playwright config in `playwright.config.ts` (currently 386 bytes — basically empty) sets up:
- A `webServer` that starts `pnpm db:migrate:local && pnpm --filter @cadeia/api seed:fixtures`.
- A `globalSetup` that ensures the local D1 has the fixture data.
- A teardown that wipes the local D1 after the test run.

**Action:** flesh out `playwright.config.ts` to the level of `vitest.config.ts` (which exists). The current config is a stub.

### 4.5 [P1] Structural assertions need clear test data expectations

The plan says "structural assertions (fast): count of nodes, count of edges, expected root node, no duplicate ids, ..." — but it doesn't say **which counts**. Each fixture scenario should have a JSON sidecar with the expected counts:

```json
// fixtures/realistic.json + fixtures/realistic.expected.json
{ "scenario": "realistic", "imovelId": 1, "expectedNodes": 47, "expectedEdges": 46, "expectedRoots": ["doc-1"] }
```

**Action:** co-generate expected counts as part of the fixture generator output, then assert against them.

### 4.6 [P1] React Flow internals are not asserted in DOM

The current `graph.spec.ts` checks for `getByTestId("graph-shell")`. React Flow renders to a complex DOM (`.react-flow`, `.react-flow__renderer`, `.react-flow__nodes`, etc.). Structural assertions should use **React Flow's exposed selectors** or `data-id` attributes you set on nodes. **Action:** add `data-testid="doc-node-${id}"` and `data-testid="lanc-edge-${id}"` to the React Flow node/edge components so Playwright can query them directly.

### 4.7 [P2] No layout-vs-rendering separation in the test

A test that asserts the React Flow rendered correctly still depends on the layout algorithm. If you change the layout, the visual snapshot breaks. **Action:** add a separate "graph data integrity" test that asserts only on the **input** data (the JSON exported to React Flow), independent of React Flow itself. This is fast and stable.

---

## 5. D1 + Drizzle blindspots

### 5.1 [P0] Drizzle is configured for migrations only, not for queries

`packages/api/src/index.ts` uses `c.env.DB.prepare("SELECT ... FROM users WHERE email = ?").bind(...).first(...)` — raw SQL. Drizzle is only invoked for `db:generate` and `db:migrate:local`. **This is a significant design choice**: the schema you lock in here is **not the schema Drizzle runtime validates against**. It's the schema migrations are generated from. The Hono handlers will use raw SQL forever, OR a future PR will move to Drizzle queries.

**Action:** the plan should commit to one:
- **Option A:** Drizzle schema as the source of truth, raw SQL queries in handlers (current pattern). Drizzle only used for migrations. Validation happens via Zod.
- **Option B:** Move to Drizzle queries in this PR. Larger surface, but consistent.

**Recommend A for Phase 1** — keep the change scope to schema + fixtures + E2E. Move to Drizzle queries in a follow-up.

### 5.2 [P0] D1 FK enforcement must be opted into

D1 does not enforce foreign keys by default. The plan acknowledges this. **Action:** in the migration SQL, add `PRAGMA foreign_keys = ON;` at connection time, and document this in `D1_LOCAL_DEV.md`. But also: **the dump strip is already aware** (`docs/D1_IMPORT.md:3` says "Foreign keys are stripped to allow bulk import without constraint failures"). So:
- Strip FKs in the **import** script (already done).
- Re-enable FKs in the **runtime** via `PRAGMA foreign_keys = ON;` in the Worker entry.

### 5.3 [P0] D1 transaction limits

D1's max rows per transaction is documented (was 100k historically; higher now but batched import is still recommended). The current `data.cleaned.core.no-auth.no-unistr.sql` is 3.2 MB which is fine for one batch. **Action:** for the fixtures (much smaller), no batching needed. But the **future real-data import** will need batching — `scripts/d1_import_chunks.sh` already exists for that.

### 5.4 [P1] D1 indexes per table (32 limit)

D1 has a 32-index-per-table limit. The Django models are unlikely to exceed this for the main tables, but if you add many composite unique indexes, watch the count:
- `Documento`: probably 3-4 indexes (PK, `imovel`, `cartorio`, `unique(numero, cartorio)`).
- `Lancamento`: 6-7 indexes (PK, `documento`, `documento_origem`, `tipo`, `transmitente`, `adquirente`, `cartorio_origem`, `cartorio_transmissao`).
- That's 7-8 on Lancamento alone. **Action:** count indexes in the generated migration; document the headroom.

### 5.5 [P1] D1 time storage

D1 doesn't have a `DATETIME` type — it uses `TEXT` (ISO 8601) or `INTEGER` (Unix epoch). Drizzle's `mode: "timestamp"` uses seconds; `mode: "timestamp_ms"` uses milliseconds. The current `users` table uses `mode: "timestamp"` (seconds). **Action:** pick one and document it; recommend `timestamp_ms` for v2 (millisecond precision is free and avoids leap-second issues).

### 5.6 [P1] Decimal/numeric in SQLite

`valor_transacao` and `area` are decimal. SQLite has no native decimal type — they're stored as `TEXT` (Drizzle's `numeric`) or `REAL` (Drizzle's `real`). **Action:** use Drizzle's `real` for these (loss of precision is acceptable for property values; alternative is to store as text in cents/square-centimeters). **Recommend `real`** for now.

### 5.7 [P2] D1 generated columns and virtual columns

D1 supports generated columns (e.g. `full_name TEXT GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED`). Useful for `get_sigla_formatada()` (Imovel's "M{number}" / "T{number}") and `FimCadeia.get_cor_css()` (color from classification). **Action:** add a few generated columns to v2 to push logic into the data layer. The `FimCadeia.color` is the highest-value one.

### 5.8 [P2] Drizzle migrations dir mismatch

`drizzle.config.ts` sets `out: "./drizzle/migrations"`, but `wrangler.toml` shows `migrations_dir = "drizzle/migrations"`. These match. ✓ (Good — flagging because drift here is silent and painful.)

### 5.9 [P2] `cri_atual` vs `cri_origem` vs `cartorio` on `Documento` — three cartório FKs

The Django model has `Documento.cartorio` (the main cartório), `Documento.cri_atual` (current CRI for the property), and `Documento.cri_origem` (CRI of the auto-created origin document). **Question:** is `Documento.cartorio` always equal to `Documento.cri_atual`? If so, drop one. The Django doc says "Referenced by `Documento.cartorio`, `Documento.cri_atual`, `Documento.cri_origem`" (`:281`) but doesn't clarify the semantics. **Action:** ask the team; if redundant, drop `Documento.cartorio` (since `cri_atual` is the meaningful one).

---

## 6. Process blindspots

### 6.1 [P0] "Single PR" for "author 13 tables from scratch" is not reviewable

A PR that introduces 13 new tables, ~100 columns, composite indexes, fixture generators, the React Flow export script, the Playwright E2E suite, and fixture data will be **thousands of lines**. Reviewers will skim; bugs will land.

**Action:** even within a "single PR" mandate, **structure the PR as a stack of logical commits** that can be reviewed in order:
1. `chore(deps): add @faker-js/faker, dagre, d3-*` (deps)
2. `feat(db): add Drizzle schema for reference tables (TIs, TerraIndigenaReferencia, DocumentoTipo, LancamentoTipo, FimCadeia, AlteracoesTipo, RegistroTipo, AverbacoesTipo, Cartorios, ImportacaoCartorios)`
3. `feat(db): add Drizzle schema for Pessoas, Imovel`
4. `feat(db): add Drizzle schema for Documento, Lancamento, LancamentoPessoa, OrigemFimCadeia`
5. `feat(db): add Drizzle schema for TIs_Imovel, Alteracoes, DocumentoImportado`
6. `feat(fixtures): add topology generator and field filler`
7. `feat(fixtures): generate minimal + realistic + edge-cases bundles`
8. `feat(scripts): add SQLite import validator and React Flow export`
9. `test(e2e): add structural + visual snapshot tests for schema graph`
10. `docs: regenerate ERD and update MIGRATION_GUIDE`

Same PR, ordered commits, each independently buildable. The reviewer can spot-check.

### 6.2 [P0] No way to validate the schema against the legacy data

The plan says "make sure we can migrate current db to new schema" but doesn't define how to **prove it**. The dump is data-only and clean of FKs, so it loads easily — but the data could fail the new schema's NOT NULL constraints, type mismatches, etc.

**Action:** add `scripts/migration/legacy-fit.ts` that:
1. Loads the cleaned SQL dump into a fresh SQLite.
2. Applies the new Drizzle schema to the same SQLite.
3. Compares row counts per table.
4. For each row, validates the new schema's NOT NULLs, types, etc.
5. Outputs a fit report: `✓ 47 tables match`, `⚠ 12 rows fail tipo_alteracao NOT NULL`, etc.

This is **the** deliverable that proves the new schema can absorb the legacy data.

### 6.3 [P1] No rollback strategy

A single PR that "locks" the schema is, by definition, hard to revert. **Action:** the PR must be marked as a **draft** until both:
- All E2E tests pass.
- The legacy-fit report shows ≥99% row match (allowing for known cleanup items like cartorio_transacao).

If it can't meet that bar, **split the PR**.

### 6.4 [P1] Worktree/branch strategy unclear

The plan says "worktree per change → PR into v2" but for a single epic PR, the worktree should be branched from `v2` HEAD. The PR target is `v2`. **Action:** name the worktree `schema-v2-lockin` or similar; merge to `v2` directly (no separate branch in v2 first).

### 6.5 [P1] The ERD `.png` is rendered from the **draft** mermaid

`docs/ERD_CADEIA_DOMINIAL.png` is rendered from the current `.md` mermaid. Once the schema changes, this needs regeneration. **Action:** commit the `.png` only after the `.md` is final, and include a CI step that re-renders the PNG on every change to the mermaid. Tool: `mmdc` (`@mermaid-js/mermaid-cli`).

### 6.6 [P2] No migration timeline for the auth table

The plan says "auth out of scope" but `users` is in the current Drizzle schema. The schema-lock PR will **not** touch `users` (good), but anyone reading the schema will wonder why `users` is in there. **Action:** add a one-line comment to `schema.ts` that the `users` table is owned by PRD-005 (auth) and is out of scope for this PR.

### 6.7 [P2] The dump file is in the repo working dir (not gitignored by path)

`.gitignore` excludes `*.sql`, but the file is at `<project-root>/data.cleaned.core.no-auth.no-unistr.sql` (the project root). **Action:** double-check with `git status` that it shows as ignored. If `git status` shows it under "untracked," add a more specific rule.

---

## 7. Things that are FINE (explicit no-change)

- **React Flow conventions for node IDs** (`doc-<id>`, `lanc-<id>`, `fim-...`): keep as-is. Stable IDs make tests reproducible.
- **The single-package `@cadeia/web` + `@cadeia/api` split**: keep. Clean separation; no need to merge.
- **Playwright as the E2E runner**: keep. Already configured at `package.json` and `playwright.config.ts` (even if the config is sparse).
- **Drizzle for migrations + raw SQL for queries**: keep for Phase 1 (see §5.1).
- **`pnpm` + `turbo` + `wrangler` toolchain**: keep. Standard for the Cloudflare Workers + TS monorepo.
- **D1 quirks handling** (FKs stripped on import, `unistr` converted, `sqlite_sequence` removed): the existing `docs/D1_IMPORT.md` is correct. The new fixtures won't need any of this — they're clean.
- **`dominial_` prefix decision** (drop it): fine, see §1.8.
- **The migration from raw SQL to Drizzle queries**: keep out of Phase 1. Don't expand scope.
- **PRDs and the .codex/ skills system**: keep. The schema PR is a standard feature workstream.
- **The "Single PR" mandate**: keep, but structure with ordered commits (see §6.1).

---

## 8. Prioritized action list

### P0 — must do before code is written

1. **Re-derive the ERD from the Django source of truth.** `docs/legacy-django/03-database-models.md` is canonical. The mermaid in `docs/ERD_CADEIA_DOMINIAL.md` has 9 entity/column gaps. Don't lock the schema on a drifted ERD.
2. **Decide FK strategy at runtime**: strip FKs in the dump-import path (already done), enable `PRAGMA foreign_keys = ON` in the Worker. Document in `D1_LOCAL_DEV.md`.
3. **Author the chain-topology generator separately from the field-filler.** Faker alone won't produce valid cadeia shapes. Topology generator controls shape; field-filler handles values.
4. **Define the fixture scenario list** (linear, multi-origin, branching convergence, fim-de-cadeia, averbação-without-origin, multi-pessoa, multi-state, self-ref, cycle). Each as a deterministic function.
5. **Decide on `cartorio_transacao`**: keep or drop? The Django doc says it's legacy/deprecated. Recommend drop.
6. **Add composite unique indexes** for `(numero, cartorio)` on `Documento`, `(lancamento, pessoa, tipo)` on `LancamentoPessoa`, `(lancamento, indice_origem)` on `OrigemFimCadeia`.
7. **Update `react-flow.md`**: the `OrigemFimCadeia` lookup must go `Documento → Lancamento → OrigemFimCadeia`, not `Documento → OrigemFimCadeia`. The `inicio_matricula` Lancamento is the chain start, not a node that other docs originate from.
8. **Build the `legacy-fit` validator script** before merging. The new schema must demonstrably absorb the legacy dump.
9. **Structure the PR with 10 ordered commits** so reviewers can spot-check.
10. **Rewrite `playwright.config.ts`** with `webServer` + `globalSetup` for the fixture-populated D1.

### P1 — should do, but won't block a draft PR

11. **Add `updated_at` to every table** for audit.
12. **Pick one timestamp mode** (`timestamp_ms`) and document it.
13. **Pick one decimal strategy** (`real`) and document it.
14. **Add `data-testid` attributes** to React Flow nodes/edges for stable Playwright selectors.
15. **Generate expected-counts JSON sidecars** per fixture scenario.
16. **Use `nivel_manual` as the x-coordinate** when set, fall back to BFS depth.
17. **Define multi-origin edge rendering** (recommend: single edge with `N origens` label when N≥2).
18. **Add visual snapshot tolerance config** (`maxDiffPixels`, `threshold`) and pin Playwright Chromium.
19. **Drop `cartorio_transacao`** from the v2 schema (write a data-migration comment for the nulling step).
20. **Resolve `Documento.cartorio` vs `Documento.cri_atual` redundancy** with the team.

### P2 — nice-to-have, follow-up PRs

21. **Use D1 generated columns** for `FimCadeia.color` and `Imovel.sigla`.
22. **Add a cycle-handling follow-up**: virtual-node layout via dagre.
23. **Move from Drizzle-migrations-only to Drizzle queries** in handlers (a separate refactor PR).
24. **Add a CI step** that re-renders the ERD PNG on every change to the mermaid source.
25. **Document `FimCadeia` color logic** in a "Styling" section of `react-flow.md`.
26. **Add a comment to `schema.ts`** that `users` is owned by PRD-005 and out of scope.
27. **Add a `validCpf()` helper** for fixture generation (check-digit-correct).

---

## Summary

The plan is **directionally correct** but **underestimates the work** (the current Drizzle schema is empty for this domain; the ERD has substantial drift from the Django source of truth; the React Flow export logic is incomplete). The biggest risks:

1. The ERD is wrong in 9+ places — **fix before writing code**.
2. Faker alone won't produce valid cadeia shapes — **separate topology from field-filling**.
3. `OrigemFimCadeia` is per-Lancamento, not per-Documento — **the React Flow export in `react-flow.md` is wrong**.
4. A single 1000+ line PR is unreviewable — **structure with ordered commits**.
5. No legacy-fit validation — **add the script that proves the new schema absorbs the old data**.

If you fix those five, the rest is execution.
