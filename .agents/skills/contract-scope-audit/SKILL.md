---
name: contract-scope-audit
description: Use when an issue asks to "validate", "audit", or "check compliance" of an existing feature against a contract clause, TDR (Termo de Referência), regulation, or scope-restriction. Distinct from blindspot-review-protocol (which reviews spec/plan against implementation) — this skill audits IMPLEMENTATION against CONTRACT/SCOPE CONSTRAINTS. Triggers on issues labeled "validar", "homologação", "conformidade TDR", "contract compliance", or any "make sure we don't violate clause X" request. Covers CadeiaDominial's TDR item 1.1(a) (no parecer jurídico, no validação registral), GDPR/LGPD, and any regulatory "what the system must NOT do" rule.
license: MIT
metadata:
  hermes:
    tags: [audit, contract, tdr, compliance, scope-restriction, regulatory]
    related_skills: [blindspot-review-protocol, codex-impl-cycle, requesting-code-review]
---

# Contract-scope-audit

## What this is

A protocol for **auditing an existing implementation against a contract clause / TDR / regulation / scope-restriction** that defines what the system MAY or MAY NOT do or say.

Distinct from `blindspot-review-protocol`, which compares spec/plan against source-of-truth. This skill compares **existing code/UI/copy** against **external scope constraints** (contract clauses, regulatory language, prohibited behaviors). The audit is **forward-looking in scope, backward-looking in code**: the code already exists; the question is whether it stays within the permitted scope.

The core move: **inventory every user-facing artifact (UI labels, tooltips, PDF templates, model defaults, JS fallbacks) and check each against the scope constraints**. The most common blindspot in regulated systems is that *individual pieces* look fine in isolation but collectively cross the line.

## When to trigger

Use this when ANY of these are true:
- An issue asks to "validate" / "audit" / "check compliance" of an existing feature against a contract clause
- The contract/TDR says "must NOT do X" or "without Y" (negative constraints)
- The system emits text visible to end users (tooltips, PDFs, badges, error messages, default values)
- A regulatory regime restricts system output (LGPD, GDPR, financial disclaimers, medical disclaimers)
- The user has invested in the implementation and wants a sanity check from someone with fresh eyes who will challenge "but is this within scope?"

Do NOT use this for:
- Pure code review (use `requesting-code-review` or PR review)
- Spec-vs-implementation drift (use `blindspot-review-protocol`)
- Performance, security, or correctness audits (use domain-specific skills)
- Implementation work (this skill produces a written audit, not code changes)

## The 6-pillar audit structure

A contract-scope audit checks **6 distinct pillars**. Each can independently violate the contract. The audit must cover all 6.

### Pillar 1: LANGUAGE / COPY audit

**Check:** every user-facing string (label, option, button, tooltip, error, PDF text, model `verbose_name`).

**For each string, ask:**
- Does it contain scope-restricted language (jurídico, validação, certidão, parecer, regular, irregular, válido, nulo, legítimo, perfeito)?
- Does it make a value judgment the system cannot justify ("lídima" = legitimate, "perfect" = complete, "invalid" = voided)?
- Does it imply legal effect the system cannot deliver?

**The label-rename vs enum-rename rule (Luandro pattern):**
- The **internal Python/DB enum string** (e.g. `origem_lidima`) often MUST be preserved to avoid migrations + data loss.
- Only the **user-facing label** (the second tuple element in `choices`, the rendered text) needs to change.
- This means: `('origem_lidima', 'Imóvel com Origem Lídima')` → `('origem_lidima', 'Imóvel com Origem Identificada')` — zero migrations, full semantic fix.
- Always grep the enum STRING value separately from the label TEXT — they're in different places and only the label needs updating.

**Tools:**
```bash
# Find every label that could violate the constraint
rg -nE "(<forbidden_term_1>|<forbidden_term_2>)" --glob '*.{html,py,js,css,md}'
# Find every internal enum value (these are protected)
rg -nE "(\<enum_value_1\>|\<enum_value_2\>)" dominial/models/
```

**Severity model:**
- **VIOLAÇÃO** — explicit legal/regulatory claim the system cannot substantiate
- **ATENÇÃO** — language with strong legal implication but not a direct claim
- **CONFORME** — neutral, descriptive, or explicitly disclaimed

### Pillar 2: VISUAL SEMANTICS audit (color/icon glyph)

**Check:** every color and icon used in the UI.

