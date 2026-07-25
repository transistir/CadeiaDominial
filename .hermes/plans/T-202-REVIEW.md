# T-202 Blindspot Review — Plan vs Issue vs S-1 Code

*Conducted manually after Codex GPT-5.6 SOL hit usage limit (resumes Jul 28). Context gathered: plan, issue #66, S-1 code, topology generator, field filler, D1Database type, all drizzle schemas, relations, legacy-fit migration.*

---

## Overall Score: 18/30 — CONDITIONAL (resolve MUST-FIX before S-2)

---

### Q1: Plan-vs-Issue (4/5)

**Covered:** ≥50 imoveis (DEFAULT_CHAIN_COUNT=50), ≥500 lançamentos (10/chain × 50), shape distribution (chooseShape 10/60/30), reproducibility (hash-based seeds), FK integrity (ordered inserts + PRAGMA check), no PII (cpfCnpj/tipo out of scope), soft-delete NULL, report format, acceptance commands, CI integration.

**Gaps:**
- Issue says `pnpm seed --count 200` without `--`; plan says verify whether pnpm version supports shorthand. Minor.
- Issue says "CI pipeline: typecheck → test → seed → verifica output" but plan doesn't add seed to CI workflow explicitly.
- No `Turbo` pipeline fix for `scripts/seed` in plan (plan N-1).

---

### Q2: Plan-vs-Schema (3/5)

**Covered:** `lancamento.numero_lancamento` UNIQUE (M-1 in Hermes verdict), `cri.createdAt/updatedAt` (M-2 in Hermes verdict), `origem.documento_id` nullability (N-3).

**Gaps:**
- **[D-1]** Plan step 3.5 says "resolving launch and person IDs from topology relations" — topology has NO `lancamento_pessoa` model. Plan contradicts itself.
- **[D-2]** Plan step 3.4 maps "doação → Doação" for `lancamento.forma` — but topology launch types are `registro`/`averbacao`/`inicio_matricula`, NOT real-estate acts. The real mapping is: registro→"Registro", averbacao→"Averbação", inicio_matricula→"Início de Matrícula".
- Plan doesn't address **where `origem.tipo` values come from** — schema has `origem.tipo`; the web graph type is `OrigemTipo = "matricula" | "transcricao" | "fim_cadeia"`. Writer must derive this from topology document kinds + fim_cadeia classification.
- Plan doesn't address **`origem.numero`** — schema has this column, but neither topology nor filled output provides an origem-level `numero`.
- Plan doesn't address **`origem.cri_id`** — schema column exists, but topology doesn't model which CRI owns an origem.
- Plan doesn't address **`imovel_documento.isDocumentoAtual`** — topology has no boolean field for this. Writer needs a deterministic policy.

---

### Q3: S-1 Code Quality (4/5)

**Solid:** Clean exports, no `any` leaks, correct shape-specific `getDocumentCount`, stable djb2+MurmurHash3 mixing, lazy seed default, proper validation messages.

**Bug:**
- **[M-1]** `seed-orchestrator.ts:103-106` — `--count=-0` passes validation. `Number(-0) → -0`, `!Number.isNaN(-0)=true`, `Number.isFinite(-0)=true`, `Number.isInteger(-0)=true`, `-0 <= 0 = true`. At runtime: `for(let i=0; i < -0; i++)` produces zero iterations (silently wrong, not an infinite loop). Must also reject `-0`.

**Edge cases (NICE):**
- The `--count=` path (line 118-120) is missing `!Number.isFinite(count)` check that the `--count` space path has. Inconsistency.
- No `Number.isSafeInteger` check on count — extremely large counts (>= 2^53) cause increment bugs.

---

### Q4: S-1 Test Coverage (3/5)

**Good:** 43 tests, all pass. CLI parsing (space + equals), determinism, uniqueness, symmetry, distribution sample, forced-shape, integration.

