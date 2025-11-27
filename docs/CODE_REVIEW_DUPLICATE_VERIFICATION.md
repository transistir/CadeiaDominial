# Code Review: Duplicate Verification and MultipleObjectsReturned Risks

**Date:** 2025-11-18
**Reviewer:** AI Code Review
**Scope:** Duplicate verification services and potential MultipleObjectsReturned exceptions

---

## Executive Summary

This code review was conducted following the fix for a `MultipleObjectsReturned` bug in the duplicate verification flow. The review identified **2 additional risk areas** where similar issues could occur, along with several code quality observations.

### Key Findings

✅ **Fixed:** Duplicate reconstruction in `LancamentoDuplicataService` (commit 4aaa5e0)
⚠️ **Risk:** Cartório lookups by name could raise `MultipleObjectsReturned`
⚠️ **Risk:** DocumentoTipo lookups assume uniqueness without database constraint
✅ **Good:** Import service uses proper duplicate prevention logic
✅ **Good:** Defensive coding patterns in place for API contract variations

---

## 1. Fixed Issues

### 1.1 MultipleObjectsReturned in Duplicate Reconstruction ✅ FIXED

**Location:** `dominial/services/lancamento_duplicata_service.py:82-84`

**Issue:** The duplicate verification flow was serializing documents and reconstructing them using `.get(numero=..., cartorio_id=...)`, which raised `MultipleObjectsReturned` when multiple documents existed with the same number in the same cartório.

**Fix Applied:**
```python
# BEFORE (BROKEN)
documento_origem = Documento.objects.get(
    numero=duplicata_info['documento']['numero'],
    cartorio_id=cartorio_origem.id
)

# AFTER (FIXED)
documento_origem = Documento.objects.get(
    id=duplicata_info['documento']['id']
)
```

**Root Cause:**
- `Documento` model has `unique_together = ('numero', 'cartorio')` constraint
- However, the constraint may not be enforced on legacy data or in edge cases
- Using `.get()` with non-unique fields is inherently risky

**Resolution:**
- Added document `id` to serialized response in `DuplicataVerificacaoService`
- Changed reconstruction to use primary key lookup
- Guarantees exact document match

---

## 2. Potential Issues Identified

### 2.1 Cartório Lookups by Name ⚠️ MEDIUM RISK

**Locations:** 8 occurrences across 3 service files

#### Affected Files:
1. `dominial/services/lancamento_origem_service.py:238`
2. `dominial/services/lancamento_campos_service.py:67`
3. `dominial/services/lancamento_campos_service.py:104`
4. `dominial/services/lancamento_campos_service.py:136`
5. `dominial/services/lancamento_campos_service.py:218`
6. `dominial/services/lancamento_form_service.py:66`
7. `dominial/services/lancamento_form_service.py:148`
8. `dominial/services/lancamento_form_service.py:195`

#### Issue Pattern:
```python
try:
    cartorio = Cartorios.objects.get(nome__iexact=cartorio_nome)
except Cartorios.DoesNotExist:
    # Handle not found
```

#### Problem:
- `Cartorios` model has unique constraint on `cns` but **NOT on `nome`**
- Multiple cartórios could have the same name (especially in different states/cities)
- Code catches `DoesNotExist` but NOT `MultipleObjectsReturned`
- If multiple cartórios exist with same name, exception propagates uncaught

#### Risk Assessment:
- **Likelihood:** Medium (depends on data quality)
- **Impact:** High (breaks transaction creation flow)
- **User Experience:** 500 error instead of helpful message

#### Recommended Fix:
```python
try:
    # Option 1: Use filter().first() for graceful fallback
    cartorio = Cartorios.objects.filter(nome__iexact=cartorio_nome).first()
    if not cartorio:
        # Handle not found

    # Option 2: Catch MultipleObjectsReturned explicitly
    cartorio = Cartorios.objects.get(nome__iexact=cartorio_nome)
except Cartorios.DoesNotExist:
    # Handle not found
except Cartorios.MultipleObjectsReturned:
    # Log warning and use first match or show error to user
    cartorio = Cartorios.objects.filter(nome__iexact=cartorio_nome).first()
    logger.warning(f"Multiple cartórios found with name: {cartorio_nome}")
```

#### Additional Context:
- Model definition (`dominial/models/imovel_models.py:46-73`):
  ```python
  class Cartorios(models.Model):
      nome = models.CharField(max_length=200)  # No unique constraint
      cns = models.CharField(max_length=20, unique=True)
  ```
- Should consider adding compound unique constraint: `unique_together = ('nome', 'estado', 'cidade')`