**For each visual element, ask:**
- Does the color carry a value judgment (green=approved, red=rejected, yellow=warning)?
- Does the icon imply state (✓ approved, ✗ rejected, ⚠ warning)?
- For features that are "organization-only" not "judgment-making", the visual should be **neutral or descriptive**, not evaluative.

**Pattern:** if a system shows "Origem Lídima" in green and "Sem Origem" in red, the user reads this as "approved" vs "rejected" even when the system only organizes data. Replace green with **neutral gray** (`#6c757d` family) for descriptive states; reserve green/red for actual pass/fail.

**Tool:**
```bash
# Find color/icon decisions paired with potentially-scope-restricted labels
rg -nE "(#28a745|#dc3545|#ffc107|🟢|🔴|🟡)" static/**/*.js static/**/*.css
# Cross-reference with the labels they decorate
```

**Output format per finding:** label + color + glyph + (Pillar 1) counterpart text.

### Pillar 3: MODEL DEFAULTS audit

**Check:** every model `default=...` value, especially for enum fields where the default might encode a positive judgment.

**Pattern:** if a model has `classificacao = CharField(choices=[...], default='origem_lidima')`, the default encodes a positive claim about every new record. The audit must ask: **does the default need to be set explicitly by the user, not assumed by the system?**

**Tool:**
```bash
# Find every default that encodes a positive/enabled value
rg -nE "default=['\"]([a-z_]+)" dominial/models/ dominial/migrations/
```

**Fix recipe:** change `default='origem_lidima'` to either `default=None` (nullable) or remove the default entirely (forces selection). Backfill considerations: in production, existing rows already have a value, so removing the default only affects new records. Document this clearly in the commit.

### Pillar 4: FALLBACK / DEFAULT UI audit

**Check:** every `else` branch, every "if type not recognized" handler, every "show this when value is missing" pattern.

**Pattern:** the most common violation is **a fallback that ASSIGNS a value** when the system should **acknowledge missing data**:
- `if (tipo === 'A') { ... } else { tipo = "Sem Origem" }` — assigns a negative value to unknown input
- `if (classificacao === 'A') { ... } else { classificacao = "inconclusa" }` — assumes incomplete
- `if (cartorio is None) { cartorio = "Desconhecido" }` — labels missing data as unknown

The correct fallback: **`tipo = "Tipo não classificado"` (descriptive, not a value judgment)** or **`return null` and let the renderer show "—"**.

**Tool:**
```bash
# Find all "else" branches in JS and Python that assign a default
rg -nE "else\s*\{?\s*[a-z_]+\s*=" static/**/*.js dominial/
```

### Pillar 5: MANDATORY DISCLAIMER audit

**Check:** does every place that shows regulated/scope-restricted information have a visible disclaimer?

**Pattern:** the contract/TDR usually allows the feature if accompanied by a disclaimer. The audit must verify:
- A disclaimer is present in every user-facing surface (UI, PDF, tooltip, email)
- The disclaimer is **visible, not hidden** (no `display:none`, no `aria-hidden`)
- The disclaimer text is **identical across surfaces** (consistency matters legally)
- The disclaimer comes BEFORE the data, not after

**Standard disclaimer template (Portuguese, CadeiaDominial case):**
```
⚠️ Atenção: Visualização organizada exclusivamente a partir dos dados cadastrados.
Não constitui parecer jurídico nem validação registral.
```

**Tool:**
```bash
# Find all surfaces that show fim-de-cadeia data
rg -nE "(Fim de Cadeia|is_fim_cadeia|classificacao_fim_cadeia)" templates/ static/ dominial/
# For each, verify a disclaimer is present
```

**Output format per surface:** file:line + disclaimer text + visibility (yes/hidden) + before/after data (correct/wrong).

### Pillar 6: GENERATIVE/INFERENCE audit

**Check:** does the system **infer or generate** statements that cross the scope line?

**Pattern:** the system might show a tooltip like "Último titular registrado" — that's a **descriptive** statement ("the last registered holder, per the documents") and is fine. But "Origem Lídima" is an **evaluative** statement ("the origin is legitimate") that requires a legal review the system cannot perform.

**Detection rule:** if the system could not defend the statement in court (without a lawyer), it shouldn't make the statement.

**Tool:** for each user-facing string, ask: "Can the system defend this claim in court with the data it has?" If no, the string must be either:
- Reworded to be descriptive only
- Removed entirely
- Prefixed by a mandatory disclaimer (Pillar 5)

## The audit output format