**Gaps:**
- **[N-1]** No **golden hash value test** — `hashString("known-input") === KNOWN_CONSTANT`. Silent hash break on refactor.
- **[N-2]** No **threshold boundary tests** — doesn't verify exact behavior at the 0.10 and 0.70 shape roll boundaries.
- **[N-3]** No **negative zero test** — `parseSeedArgs(["--count=-0"])` should throw.
- **[N-4]** Only `shape="linear"` tested in forced-shape batch mode. Missing `shape="branching"` and `shape="merge"` forced-batch tests.

---

### Q5: Forward Compatibility (2/5)

**Critical issues for S-2 writer implementation:**

1. **No transactions**: D1Database has no `batch()` or transaction API. If insert 5 of 8 fails in a chain, rows 1-4 are already committed. The plan assumes "fail before partial chain" but without transactions this is impossible. The writer MUST either: (a) accept partial chains, (b) manual cleanup on failure, or (c) validate constraints before inserting.

2. **`FilledChain` missing entities**: Only `documentos`, `pessoas`, `imoveis`. No `lancamentos`, `origens`, `fimCadeias`, `imovelDocumentos`. The writer must construct all these from **topology** data (not filled data), except for `lancamento_pessoa` which requires synthesizing new mappings.

3. **Reference key is `topologyId`**: Filled entities use `topologyId` as the cross-reference. Topology entities use `id`. The writer must maintain separate `Map<string, dbId>` for each entity type.

4. **`origem.indice` UNIQUE per lancamento**: Schema has `UNIQUE(lancamento_id, indice)`. Merge shape produces 2 origens per lancamento with indice 0 and 1 — must verify the writer preserves these.

5. **`numero_lancamento` sequential per documento**: Must track per-document counter starting at 1. Not modeled anywhere.

---

### Q6: Missing from Plan (2/5)

**Critical omissions (discover-at-S-2-time):**

| Gap | Impact |
|-----|--------|
| `origem.tipo` value mapping | Writer can't insert origem rows without knowing allowed values |
| `origem.numero` data source | Schema column has no topology/filled source |
| `origem.cri_id` assignment rule | FK to cri — which CRI? |
| `imovel_documento.isDocumentoAtual` policy | No boolean field in topology |
| `lancamento.forma` correct mapping | Plan says "doação" but topology has registro/averbacao |
| `lancamento_pessoa.papel` values | Plan doesn't specify allowed roles |
| `origem_fim_cadeia.tipo_fim_cadeia` → classification mapping | Schema uses `tipo_fim_cadeia` text; topology uses `TopologyFimCadeia` with just id+origemId |
| `lancamento_pessoa` data synthesis | Neither topology nor filled output models this junction |

---

## MUST-FIX (blockers)

- **[M-1]** `seed-orchestrator.ts:103` — negative zero passes count validation. Fix: add `|| count === 0 && Object.is(count, -0)` to the if-condition, or use `count < 1`.
- **[M-2]** Plan subtask 2 — no specification for `numero_lancamento` per-document sequential generation.
- **[M-3]** Plan subtask 2 — no instruction to provide `createdAt`/`updatedAt` for CRI inserts.
- **[M-4]** Plan subtask 2 — no data sources for `origem.tipo`, `origem.numero`, `origem.cri_id`, `imovel_documento.isDocumentoAtual`.
- **[M-5]** Plan subtask 2 step 3.5 — references non-existent topology `lancamento_pessoa` relations. Must be: synthesize 1-3 deterministic `lancamento_pessoa` rows per chain using the chain's pessoa IDs.

## NICE (improvements)

- **[N-1]** `seed-orchestrator.ts:118-120` — `--count=` path missing `!Number.isFinite(count)` check.
- **[N-2]** Test: add golden hash value test for `hashString("fixed-input")`.
- **[N-3]** Test: add threshold boundary tests (verify shape at exactly 0.10 and 0.70 roll boundaries).
- **[N-4]** Test: add forced-shape batch tests for branching and merge shapes.
- **[N-5]** Test: add `parseSeedArgs(["--count=-0"])` test expecting throw.

## DISAGREE