---

### 2.2 DocumentoTipo Lookups Assume Uniqueness ⚠️ LOW RISK

**Locations:** 10 occurrences across 3 service files

#### Affected Files:
1. `dominial/services/hierarquia_arvore_service.py:220, 222`
2. `dominial/services/hierarquia_origem_service.py:90`
3. `dominial/services/lancamento_origem_service.py:132, 136, 142, 146, 152, 258, 375`

#### Issue Pattern:
```python
tipo_doc = DocumentoTipo.objects.get(tipo='matricula')
tipo_doc = DocumentoTipo.objects.get(tipo='transcricao')
```

#### Problem:
- `DocumentoTipo` model has `TIPO_CHOICES` but no unique constraint on `tipo` field
- If database contains duplicate tipo values, `.get()` will raise `MultipleObjectsReturned`
- No exception handling for this case

#### Risk Assessment:
- **Likelihood:** Very Low (data should be controlled, only 2 valid choices)
- **Impact:** Medium (breaks document creation)
- **User Experience:** 500 error

#### Model Definition (`dominial/models/documento_models.py:5-18`):
```python
class DocumentoTipo(models.Model):
    TIPO_CHOICES = [
        ('transcricao', 'Transcrição'),
        ('matricula', 'Matrícula')
    ]
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)  # No unique constraint
```

#### Recommended Fix:
**Option 1: Add Database Constraint (Preferred)**
```python
class DocumentoTipo(models.Model):
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, unique=True)
```

**Option 2: Cache Lookups**
```python
# In service layer
_tipo_cache = {}

def get_documento_tipo(tipo_name):
    if tipo_name not in _tipo_cache:
        _tipo_cache[tipo_name] = DocumentoTipo.objects.get(tipo=tipo_name)
    return _tipo_cache[tipo_name]
```

**Option 3: Use get_or_create (Defensive)**
```python
tipo_doc, _ = DocumentoTipo.objects.get_or_create(
    tipo='matricula',
    defaults={'tipo': 'matricula'}
)
```

---

## 3. Code Quality Observations

### 3.1 Cross-Property Duplicate Prevention ✅ GOOD

**Location:** `dominial/services/importacao_cadeia_service.py:59-63`

**Pattern:**
```python
# Verificar se já não foi importado (de qualquer propriedade)
# Correção: verifica apenas pelo documento, não pelo imovel_origem
if DocumentoImportado.objects.filter(
    documento=documento
).exists():
    erros.append(f"Documento {documento.numero} já foi importado")
    continue
```

**Analysis:**
- ✅ Correctly prevents duplicate imports from different chain paths
- ✅ Uses `.filter().exists()` instead of `.get()` - more robust
- ✅ Clear comment explaining the logic
- ✅ Previously fixed in earlier session

---

### 3.2 Defensive API Contract Handling ✅ GOOD

**Location:** `dominial/services/lancamento_duplicata_service.py:212-235`

**Pattern:**
```python
# DEFENSIVE: Handle both old (list) and new (dict with 'documentos' key) formats
if isinstance(cadeia_dominial_raw, dict):
    logger.warning("DEFENSIVE: cadeia_dominial is dict (new format)")
    cadeia_dominial = cadeia_dominial_raw.get('documentos', [])
elif isinstance(cadeia_dominial_raw, list):
    logger.info("DEFENSIVE: cadeia_dominial is list (expected)")
    cadeia_dominial = cadeia_dominial_raw
else:
    logger.error("DEFENSIVE: Unexpected cadeia_dominial type")
    cadeia_dominial = []
```

**Analysis:**
- ✅ Excellent defensive coding pattern
- ✅ Comprehensive logging for debugging
- ✅ Graceful fallback to empty list
- ✅ Prevents template crashes from API contract changes

---

### 3.3 Transaction Atomicity ✅ GOOD

**Location:** `dominial/services/importacao_cadeia_service.py:37`

**Pattern:**
```python
with transaction.atomic():
    # Import operations
```

**Analysis:**
- ✅ Proper use of database transactions
- ✅ Ensures data integrity during multi-step imports
- ✅ All-or-nothing behavior prevents partial imports

---

## 4. Recommendations

### 4.1 Immediate Actions (High Priority)

1. **Fix Cartório Lookup Risk**
   - Add exception handling for `MultipleObjectsReturned` in 8 locations
   - Consider adding compound unique constraint to `Cartorios` model
   - Estimated effort: 2-3 hours

2. **Add Unique Constraint to DocumentoTipo**
   - Add `unique=True` to `tipo` field
   - Create migration
   - Verify no duplicate data exists first
   - Estimated effort: 30 minutes