```markdown
# Contract-scope audit: <feature/issue>

## Source constraints
<quote the exact contract/TDR clauses being audited against, e.g. "TDR item 1.1(a): ... sem emissão de parecer jurídico ou validação registral">

## Conformance verdict
CONFORMIDADE: [APROVADO | NECESSITA AJUSTES]
Headline: N findings (X VIOLAÇÃO / Y ATENÇÃO / Z CONFORME)

## Findings (per pillar)

### Pillar 1 — Language / Copy
- ⚠️ **ATENÇÃO** — `file.html:42` — "Imóvel com Origem Lídima" — "Lídima" implica legitimidade. Sugestão: "Origem Identificada".
- ✅ **CONFORME** — `file.html:50` — "Fim de Cadeia" — descritivo, sem juízo de valor.

### Pillar 2 — Visual Semantics
- ⚠️ **ATENÇÃO** — `cadeia_dominial_d3.js:929` — verde para "Origem Lídima" cria leitura aprovado/reprovado. Sugestão: cor neutra (#6c757d).

### Pillar 3 — Model Defaults
- ⚠️ **ATENÇÃO** — `lancamento_models.py:306` — `default='origem_lidima'` codifica conclusão positiva. Sugestão: `default=None` (nullable).

### Pillar 4 — Fallback UI
- ⚠️ **ATENÇÃO** — `cadeia_dominial_d3.js:980` — fallback "Sem Origem" rotula dado ausente como negativo. Sugestão: "Tipo não classificado".

### Pillar 5 — Mandatory Disclaimer
- ❌ **VIOLAÇÃO** — Nenhuma ressalva em `cadeia_dominial_pdf.html`, `cadeia_completa_pdf.html`, nem nos tooltips. Adicionar disclaimer visível em todas as 3 superfícies.

### Pillar 6 — Generative/Inference
- (nenhum achado)

## Suggested fix plan
5 commits, ordem recomendada:
1. `fix(label):` — trocar rótulos user-facing (preservar enum interno)
2. `feat(ui):` — adicionar ressalva nas 3 superfícies
3. `fix(visual):` — cor neutra para estados descritivos
4. `fix(fallback):` — "Tipo não classificado" em vez de "Sem Origem"
5. `fix(model):` — remover default positivo
```

## The fix-as-5-separate-commits pattern

When the audit returns "NECESSITA AJUSTES", the fix is almost always a 5-commit PR (one per pillar + intro). **Keep commits atomic and reviewable**:

| Commit | What it touches | Verification |
|---|---|---|
| 1. `fix(label):` | User-facing text only (preserve internal enum strings) | `rg <old_label>` returns 0 hits in user-facing files |
| 2. `feat(ui):` | Add disclaimer to 3+ surfaces | `rg <disclaimer_text>` returns N hits = number of surfaces |
| 3. `fix(visual):` | Replace semantic color/icon with neutral | visual regression check |
| 4. `fix(fallback):` | Replace "Sem X" fallback with "Não classificado" | `rg "Sem Origem"` returns 0 in fallback branches |
| 5. `fix(model):` | Remove default | migration NOT required (just nullable change) |

**Why 5 commits, not 1?** Each commit is independently reviewable. A reviewer can see "labels fixed" without skimming through color/UI changes. Audit-friendly. Rollback-friendly.

**Why label-rename preserves the enum?** The internal Python string (`origem_lidima`) is a stable identifier. Renaming it would require a migration to rename the DB column values. The label is a separate concept: the visible text the user reads. Always preserve the identifier; only change the display text.

## The audit-then-fix flow (5 steps)

```bash
# 1. Audit (read-only, Codex GPT-5.6 xhigh or equivalent)
cat /tmp/audit-prompt.md | codex exec -m gpt-5.6-sol \
  -c model_reasoning_effort=xhigh --sandbox read-only - \
  2>&1 | tee /tmp/audit.log

# 2. Review the audit (form your own verdict — see codex-impl-cycle Pitfall #12)

# 3. Fix (Codex workspace-write, with the 5-commit recipe)
cd /root/dev/<repo>
git worktree add -b feature/issue-N-<short> ../worktrees/<short> origin/<base>
cd ../worktrees/<short>
cat /tmp/fix-prompt.md | codex exec --dangerously-bypass-approvals-and-sandbox \
  --sandbox workspace-write -m gpt-5.6-sol -c model_reasoning_effort=high -

# 4. Review the fix (Codex xhigh, read-only)
cat /tmp/review-prompt.md /tmp/prN-diff.txt | codex exec -m gpt-5.6-sol \
  -c model_reasoning_effort=xhigh --sandbox read-only -

# 5. Open PR (do not merge — wait for user)
git push origin feature/issue-N-<short>
gh pr create --base <base> --head feature/issue-N-<short> --title "..." --body "..."
```

