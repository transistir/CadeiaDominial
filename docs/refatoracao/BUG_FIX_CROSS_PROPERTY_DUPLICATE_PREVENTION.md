# Bug Fix: Cross-Property Chain Duplicate Import Prevention

**Date:** 2025-11-18
**Status:** ✅ Fixed and Tested
**Files Modified:**
- `dominial/services/importacao_cadeia_service.py`
- `dominial/tests/test_cross_property_duplicate_prevention.py` (new)

## Summary

Fixed a critical bug in `ImportacaoCadeiaService` that allowed the same document to be imported multiple times when reached through different property chains.

## The Bug

### What Was Happening

When the `DocumentoImportado` model was enhanced to track the original property of each imported document (`imovel_origem`), the duplicate prevention logic was not updated to match the new semantics.

**Old duplicate check (lines 56-61):**
```python
if DocumentoImportado.objects.filter(
    documento=documento,
    imovel_origem=documento_origem.imovel  # ❌ Only checks specific property
).exists():
    erros.append(f"Documento {documento.numero} já foi importado")
    continue
```

### Why This Was a Problem

Consider this scenario:

```
Property 1 (Imovel1):
    Doc A (belongs to Imovel1)
      ↓
    Doc B (belongs to Imovel2)

Property 2 (Imovel2):
    Doc B (belongs to Imovel2)
      ↓
    Doc C (belongs to Imovel3)

Property 3 (Imovel3) - Destination:
    Will import documents from chains
```

**The problem:**
1. User imports Doc B from Imovel1's chain to Imovel3 ✅
   - Creates `DocumentoImportado(documento=Doc B, imovel_origem=Imovel2)`
2. User tries to import Doc B again from Imovel2's chain to Imovel3 ❌
   - The duplicate check filters by `(documento=Doc B, imovel_origem=Imovel2)`
   - This matches the existing record, so duplicate is prevented... **WRONG!**
   - Actually, the check was filtering by `documento_origem.imovel` (the source property of the import operation), not by the document's actual original property
   - Since the source property differs between the two import attempts, the duplicate was not detected
   - Doc B could be imported multiple times!

### Root Cause

The duplicate check assumed every imported document came from the current source property (`documento_origem.imovel`). However, in cross-property chains, documents can originate from properties different from the current import source.

## The Fix

Changed the duplicate check to only filter by the document itself, regardless of which property path leads to it:

**New duplicate check (lines 55-63):**
```python
# Verificar se já não foi importado (de qualquer propriedade)
# Correção: verifica apenas pelo documento, não pelo imovel_origem
# Isso previne duplicatas mesmo quando o documento é alcançado através
# de diferentes caminhos na cadeia (propriedades diferentes)
if DocumentoImportado.objects.filter(
    documento=documento  # ✅ Checks only by document
).exists():
    erros.append(f"Documento {documento.numero} já foi importado")
    continue
```

### Why This Works

- A document should only be imported once into a destination property, regardless of which chain path discovers it
- The `DocumentoImportado` model correctly tracks the document's actual original property (`imovel_origem`)
- The duplicate check now prevents re-imports from any source path

## Testing

Created comprehensive test suite in `dominial/tests/test_cross_property_duplicate_prevention.py`:

### Test Cases

1. **`test_prevents_duplicate_import_from_different_property_paths`**
   - ✅ Core bug fix test
   - Verifies document is only imported once even when reached through different chains

2. **`test_import_different_documents_from_different_chains`**
   - ✅ Positive case
   - Ensures different documents can still be imported normally

3. **`test_batch_import_with_duplicate_in_different_chains`**
   - ✅ Batch scenario
   - Tests partial success when one document in batch is duplicate

4. **`test_records_correct_imovel_origem_for_each_import`**
   - ✅ Data integrity
   - Verifies `imovel_origem` is correctly recorded as document's original property

5. **`test_same_document_number_different_properties_allowed`**
   - ✅ Edge case
   - Documents with same number but from different properties are different documents

6. **`test_all_documents_already_imported_returns_success`**
   - ✅ Graceful handling
   - Attempting to import all already-imported documents returns success with message

### Test Results

```bash
$ pytest dominial/tests/test_cross_property_duplicate_prevention.py -v

============================== 6 passed in 6.47s ===============================
```

## Impact Assessment

### What Changed
- ✅ Documents are now correctly prevented from being imported multiple times
- ✅ Cross-property chain traversal works correctly
- ✅ `imovel_origem` tracking remains intact

### What Didn't Change
- ✅ Same document number in different properties are still treated as different documents
- ✅ Batch imports continue to work with partial success
- ✅ Error messages and return structures remain the same

### Backward Compatibility
- ✅ No database migrations needed
- ✅ No API changes
- ✅ Existing imported documents unaffected

## Prevention

To prevent similar issues in the future:

1. **When modifying models:** Always review related service logic for alignment
2. **When adding tracking fields:** Update all queries that use those fields
3. **Test cross-entity scenarios:** Don't just test single-property cases
4. **Document semantic changes:** Clearly explain what fields track and how they're used

## Related Files

- **Service:** `dominial/services/importacao_cadeia_service.py:55-63`
- **Model:** `dominial/models/documento_importado_models.py`
- **Tests:** `dominial/tests/test_cross_property_duplicate_prevention.py`

## Commit Message

```
Fix: Prevent cross-property chain duplicate imports

Previously, DocumentoImportado duplicate checks filtered by both
documento and imovel_origem, allowing the same document to be
imported multiple times when reached through different property
chains.

Now checks only by documento, ensuring each document is imported
exactly once regardless of which chain path discovers it.

Added comprehensive test suite covering:
- Cross-property duplicate prevention
- Batch imports with duplicates
- Correct imovel_origem recording
- Edge cases

All tests passing (6/6)
```