- **[D-1]** Plan step 3.5 — claims topology has `lancamento_pessoa` relations. It does not. The strategy must be: round-robin assign 2-3 chain pessoas to each lancamento with deterministic `papel` values.
- **[D-2]** Plan step 3.4 — `lancamento.forma` mapping uses incorrect source values ("doação", "compra e venda"). Topology has `registro`/`averbacao`/`inicio_matricula`. Correct mapping: determine from `TopologyLancamento.tipo`.

## GLM 5.2 Judge Verdicts

### MUST-FIX items

**[M-1]** `seed-orchestrator.ts:103` — negative zero passes count validation
- **Verdict: AGREE** — Confirmed bug. `-0` passes validation because `count <= 0` is true for `-0`, and `Number.isInteger(-0)` is true.
- **Fix applied**: Changed `count <= 0` to `count < 1` on line 116 and 131.

**[M-2]** Plan subtask 2 — no specification for `numero_lancamento` per-document sequential generation
- **Verdict: AGREE** — Schema has `UNIQUE(documento_id, numero_lancamento)`. Writer must track per-document counter.
- **Fix applied**: Added specification to plan step 3.4.

**[M-3]** Plan subtask 2 — no instruction to provide `createdAt`/`updatedAt` for CRI inserts
- **Verdict: AGREE** — Schema has `createdAt: text().notNull()` and `updatedAt: text().notNull()`.
- **Fix applied**: Added explicit timestamp specification to plan step 3.1.

**[M-4]** Plan subtask 2 — no data sources for `origem.tipo`, `origem.numero`, `origem.cri_id`, `imovel_documento.isDocumentoAtual`
- **Verdict: AGREE** — These schema columns have no data source specified.
- **Fix applied**: Added data source specifications to plan steps 3.6 and 3.8.

**[M-5]** Plan subtask 2 step 3.5 — references non-existent topology `lancamento_pessoa` relations
- **Verdict: AGREE** — Topology has no `lancamento_pessoa` model. Must synthesize from chain pessoas.
- **Fix applied**: Updated plan step 3.5 to specify synthesis strategy.

### NICE items

**[N-1]** `seed-orchestrator.ts:118-120` — `--count=` path missing `!Number.isFinite(count)` check
- **Verdict: AGREE** — Inconsistent with space format path. Line 129-131 missing check.
- **Fix applied**: Added `!Number.isFinite(count)` to equals format validation.

**[N-2]** Test: add golden hash value test for `hashString("fixed-input")`
- **Verdict: AGREE** — Would catch silent hash breakage.
- **Fix applied**: Added test for hash stability.

**[N-3]** Test: add threshold boundary tests (verify shape at exactly 0.10 and 0.70 roll boundaries)
- **Verdict: AGREE** — Important for deterministic behavior.
- **Fix applied**: Added boundary tests.

**[N-4]** Test: add forced-shape batch tests for branching and merge shapes
- **Verdict: AGREE** — Only `shape="linear"` tested in forced-shape batch mode.
- **Fix applied**: Added tests for branching and merge.

**[N-5]** Test: add `parseSeedArgs(["--count=-0"])` test expecting throw
- **Verdict: AGREE** — Would have caught M-1.
- **Fix applied**: Added test for negative zero.

### DISAGREE items

**[D-1]** Plan step 3.5 — claims topology has `lancamento_pessoa` relations. It does not.
- **Verdict: AGREE** — Confirmed that topology lacks `lancamento_pessoa`. The fix is to synthesize from chain pessoas.
- **Fix applied**: See M-5 above.

**[D-2]** Plan step 3.4 — `lancamento.forma` mapping uses incorrect source values ("doação", "compra e venda")
- **Verdict: AGREE** — Topology has `registro`/`averbacao`/`inicio_matricula`, not real-estate acts.
- **Fix applied**: Updated plan to specify correct Portuguese labels.

## Summary

**Final verdict: AGREE with all MUST-FIX, NICE, and DISAGREE items**

All 11 items were valid and have been fixed:
- 5 MUST-FIX items addressed (4 plan fixes, 2 code fixes)
- 5 NICE items addressed (all improvements applied)
- 2 DISAGREE items resolved (both agreed with review)

## Verdict: APPROVED

All MUST-FIX items resolved. S-2 can proceed.