## Common pitfalls in contract-scope audits

1. **Treating the contract as a wishlist, not a constraint** — the TDR/contract clauses are the binding spec. "But it would be more useful to show X" is not an argument; if X violates the contract, X is out of scope.
2. **Confusing the user with two different disclaimers** — if the disclaimer in the D3 tooltip says one thing and the PDF disclaimer says another, you've created two compliance surfaces. They MUST be byte-identical (or at least semantically equivalent).
3. **Hiding the disclaimer in CSS** — `display:none`, `aria-hidden`, `font-size:0`, "minified to nothing" all kill the disclaimer legally. The audit must verify the disclaimer is RENDERED.
4. **Removing the model default without checking for backfill** — if existing rows have the default value, the migration is a no-op for them, but new records require explicit selection. Document this in the migration comment.
5. **Stopping at "the labels are OK"** — language is only 1 of 6 pillars. A neutral label with a green check icon still crosses the line.
6. **Trusting the implementer not to invent a "reasonable" disclaimer** — the disclaimer text must come from the contract/TDR or a lawyer, not from the implementer's intuition. If the contract doesn't specify the exact text, flag this as an open question for the user.

## When the audit returns APROVADO

Even when the audit finds no violations, write the FINE list (anti-second-guess). List:
- Each pillar that was checked
- The surfaces that were verified
- The disclaimers that were confirmed visible
- The model defaults that were confirmed neutral

Without the FINE list, the next audit will re-litigate everything.

## From audit to manual test checklist (handoff to user)

After the fix is merged as a PR, the user will manually test it. Generate a **MANUAL TEST CHECKLIST** in a separate Codex call (read-only, xhigh). Structure:

- **Pré-condições** — branch, URL, login, imóvel de teste
- **1 section per fix commit** — each commit gets its own test group
- **Per surface** — D3, formulário, PDF, admin (each has its own bullets)
- **DB-compatibilidade check** — always include a `python manage.py shell` probe to verify internal enum strings were preserved (e.g. `OrigemFimCadeia.objects.get(...).classificacao_fim_cadeia` returns the original slug, not the new label)
- **PDFs get their own group** — explicitly download each PDF and verify the banner is present, the old label is gone, the layout is not broken
- **Sanity checks** — `rg "Lídima"` everywhere should return 0 in user-facing files; `rg "validação registral"` should return only the negative disclaimer

**Honest caveats to flag to the user:**
- The checklist may include code snippets (e.g. JS console simulation) that depend on globals (`window.tisId`, `window._zoomGroup`) that may not exist in the actual build. Tell the user upfront: "if this doesn't work, the test is invalid; report back".
- The audit is for **commit 4 (fallback) is hard to test without modifying DB or monkey-patching JS**. The simulation snippet is best-effort.
- The checklist should be **short and skimmable** — under 30 bullets total if possible. The user is running it, not writing it.

The handoff prompt template:
```
Generate a MANUAL TEST CHECKLIST for PR #N. The PR implements M contract-compliance fixes.
Format: por surface (formulário, D3, PDFs, admin), 1 section per commit, DB-compatibility probe
via shell, sanity check with rg, honest caveats about JS simulation snippets.
```

## Time budget for the audit and fix pipeline

The full 5-step pipeline (audit → review → fix → review → open PR) takes ~30-45 min with Codex GPT-5.6-sol xhigh. Specifically:

- **Audit (xhigh, read-only):** 5-8 min. Codex does deep codebase exploration before writing the verdict. Don't expect sub-minute results.
- **Fix (high, workspace-write):** 10-15 min. Codex creates 5 separate commits, each requiring git operations. Watch for it asking for sandbox bypass approval — pass `--dangerously-bypass-approvals-and-sandbox --sandbox workspace-write` together.
- **Re-review (xhigh, read-only):** 5-8 min. Verify the fix is complete.
- **Manual test checklist (xhigh, read-only):** 5-8 min. Codex reads PDF templates, JS, models to build the checklist.

