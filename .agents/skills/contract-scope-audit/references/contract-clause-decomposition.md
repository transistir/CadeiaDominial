# Contract-clause decomposition

How to break a contract / TDR / regulatory clause into the 6-pillar audit framework, so each clause maps to specific user-facing surfaces to check.

## The principle

A contract clause that says "X is allowed / X is forbidden / X is required" is a **scope constraint**. To audit the implementation against this constraint, decompose the clause into the **observable surfaces** where compliance can be detected, and the **test cases** that prove compliance.

Most failures happen because the clause is decomposed INCOMPLETELY — only the "obvious" surface is checked (e.g. only the UI label), while hidden surfaces (CSS colors, model defaults, JS fallbacks, PDF text) violate the clause silently.

## The decomposition recipe (5 steps)

### Step 1: Extract the literal constraint

Copy the clause verbatim, with its source citation. The audit must reference the EXACT text, not a paraphrase.

**Example (CadeiaDominial, TDR item 1.1(a)):**

```
"Análise de fim de cadeia dominial consiste na identificação do último
titular registrado no conjunto de documentos cadastrados, com indicação
de lacunas ou pendências documentais, SEM EMISSÃO DE PARECER
JURÍDICO OU VALIDAÇÃO REGISTRAL."

Source: Contrato Nº 019/2026/AJU-FADESP, TDR, item 1.1(a)
```

### Step 2: List the POSITIVE and NEGATIVE obligations

Split the clause into:
- **POSITIVE:** what the system MUST do (e.g. "identify the last registered holder")
- **NEGATIVE:** what the system MUST NOT do (e.g. "no legal opinion, no registry validation")

The NEGATIVE obligations are usually more dangerous because they have many hidden surfaces where they can be violated.

**Example:**

| Type | Obligation |
|---|---|
| POSITIVE | Identify the last registered holder |
| POSITIVE | Indicate documentary gaps or pendencies |
| NEGATIVE | NO emission of parecer jurídico (legal opinion) |
| NEGATIVE | NO validação registral (registry validation) |

### Step 3: For each obligation, list the AUDITABLE SURFACES

For each obligation, ask: "WHERE could the system violate this in user-facing code?"

**For NEGATIVE obligations, the surfaces are:**
- UI labels and buttons (Django templates, JS, React)
- Tooltips and help text
- Error messages and validation feedback
- PDF templates and report headers
- Email subjects and bodies
- API response fields
- Excel export headers
- CSS classes that imply state (colors, icons)
- Model defaults that encode judgment
- JS fallbacks (the `else` branch)
- Documentation strings (help_text, verbose_name, docstrings)
- Logs and audit trails (if visible to users)

**For POSITIVE obligations, the surfaces are:**
- The view / endpoint that performs the identification
- The data structure returned to the user
- The rendering of the result (chain, table, tree)
- The handling of edge cases (no documents, multiple holders, etc.)

**Example (NEGATIVE: "no parecer jurídico"):**

| Surface | What to check | Where in CadeiaDominial |
|---|---|---|
| UI label | Does the option text claim legal effect? | `_area_origem_form.html:86` |
| UI tooltip | Does the tooltip make a legal claim? | `cadeia_dominial_d3.js:1001` |
| UI color | Does the color imply approved/rejected? | `cadeia_dominial_d3.js:929` |
| UI icon | Does the icon imply state judgment? | `cadeia_dominial_d3.js:1001` (🟢/🔴) |
| Model default | Does the default encode a positive judgment? | `0041_fimcadeia.py:19` |
| JS fallback | Does the fallback label missing data negatively? | `cadeia_dominial_d3.js:980` |
| PDF text | Does the PDF text make a legal claim? | `cadeia_dominial_pdf.html` |
| Disclaimer | Is there a visible non-claim disclaimer? | (all PDFs and tooltips) |

### Step 4: For each surface, define the COMPLIANCE TEST

For each surface, write a one-line test that the implementer / reviewer can run mechanically:

**Example:**

| Surface | Test |
|---|---|
| UI label | `rg -nF "Lídima" templates/dominial/` should return 0 hits |
| UI tooltip | `rg -nF "Lídima" static/dominial/js/` should return 0 hits |
| UI color | `rg -nE "(#28a745\|🟢).*origem_lidima" static/` should return 0 hits |
| Model default | `rg -nF "default='origem_lidima'" dominial/` should return 0 hits |
| JS fallback | `rg -nF "Sem Origem" static/dominial/js/` in fallback branches should return 0 hits |
| Disclaimer | `rg -nF "Não constitui parecer jurídico" templates/dominial/ static/` should return ≥3 hits (one per surface) |

### Step 5: Run the tests, classify the output

