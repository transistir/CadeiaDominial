# Produto 1 - Revised Implementation Plan (Post-Codex Review)

**Worktree:** /root/dev/cadeia-dominial/worktrees/produto-1
**Branch:** feat/produto-1-issues-47-53
**Base:** origin/main (c94ba3d)
**Codex Score: 2.7/5 → revised plan below**

## Codex Key Findings

### Critical Corrections Needed

| Issue | Original Score | Key Gaps |
|-------|:---:|---|
| #47 | 3→5 | Server-side normalize missing. `replace(',','.')` single-match bug. Two area templates. |
| #48 | 2→5 | setTimeout fragile. Three overlapping fit routines create races. |
| #49 | 3→5 | SVG lacks viewBox. Need beforeprint/afterprint. @page landscape. Hide base nav. |
| #50 | 2→5 | Only changed imovel_form. 73 matches in 19 templates need systematic audit. |
| #51 | 4→5 | Handle transcrição + matrícula. Show target documento, not always imóvel principal. |
| #52 | 2→5 | Lexicographic ordering bug. LancamentoPessoa not legacy FK. No select_related. |
| #53 | 3→5 | Word-boundary matching. Accent normalization. Priority for multiple keywords. |

### Deploy Blocker
nginx: `Cache-Control: public, immutable` 30d + `StaticFilesStorage` no fingerprinting.
→ HTML novo chega com JS/CSS velho. Must version assets or purge cache on deploy.

### Order
1. #47 (client+server validation)
2. #51 (simplest, before #52 for layout)
3. #52 (builds on #51 layout)
4. #53 (keywords)
5. #48 (refactor fit)
6. #49 (print, depends on #48)
7. #50 (textual swap, last to avoid merge conflicts)

---

## Corrected Implementation Specs

### #47 — Comma → Period (FULL SPEC)

**Files:**
- `templates/dominial/components/_area_form.html` — normalize script
- `templates/dominial/components/_area_origem_form.html` — same (used by lancamento form)
- `dominial/services/lancamento_campos_service.py` (@line 51) — **server-side** normalize: `area_str.replace(',', '.')` before `float()`, or use `Decimal`

**Client-side:**
- Replace ALL commas: `value.replace(/\,/g, '.')` NOT `.replace(',', '.')`
- Full validation regex: `/^\d+([\.,]\d+)?$/` (NOT `parseFloat` which accepts `12abc`)
- Error message when non-numeric after normalization

**Server-side:**
- In `lancamento_campos_service.py`: before `float(area)`, normalize comma→period
- Consider `Decimal` for precision (max_digits=12, 4 decimal places)

### #48 — Auto-fit Tree (REFACTORED)

**File:** `static/dominial/js/cadeia_dominial_d3.js`

**Problem:** Three competing routines:
- `enquadrarArvoreNoSVG()` @L168 (already called) — debounce transition
- `expandirArvore()` @L18 — debounce 300ms
- `centralizarArvore()` @L315 — sets scale=1, no bounding box

**Solution: Single `fitTreeToViewport()`** that:
- Uses `requestAnimationFrame` after DOM render, NOT setTimeout
- Reads actual container dimensions from SVG boundingClientRect
- Sets SVG viewBox to fit all nodes
- Handles: empty tree, fetch error, single node, resize
- Replace existing `enquadrarArvoreNoSVG()` call with this unified function
- Keep manual expand button (calls same function)

### #49 — Print Button (ENHANCED)

**Files:**
- `templates/dominial/cadeia_dominial_d3.html` — button
- `static/dominial/css/cadeia_dominial_d3.css` — @media print + hide base nav

**Additional requirements:**
- `@page { size: landscape; margin: 1cm; }`
- `beforeprint` event: set SVG viewBox from tree bounding box, reset zoom
- `afterprint` event: restore zoom/pan state
- Hide in @media print: `base.html` nav/header (`.navbar`, `.nav`, `header`)
- Disable button while tree is loading

### #50 — "Cartório" → "Registro Imobiliário" (AUDITED)

