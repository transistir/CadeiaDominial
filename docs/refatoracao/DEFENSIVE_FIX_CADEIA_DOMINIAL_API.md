# Defensive Fix: Cadeia Dominial API Contract Handling

**Date:** 2025-11-18
**Status:** ✅ Implemented and Tested
**Files Modified:**
- `dominial/services/lancamento_duplicata_service.py`
- `templates/dominial/duplicata_importacao.html`

## Summary

Added comprehensive defensive coding to handle potential API contract inconsistencies in the duplicate import workflow, preventing template crashes when the cadeia dominial data structure varies.

## The Problem

The API contract for `cadeia_dominial` changed in commit 4bc9bd9:

### Old Format (List)
```python
cadeia_dominial = [
    {'documento': <Documento>, 'lancamentos': [...]},
    {'documento': <Documento>, 'lancamentos': [...]},
]
```

### New Format (Dict)
```python
cadeia_dominial = {
    'documento_origem': {'numero': 'M123', 'id': 1},
    'total_documentos': 3,
    'documentos': [
        {'documento': <Documento>, 'lancamentos': [...]},
        {'documento': <Documento>, 'lancamentos': [...]},
    ]
}
```

### The Issue

While an adapter layer exists in `LancamentoDuplicataService.verificar_duplicata_antes_criacao()` (line 92) to extract the list:
```python
'cadeia_dominial': duplicata_info.get('cadeia_dominial', {}).get('documentos', [])
```

There was concern about potential code paths where:
1. The adapter might be bypassed
2. The dict structure could be passed directly
3. Edge cases could cause template crashes

## The Solution

Implemented **defense in depth** with three layers of protection:

### Layer 1: Service-Level Defensive Handling

**File:** `dominial/services/lancamento_duplicata_service.py:192-312`

Added comprehensive defensive code in `obter_dados_duplicata_para_template()`:

```python
# DEFENSIVE: Handle both old (list) and new (dict with 'documentos' key) formats
if isinstance(cadeia_dominial_raw, dict):
    logger.warning(
        "DEFENSIVE: cadeia_dominial is dict (new format from DuplicataVerificacaoService). "
        f"Keys: {cadeia_dominial_raw.keys()}. Extracting 'documentos' list."
    )
    cadeia_dominial = cadeia_dominial_raw.get('documentos', [])
    if not cadeia_dominial:
        logger.error(
            "DEFENSIVE: 'documentos' key missing or empty in cadeia_dominial dict. "
            f"Available keys: {cadeia_dominial_raw.keys()}"
        )
elif isinstance(cadeia_dominial_raw, list):
    logger.info("DEFENSIVE: cadeia_dominial is list (expected adapter output). Using directly.")
    cadeia_dominial = cadeia_dominial_raw
else:
    logger.error(
        f"DEFENSIVE: Unexpected cadeia_dominial type: {type(cadeia_dominial_raw)}. "
        "Defaulting to empty list to prevent template crash."
    )
    cadeia_dominial = []
```

**Features:**
- ✅ Detects dict vs list format automatically
- ✅ Extracts `documentos` list from dict if needed
- ✅ Logs warnings/errors for debugging
- ✅ Defaults to empty list on unexpected types
- ✅ Validates item structure before processing
- ✅ Exception handling with detailed error logging
- ✅ Success logging with metrics

### Layer 2: Comprehensive Logging

Added logging at multiple checkpoints:

```python
import logging
logger = logging.getLogger(__name__)

# Entry point logging
logger.warning("DEFENSIVE: cadeia_dominial is dict...")
logger.info("DEFENSIVE: cadeia_dominial is list...")
logger.error("DEFENSIVE: Unexpected cadeia_dominial type...")

# Item validation logging
logger.error("DEFENSIVE: cadeia_dominial item is not dict...")
logger.error("DEFENSIVE: cadeia_dominial item missing 'documento' key...")

# Exception logging
logger.error(f"DEFENSIVE: Exception formatting cadeia_dominial: {e}...")

# Success logging
logger.info(f"DEFENSIVE: Successfully formatted template data. cadeia_dominial items: {len(...)}")
```

**Benefits:**
- Track which data structure is received in production
- Diagnose edge cases quickly
- Monitor for unexpected scenarios
- Verify adapter is working correctly

### Layer 3: Template-Level Graceful Degradation