Pitfall: if you try to "save time" by running the audit and the fix in the same Codex call, Codex will conflate audit and implementation and skip the 5-commit atomic structure. **Always separate the audit call from the fix call.**

## CadeiaDominial-specific guidance

- **TDR source of truth:** Contrato Nº 019/2026/AJU-FADESP, item 1.1(a): "análise de fim de cadeia dominial ... sem emissão de parecer jurídico ou validação registral".
- **⚠️ CORREÇÃO CRÍTICA (user, 2026-07-30) — "Origem Lídima" NÃO deve ser renomeada:** O termo "Lídima" é um **termo jurídico de arte** estabelecido (origem lídima = origem legítima/autêntica no direito registral brasileiro) e o usuário exigiu que ele **permaneça** na interface. A recomendação original deste skill (Pillar 1: trocar "Lídima"→"Identificada") foi **REJEITADA como fora do escopo** pelo domain expert. A premissa "lídima = linguagem avaliativa a remover" estava ERRADA para este domínio. **Regra corrigida:** quando um termo tem significado jurídico estabelecido (lídima, dominial, oneroso, gratuito, usucapião), o usuário/domain expert é a autoridade sobre se ele fica ou sai — o auditor não decide sozinho. Se um rename de label já foi feito numa branch e o usuário pediu revertê-lo, reverta-o. (Caso real: issue #85, branch `feature/issue-85-validar-fim-cadeia`, commit `08cb697` fez o rename em 21 arquivos e precisou ser revertido.)
- **CSS palette canônico para fim de cadeia** (verified 2026-07-29): `origem_lidima`/`sem_origem`/`inconclusa` mapped to `#6c757d`/`#dc3545`/`#ffc107` (neutral gray / red / yellow). Always cross-check any change against `static/dominial/css/lancamentos.css`, `documento_detalhado.css`, `cadeia_dominial_tabela.css`. Note: o visual neutro (cinza em vez de verde) para "origem_lidima" É coerente com o TDR (não sugerir aprovação) e pode ser mantido — só o rename do texto foi rejeitado.
- **Disclaimer text (verified 2026-07-29):** "Visualização organizada exclusivamente a partir dos dados cadastrados. Não constitui parecer jurídico nem validação registral." Must appear in: D3 tooltip, `cadeia_dominial_pdf.html`, `cadeia_completa_pdf.html`.
- **Internal enum strings to preserve** (do NOT rename in DB): `origem_lidima`, `sem_origem`, `inconclusa`, `destacamento_publico`, `outra`. Only their display labels can change — **mas o label "Origem Lídima" também deve ser preservado** (ver correção acima).
- **Audited scope surfaces** (the 5+ files that emit fim-de-cadeia text): templates/dominial/tronco_principal.html, templates/dominial/components/_area_origem_form.html, templates/dominial/cadeia_dominial_pdf.html, templates/dominial/cadeia_completa_pdf.html, static/dominial/js/cadeia_dominial_d3.js, static/dominial/js/origem_simples.js, dominial/models/documento_models.py, dominial/models/lancamento_models.py, dominial/templatetags/dominial_extras.py.

## Related skills (overlap notes for the curator)

- `blindspot-review-protocol` — reviews spec/plan against implementation. Different direction: this skill reviews implementation against contract. The two often pair: spec-review catches "the spec is wrong", contract-audit catches "the code is correct for the spec but the spec is wrong for the contract".
- `codex-impl-cycle` — the orchestrator cycle (plan → impl → review). The contract-scope-audit produces findings; the cycle applies the fix.
- `requesting-code-review` — pre-commit code review. Different artifact: code quality vs. regulatory compliance.
- `writing-plans` — produces plans. This skill produces audits.

If a future request mixes "audit against contract" with "fix the findings", run this skill first (output: audit with fix plan), then a separate implementer card for the fix using codex-impl-cycle.

## See also (support files)

- `references/contract-clause-decomposition.md` — how to break a TDR/contract clause into auditable sub-requirements. Includes the 6-pillar derivation.
- `references/disclaimer-text-by-domain.md` — domain-specific disclaimer templates (CadeiaDominial/LGPD/financial/medical).
- `references/label-rename-without-migration.md` — the pattern of preserving internal enum strings while renaming only user-facing labels. Includes Django `choices` and React rendering examples.
- `references/manual-test-checklist-template.md` — prompt template for generating the handoff checklist (audit→fix→manual test), plus a real example from issue #85 / PR #89. Includes honest caveats about JS simulation snippets and DB-compatibility probes.