**Rule:** CRI (Cartório de Registro de Imóveis) only. Keep "Cartório" for tabelionato/notas.

**Systematic audit required:**
- CRIs: `imovel.cartorio`, `documento.cartorio`, `cartorio_origem` → change label text
- Tabelionato: `cartorio_transmissao_compat` → KEEP "Cartório"
- Field names, IDs, URLs, CSS classes: NEVER change

**Must audit ALL templates** (not just imovel_form). Current implementation only touched 6 strings in imovel_form.html — need `rg cartorio` across all templates.

### #51 — Matrícula Highlight (CORRECTED)

**Label handling:**
- Use `{{ imovel.get_tipo_documento_principal_display }}` instead of hardcoded "MATRÍCULA"
- Show both: imóvel principal doc AND target documento for this lancamento
- Target doc may differ from imóvel principal (histórico/importado)

**CSS:** Move inline style to `forms.css`. No sticky on narrow screens (`@media max-width`).

### #52 — Previous Lancamentos Panel (CORRECTED)

**Files:**
- `dominial/views/lancamento_views.py` — query with select_related
- `templates/dominial/lancamento_form.html` — panel
- `static/dominial/css/forms.css` — styles
- `static/dominial/js/lancamento_form.js` — minimal JS

**Query corrections:**
- Order: `-data, -id` (NOT `-numero_lancamento` which is lexicographic)
- `select_related('tipo', 'documento')` to avoid N+1
- `prefetch_related('lancamentopessoa_set__pessoa')` for transmitente/adquirente names
- Limit 20, but indicate "últimos 20" not "(20)" which implies total

**People:** Use `LancamentoPessoa` relationship, not legacy FK fields `transmitente`/`adquirente` (which may be null)
- `LancamentoPessoa.objects.filter(lancamento=..., tipo='transmitente').first()` per lancamento
- Or prefetch and iterate in template

**Layout:** Use `<details><summary>` native HTML (no JS collapse needed, better a11y)

### #53 — Keyword Alerts (CORRECTED)

**Files:**
- `dominial/views/api_views.py` — keyword matching logic
- `templates/dominial/lancamentos.html` — badge display
- `static/dominial/css/lancamentos.css` — badge styles

**Keyword config (dict with priority):**
```python
PALAVRAS_CHAVE_ALERTA = [
    {'label': 'URGENTE', 'slug': 'urgente', 'priority': 1, 'color': 'red'},
    {'label': 'ATENÇÃO', 'slug': 'atencao', 'priority': 2, 'color': 'orange'},
    {'label': 'PENDENTE', 'slug': 'pendente', 'priority': 3, 'color': 'amber'},
]
```

**Matching rules:**
- **Word boundary**: `\b` regex — "PENDENTE" in "INDEPENDENTE" should NOT match
- **Accent normalization**: `ATENCAO` matches `ATENÇÃO` (unicodedata.normalize + remove diacritics)
- **Case insensitive**: `casefold()` or `re.IGNORECASE`
- Show only **highest priority** keyword when multiple found (not all)
- Only apply if `observacoes` is not empty
- Process in Python (list is per-page, max 10 items — cheap)

---

## Deploy Corrections

**Cache invalidation required.** Options:
1. Add `ManifestStaticFilesStorage` to settings_prod.py (hash filenames)
2. Or: change asset URLs on deploy (e.g., `?v=2`)
3. Or: purge nginx cache (`docker-compose exec nginx nginx -s reload` + clear browser cache)

**Deploy steps:**
```bash
# On test server
ssh root@188.245.225.127
cd /root/CadeiaDominial
git pull origin main  # or checkout feat/produto-1-issues-47-53
docker-compose down web
docker-compose build --no-cache web
docker-compose up -d
# Wait for health check
docker-compose exec web python manage.py collectstatic --noinput
docker-compose restart nginx
```

**Smoke tests after deploy:**
- Empty tree / small tree / large tree
- Print after zoom/pan
- Area with comma / period / invalid input
- Transcrição document type
- History with multiple people
- Keywords with accents / word boundaries / multiple matches