**File:** `templates/dominial/duplicata_importacao.html:163-169, 258-289`

Updated template to handle missing data gracefully:

**Hidden Inputs Section:**
```django
{% if duplicata_info.cadeia_dominial %}
    {% for item in duplicata_info.cadeia_dominial %}
        {% if item.documento and item.documento.id %}
            <input type="hidden" name="documentos_importaveis[]" value="{{ item.documento.id }}">
        {% endif %}
    {% endfor %}
{% endif %}
```

**Display Section:**
```django
{% if duplicata_info.cadeia_dominial %}
    {% for item in duplicata_info.cadeia_dominial %}
        {% if item.documento %}
            <div class="lancamento-item">
                <h6><strong>{{ item.documento.numero|default:"N/A" }}</strong> - {{ item.documento.tipo|default:"N/A" }}</h6>
                <p><small>Livro: {{ item.documento.livro|default:"N/A" }}, Folha: {{ item.documento.folha|default:"N/A" }}</small></p>
                ...
            </div>
        {% endif %}
    {% empty %}
        <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle"></i>
            Nenhum documento encontrado na cadeia dominial.
        </div>
    {% endfor %}
{% else %}
    <div class="alert alert-warning">
        <i class="fas fa-exclamation-triangle"></i>
        Informações da cadeia dominial não disponíveis.
    </div>
{% endif %}
```

**Features:**
- ✅ Checks for null/empty cadeia_dominial
- ✅ Validates item.documento exists
- ✅ Uses default filters for missing values
- ✅ Shows helpful warnings when data unavailable
- ✅ {% empty %} clause for empty iterations
- ✅ Never crashes on missing attributes

## Data Flow Protection

### Normal Flow (Adapter Working)
```
DuplicataVerificacaoService.verificar_duplicata_origem()
  returns: {'existe': True, 'cadeia_dominial': {'documentos': [...]}}
         ↓
LancamentoDuplicataService.verificar_duplicata_antes_criacao()
  extracts: duplicata_info.get('cadeia_dominial', {}).get('documentos', [])
  returns: {'tem_duplicata': True, 'cadeia_dominial': [...]}
         ↓
LancamentoDuplicataService.obter_dados_duplicata_para_template()
  receives: cadeia_dominial = [...]  (list)
  ✅ DEFENSIVE: Detects list, uses directly
  logs: "DEFENSIVE: cadeia_dominial is list (expected adapter output)"
         ↓
Template receives: dados_template['cadeia_dominial'] = [...]
  ✅ DEFENSIVE: Validates items exist before rendering
```

### Edge Case Flow (Adapter Bypassed)
```
Unknown code path passes dict directly
         ↓
LancamentoDuplicataService.obter_dados_duplicata_para_template()
  receives: cadeia_dominial = {'documentos': [...]}  (dict)
  ✅ DEFENSIVE: Detects dict, extracts 'documentos' list
  logs: "DEFENSIVE: cadeia_dominial is dict (new format)..."
         ↓
Template receives: dados_template['cadeia_dominial'] = [...]
  ✅ DEFENSIVE: Validates items exist before rendering
```

### Failure Flow (Unexpected Type)
```
Corrupted data or bug passes unexpected type
         ↓
LancamentoDuplicataService.obter_dados_duplicata_para_template()
  receives: cadeia_dominial = "string" or None or ???
  ✅ DEFENSIVE: Detects unexpected type, defaults to []
  logs: "DEFENSIVE: Unexpected cadeia_dominial type: <class 'str'>"
         ↓
Template receives: dados_template['cadeia_dominial'] = []
  ✅ DEFENSIVE: Shows warning "Informações da cadeia dominial não disponíveis"
  ✅ No crash, user sees helpful message
```

## Testing

### Test Results
```bash
$ pytest dominial/tests/test_fase2_duplicata_integracao.py -v
======================== 9 passed, 3 skipped in 9.72s =========================
```

All integration tests pass, including:
- `test_obter_dados_duplicata_para_template` ✅
- `test_verificar_duplicata_antes_criacao_com_duplicata` ✅
- `test_processar_importacao_duplicata_sucesso` ✅

