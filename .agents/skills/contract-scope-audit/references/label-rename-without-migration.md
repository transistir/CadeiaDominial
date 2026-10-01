# Label-rename without migration

The pattern of preserving the internal Python/DB enum string while renaming only the user-facing display label. Zero migrations, zero data loss, full semantic fix.

## The principle

A Django (or any ORM) enum field has TWO concepts:

1. **Identifier (the value):** a stable, machine-readable string used in code, DB, URLs, API payloads. Renaming this requires a migration that rewrites all rows + all code that references it.
2. **Label (the display text):** the human-readable string shown in the UI. Renaming this is a single tuple-element change in `choices=`, zero migrations.

**Always rename only the label, never the identifier.**

## Django `choices` pattern

The `choices` attribute is a list of `(identifier, label)` tuples. The identifier goes to the DB; the label goes to the UI:

```python
# In models/documento_models.py
classificacao = models.CharField(
    max_length=50,
    choices=[
        ('origem_lidima', 'Imóvel com Origem Lídima'),  # ← LABEL here
        ('sem_origem', 'Imóvel sem Origem'),
        ('inconclusa', 'Situação Inconclusa'),
    ],
    ...
)

# To rename only the LABEL (zero migration):
classificacao = models.CharField(
    max_length=50,
    choices=[
        ('origem_lidima', 'Imóvel com Origem Identificada'),  # ← only this changed
        ('sem_origem', 'Imóvel sem Origem'),
        ('inconclusa', 'Situação Inconclusa'),
    ],
    ...
)

# The DB still stores 'origem_lidima'. The user now sees 'Identificada'.
```

## Patterns to look for

### 1. Direct `choices` tuples (most common)

```python
# Find every choices tuple in the codebase
rg -nE "choices\s*=\s*\[" dominial/models/ | head -20
```

For each tuple, the second element is the label. Search for "judge-y" labels (Lídima, Válido, Nulo, Perfeito, Regular, Irregular, Legítimo) and rename only those.

### 2. `get_<field>_display()` references

The Django convention `obj.get_classificacao_display()` returns the LABEL. If any code uses this method to render the label, the rename propagates automatically. Verify by `grep`-ing:

```bash
rg -nE "get_[a-z]+_display\(\)" dominial/ static/dominial/js/ templates/dominial/
```

### 3. Template filter lookups (manual dict mapping)

Some code uses a manual `dict()` to map identifier → display text, often in template tags or JS:

```python
# In dominial/templatetags/dominial_extras.py
TIPO_NOMES = {
    'origem_lidima': 'Origem Lídima',  # ← also rename here
    'sem_origem': 'Sem Origem',
    'inconclusa': 'Situação Inconclusa',
}
```

These are NOT auto-updated by Django. **You must rename them manually in lockstep with the `choices` tuple.** Search for dicts keyed by your enum values:

```bash
rg -nE "'origem_lidima'|\"origem_lidima\"" dominial/ static/dominial/js/ templates/
# Every hit is either: a choices tuple (label position), a dict key (rename label), a comparison (DO NOT rename), or a comment
```

### 4. JS object maps

```javascript
// In static/dominial/js/cadeia_dominial_d3.js
const CLASSIFICACAO_LABELS = {
  "origem_lidima": "Origem Lídima",  // ← rename here
  "sem_origem": "Sem Origem",
  "inconclusa": "Situação Inconclusa",
};
```

Same rule: rename the VALUE side of the key-value pair, not the KEY.

## What NEVER to rename

- The identifier string itself: `'origem_lidima'` (single-quoted in Python, double-quoted in JS, used as comparison/key/URL)
- Migration history files (they preserve the old state by design)
- Test fixtures that assert on the identifier (`assert obj.classificacao == 'origem_lidima'` — still works, identifier unchanged)
- API response keys
- URL parameters
- Database column values

## The grep recipe for verifying "label-only rename"

After applying the rename, run these two greps and verify:

```bash
# 1. The OLD label text should be GONE from user-facing files
rg -nF "Origem Lídima" templates/ static/ dominial/models/ dominial/templatetags/
# Expected: 0 hits (or only in historical docs that should be kept as-is)

# 2. The identifier should be UNCHANGED everywhere
rg -nF "origem_lidima" dominial/ templates/ static/
# Expected: many hits, ALL unchanged (the identifier was preserved)
```

If the OLD label still appears somewhere user-facing, you missed a file. If the identifier count changed, you accidentally renamed an identifier.

## Why this matters

- **Zero migrations:** the DB column values stay `origem_lidima`, no `makemigrations` + `migrate` cycle.
- **Zero data loss:** existing rows keep their data. Audit/history stays consistent.
- **Zero backfill:** no need to update rows in production.
- **Trivial rollback:** if the rename is wrong, revert the label and you're done.
- **Audit-friendly:** the contract-auditor can see "label changed, identifier unchanged" as a one-line commit.

The cost: you have to remember to rename the label in MULTIPLE places (choices tuple, dict map, JS object). Use the grep recipe to verify completeness.

## Common gotcha: renaming the label but forgetting a JS map

The D3 file (or any frontend JS) often has its own label dictionary:

```javascript
// static/dominial/js/cadeia_dominial_d3.js:993
if (d.data.classificacao_fim_cadeia === "origem_lidima") {
  classificacao = "Origem Lídima";  // ← for got here
}
```

If you rename the Django label but miss this, the D3 frontend still shows the old text. Always grep for the identifier across BOTH backend AND frontend:

```bash
rg -nF "origem_lidima" --type-add 'web:*.{js,ts,jsx,tsx,html}' --type web
```

## When you DO need to rename the identifier

If the identifier itself is the problem (e.g. `'parecer_juridico'` in the identifier IS the legal claim), the right fix is a 3-step migration:

1. Add the new identifier as an alias (`db.add_argument('--migrate-old-ids', ...)`)
2. Add a data migration to rewrite rows
3. Update all code references + remove the old identifier

This is a 2-3 PR effort, not a 1-commit rename. Distinguish early: **is the problem in the identifier or in the label?**

The CadeiaDominial TDR case (origem_lidima) is a label-only problem. The identifier `origem_lidima` is just a slug — it doesn't appear in the UI unless explicitly rendered. The label `Lídima` is the user-facing text. Renaming the label is the right fix.