### 4.2 Medium-Term Improvements

3. **Standardize .get() Usage Pattern**
   - Create service method wrapper for safe `.get()` operations
   - Document when to use `.get()` vs `.filter().first()`
   - Add to coding guidelines

4. **Add Integration Tests**
   - Test duplicate cartório names scenario
   - Test multiple DocumentoTipo records with same tipo
   - Test all recent bug fixes together

### 4.3 Long-Term Enhancements

5. **Consider Caching Strategy**
   - Cache frequently-accessed reference data (DocumentoTipo, Cartorios)
   - Reduce database queries
   - Improve performance

6. **Add Monitoring**
   - Log all `MultipleObjectsReturned` exceptions
   - Alert on data integrity issues
   - Track duplicate prevention effectiveness

---

## 5. Testing Recommendations

### 5.1 Unit Tests Needed

```python
# Test: Multiple cartórios with same name
def test_multiple_cartorios_same_name():
    """Verify graceful handling when multiple cartórios share name"""
    # Create 2 cartórios with same name
    # Attempt lancamento creation
    # Assert: Should not crash, should log warning

# Test: Duplicate DocumentoTipo records
def test_duplicate_documento_tipo():
    """Verify handling of duplicate DocumentoTipo records"""
    # Create duplicate 'matricula' records
    # Attempt document creation
    # Assert: Should use get_or_create or handle exception
```

### 5.2 Integration Tests Needed

```python
# Test: End-to-end duplicate import prevention
def test_cross_property_chain_duplicate_prevention():
    """Verify documents can't be imported twice via different chains"""
    # Already exists in test_cross_property_duplicate_prevention.py
    # Verify still passing after all recent changes

# Test: Complete duplicate verification flow
def test_duplicate_verification_with_multiple_origins():
    """Test duplicate detection with MultipleObjectsReturned scenarios"""
    # Create duplicate documents with same numero/cartorio
    # Verify duplicate detection still works
    # Assert: Should return proper warning, not crash
```

---

## 6. Code Metrics

### Services Analyzed
- `duplicata_verificacao_service.py` (229 lines)
- `lancamento_duplicata_service.py` (312 lines)
- `importacao_cadeia_service.py` (239 lines)
- `lancamento_origem_service.py` (517 lines)
- `lancamento_campos_service.py` (352 lines)
- `lancamento_form_service.py` (400+ lines)
- `hierarquia_arvore_service.py` (351 lines)

### Issues Found
- **Critical:** 0 (1 was fixed in commit 4aaa5e0)
- **High:** 1 (Cartório lookup by name)
- **Medium:** 0
- **Low:** 1 (DocumentoTipo uniqueness)
- **Code Quality Observations:** 3 positive patterns identified

### Lines of Code Reviewed
- **Total:** ~2,600 lines across 7 service files
- **Focus Areas:** ORM queries using `.get()`, duplicate prevention logic, exception handling

---

## 7. Conclusion

The codebase demonstrates several strong patterns including defensive coding, transaction atomicity, and clear duplicate prevention logic. The recent fix for `MultipleObjectsReturned` in duplicate reconstruction was well-executed.

However, **8 instances of Cartório lookup by name** present a moderate risk of similar exceptions. Adding proper exception handling would significantly improve robustness.

The `DocumentoTipo` uniqueness issue is low-risk but should be addressed to prevent future data integrity problems.

Overall code quality is **good** with room for improvement in defensive `.get()` usage patterns.

---

## Appendix A: All `.get()` Calls Analyzed

### Safe `.get()` Calls (Primary Key Lookups)
- `Imovel.objects.get(id=...)` - 2 occurrences ✅
- `Documento.objects.get(id=...)` - 4 occurrences ✅
- `User.objects.get(id=...)` - 2 occurrences ✅
- `DocumentoImportado.objects.get(id=...)` - 1 occurrence ✅

### Safe `.get()` Calls (Unique Fields)
- `Cartorios.objects.get(id=...)` - 3 occurrences ✅
- `request.POST.get(...)` - Many occurrences (not ORM) ✅

### Potentially Unsafe `.get()` Calls
- `Cartorios.objects.get(nome__iexact=...)` - 8 occurrences ⚠️
- `DocumentoTipo.objects.get(tipo=...)` - 10 occurrences ⚠️

### Fixed `.get()` Calls
- `Documento.objects.get(numero=..., cartorio_id=...)` - Was 1 occurrence, now fixed ✅

---

**Review Completed:** 2025-11-18
**Next Review Recommended:** After implementing Cartório exception handling