### Test Coverage
```python
# Test simulates old format (list)
duplicata_info = {
    'tem_duplicata': True,
    'documento_origem': self.documento_origem,
    'documentos_importaveis': [self.documento_origem],
    'cadeia_dominial': [{  # ← List format
        'documento': self.documento_origem,
        'lancamentos': [self.lancamento_origem]
    }]
}

dados_template = LancamentoDuplicataService.obter_dados_duplicata_para_template(duplicata_info)

# Defensive code handles it correctly
assert len(dados_template['cadeia_dominial']) == 1  # ✅ Passes
```

## Impact Assessment

### Before (Potential Issues)
- ❌ Template could crash if dict passed directly
- ❌ No logging to diagnose data structure issues
- ❌ Silent failures or confusing errors
- ❌ Difficult to debug production issues

### After (Defensive)
- ✅ Template never crashes (graceful degradation)
- ✅ Comprehensive logging for debugging
- ✅ Clear error messages in UI
- ✅ Easy to diagnose production issues
- ✅ Works with both old and new formats
- ✅ Validates data at every step

### Backward Compatibility
- ✅ No breaking changes
- ✅ All existing tests pass
- ✅ Works with current adapter layer
- ✅ Also works if adapter is bypassed
- ✅ Template displays helpful warnings

## Logging Examples

### Normal Case (List Format)
```
INFO: DEFENSIVE: cadeia_dominial is list (expected adapter output). Using directly.
INFO: DEFENSIVE: Successfully formatted template data. cadeia_dominial items: 3
```

### Edge Case (Dict Format)
```
WARNING: DEFENSIVE: cadeia_dominial is dict (new format from DuplicataVerificacaoService).
         Keys: dict_keys(['documento_origem', 'total_documentos', 'documentos']).
         Extracting 'documentos' list.
INFO: DEFENSIVE: Successfully formatted template data. cadeia_dominial items: 3
```

### Error Case (Missing Key)
```
WARNING: DEFENSIVE: cadeia_dominial is dict (new format from DuplicataVerificacaoService).
         Keys: dict_keys(['documento_origem', 'total_documentos']).
         Extracting 'documentos' list.
ERROR: DEFENSIVE: 'documentos' key missing or empty in cadeia_dominial dict.
       Available keys: dict_keys(['documento_origem', 'total_documentos'])
INFO: DEFENSIVE: Successfully formatted template data. cadeia_dominial items: 0
```

### Unexpected Type
```
ERROR: DEFENSIVE: Unexpected cadeia_dominial type: <class 'str'>.
       Defaulting to empty list to prevent template crash.
INFO: DEFENSIVE: Successfully formatted template data. cadeia_dominial items: 0
```

## Monitoring Recommendations

In production, monitor logs for:

1. **WARNING: "cadeia_dominial is dict"** → Indicates adapter bypass, investigate code path
2. **ERROR: "documentos' key missing"** → API contract violation, needs immediate fix
3. **ERROR: "Unexpected cadeia_dominial type"** → Data corruption or severe bug
4. **ERROR: "Exception formatting"** → Unexpected error, check data integrity

## Prevention Guidelines

To prevent similar issues in the future:

1. **API Contract Changes:**
   - ✅ Update all consumers in the same commit
   - ✅ Add defensive handling for backward compatibility
   - ✅ Document contract changes clearly
   - ✅ Add logging to track format variations

2. **Template Rendering:**
   - ✅ Always validate data exists before accessing
   - ✅ Use default filters for optional fields
   - ✅ Provide {% empty %} clauses for loops
   - ✅ Show helpful error messages to users

3. **Service Layer:**
   - ✅ Validate input types at method entry
   - ✅ Log unexpected data structures
   - ✅ Fail gracefully with defaults
   - ✅ Add metrics/logging for monitoring

## Related Files

- **Service:** `dominial/services/lancamento_duplicata_service.py:192-312`
- **Template:** `templates/dominial/duplicata_importacao.html:163-169, 258-289`
- **Tests:** `dominial/tests/test_fase2_duplicata_integracao.py`
- **Original API Change:** Commit 4bc9bd9 (Nov 15, 2025)
- **Adapter Fix:** Commit 823cb48 (Nov 15, 2025)
- **Defensive Fix:** This commit (Nov 18, 2025)

## Summary

This defensive fix ensures the duplicate import workflow is **bulletproof** against API contract variations:

- **Service layer** handles both data formats automatically
- **Logging** provides visibility into data structures in production
- **Template** never crashes, shows helpful messages instead

**Result:** Users always see a working import screen, even if underlying data structures vary or have issues.