| Test result | Classification | Action |
|---|---|---|
| 0 hits where expected | CONFORME | Pass |
| N hits where 0 expected, but they are old/legacy/intentional | CONFORME (legacy) | Document the exemption |
| N hits where 0 expected, and they are user-facing | VIOLAÇÃO | Must fix |
| ≤N hits where ≥N expected (e.g. missing a disclaimer surface) | VIOLAÇÃO | Must fix (add disclaimer) |
| N hits where N expected | CONFORME | Pass |

## Worked example: decomposing "no validação registral"

**Step 1 — Literal constraint:**

```
"análise de fim de cadeia dominial ... sem emissão de parecer jurídico
OU VALIDAÇÃO REGISTRAL"

Source: Contrato Nº 019/2026/AJU-FADESP, TDR, item 1.1(a)
```

**Step 2 — Obligations:**

| Type | Obligation |
|---|---|
| NEGATIVE | NO "validação registral" — i.e. the system must not validate whether a registration is correct, sufficient, or legally effective |

**Step 3 — Surfaces (going beyond just "the label"):**

| Surface | What to check |
|---|---|
| Classification labels | "Imóvel com Origem Lídima" implies "validated as legitimate" — VIOLATION |
| Color coding | Green for "Lídima", red for "Sem Origem" — implies approval/rejection — VIOLATION |
| Model default | `default='origem_lidima'` — assumes validation is positive — VIOLATION |
| JS fallback | Defaulting unknown types to "Sem Origem" — labels unknown as negative — VIOLATION |
| Disclaimer | No visible "não constitui validação registral" — VIOLATION |

**Step 4 — Compliance tests:**

```bash
# Test 1: labels don't make legal claims
rg -nE "(Lídima|Legítimo|Válido|Perfeito|Regular)" templates/dominial/ static/dominial/js/ dominial/models/

# Test 2: colors are neutral for descriptive states
rg -nE "#28a745" static/dominial/css/ | grep -i "origem_lidima"
# Expected: 0 hits (or only in non-origem_lidima contexts)

# Test 3: no positive default
rg -nE "default=['\"](origem_lidima|lidima|valido|perfeito)" dominial/

# Test 4: no negative fallback
rg -nE "(else|default).*['\"]Sem Origem['\"]" static/dominial/js/

# Test 5: disclaimer is visible
rg -nF "Não constitui validação registral" templates/dominial/ static/dominial/js/
# Expected: ≥3 hits (D3 tooltip + 2 PDFs minimum)
```

**Step 5 — Classification:**

| Test | Result | Classification |
|---|---|---|
| 1 — labels | "Lídima" appears in 4 user-facing files | VIOLAÇÃO |
| 2 — colors | `#28a745` paired with `origem_lidima` in D3 + CSS | VIOLAÇÃO |
| 3 — default | `default='origem_lidima'` in 0041_fimcadeia.py:19 | VIOLAÇÃO |
| 4 — fallback | `else { tipo = "Sem Origem" }` in D3 | VIOLAÇÃO |
| 5 — disclaimer | 0 hits anywhere | VIOLAÇÃO |

Total: 5 violations → CONFORMIDADE: NECESSITA AJUSTES (5 commits fix).

## Anti-patterns in decomposition

- **Stopping at the UI label.** "We changed the label, we're done." No — colors, defaults, fallbacks, disclaimers are separate pillars.
- **Treating the clause as a wishlist.** The clause is BINDING. "But it would be useful to show X" is not an argument.
- **Decomposing only the NEGATIVE obligations.** POSITIVE obligations also need surfaces ("where does the system identify the last registered holder?"). Missing surfaces → missing requirements.
- **Asking "is this within scope?" per file in isolation.** The clause must be checked across ALL files together. A file can look fine in isolation but the COLLECTIVE behavior crosses the line.
- **Skipping the compliance tests.** The tests are what makes the audit VERIFIABLE. Without them, "looks fine to me" is a self-report, not an audit.

## The "audit-derivation" prompt template

When delegating the audit to Codex / Claude / GLM, use this prompt structure:

```markdown
You are auditing an existing feature against a contract clause.

## Source constraint (quote verbatim)
"<exact contract / TDR / regulation text>"

## Decomposition request
For EACH of the 6 pillars below, list the user-facing surfaces to check
and the compliance test to run:

1. LANGUAGE / COPY — labels, tooltips, error messages, PDF text
2. VISUAL SEMANTICS — colors, icons
3. MODEL DEFAULTS — Django `default=`, JS fallback values
4. FALLBACK UI — `else` branches, "value not found" handlers
5. MANDATORY DISCLAIMER — visible, consistent, before data
6. GENERATIVE / INFERENCE — any system-generated claim

## Output format
For each pillar, list the file:line citations where the clause is
VIOLATED, ATENÇÃO (mild violation), or CONFORME.

End with: "CONFORMIDADE: APROVADO | NECESSITA AJUSTES" + headline counts.
```

This is the prompt I used for the CadeiaDominial #85 audit. It produced the structured 5-finding output in ~5 minutes of Codex GPT-5.6 xhigh execution.
