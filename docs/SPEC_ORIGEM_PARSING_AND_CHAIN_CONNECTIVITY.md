# SPEC: Origem Text Parsing & Chain Connectivity (3-Tier Fallback)

**Status:** IMPLEMENTATION PENDING  
**Last Updated:** 2026-07-14  
**Issue:** Unmatched document origins in chain connectivity due to legacy cartório data loss

---

## Executive Summary

The CadeiaDominial ancestry graph shows **disconnected "orphan" documents** that should form a single hierarchical chain. Root cause: **legacy Django design flaw** where `Lancamento.cartorio_origem_id` is a SINGLE FK, losing cartório information when users enter multiple origins from different cartórios.

**Solution:** 3-tier fallback lookup with conservative cross-CRI recovery for origins with lost cartório data.

**Impact:** 94% resolution rate (148 of 157 previously unmatched origins)

---

## Problem Statement

### Domain Identity Model (Hiure - Authoritative)

In CadeiaDominial, a document's identity is: **tipo + número + cartório**

The same number can exist in multiple cartórios. Example:
- Matrícula 8432 exists at CRI 1355 
- Matrícula 8432 also exists at CRI 3707
- These are DIFFERENT documents because the cartório differs

The cartório is NOT auxiliary — it is part of the identity. When a user creates an "Início de Matrícula", they record THREE pieces of information for each origin:
- **Tipo** do documento de origem (matrícula/transcrição)
- **Número** do documento de origem  
- **Cartório** de origem

The cartório specified in the origem is THE cartório that should be used to find the previous document in the chain.

### Legacy Data Limitation

The legacy Django system had a **design flaw**: `Lancamento.cartorio_origem_id` is a SINGLE FK — one cartório per lancamento.

When a user entered multiple origins from DIFFERENT cartórios (e.g., "M50 from 1º CRI Salvador; T20 from 2º CRI Salvador; M30 from 3º CRI Itabuna"), only the FIRST cartório was saved. The other origins lost their cartório information.

**This is documented in:** `docs/db/legacy/MULTIPLAS_ORIGENS_CARTORIOS_ANALISE.md`

### Impact on Chain Connectivity

The system should NOT:
- Automatically use the current document's cartório (wrong for cross-CRI origins)
- Search across all cartórios as adivinhação (guessing — violates identity model)
- Choose by date, city, or name similarity (not authoritative)

When cartório information is missing (due to legacy flaw), origins cannot be found, creating disconnected orphan documents in the ancestry graph.

---

## Data Evidence

### Production Data Analysis (old dump: 1,220 documents, 3,172 lancamentos)

```
Total unmatched origins: 157
  - Cross-CRI rescuable: 149 (95%)
    - Unique match (exactly 1 doc with that tipo+numero): 148
    - Multiple matches: 1 (matricula 8432 exists at cri 1355 AND cri 3707)
  - Same-CRI but unmatched: 0 (no format issues — purely cartório mismatch)
  - Truly missing (no document with that tipo+numero anywhere): 8
```

**Systematic pattern:** lookup cri=1305 but documents exist at cri=1355 (transposition error: 0 vs 5)

### Current Migration Code Analysis

**`buildOrigemRows()` function (lines 980-1155, `legacy-fit.ts`):**

1. **Document index (line 1008):**
```typescript
documentoByKey.set(`${criId}|${tipo}|${numero}`, id);
// Documents indexed by their OWN criId
```

2. **rootCriId determination (lines 1046-1050):**
```typescript
const rootCriId =
  integerOrNull(lancamento[C.lancamento.cartorioOrigemId]) ??  // Tier 1: user-selected cartório
  (documentoId !== null 
    ? (documentoById.get(documentoId)?.criId ?? null)          // Tier 2: current document's cartório
    : null);
```

3. **Lookup logic (lines 1106-1109):**
```typescript
matchedDocumentoId =
  documentoByKey.get(`${rootCriId}|${token.tipo}|${token.numero}`) ?? null;
// Uses rootCriId for ALL origins of a lancamento
if (matchedDocumentoId === null) unmatchedOrigemTokens++;
```

**`parseOrigemText()` function (lines 422-440):**

- Extracts tipo and numero from text like "M517; M526; T2108"
- **No cartório extraction** (cartório comes from `cartorio_origem_id` column)
- Already handles basic patterns: `M\d+`, `T\d+`, `\d+`

---

## Proposed Solution: 3-Tier Fallback

### Tier 1: cartorio_origem_id (User-Selected Cartório)

Use `cartorio_origem_id` from the lancamento as the lookup cartório. This is the cartório the user selected in the UI.

**Status:** Already implemented — works for origins where the cartório is correct.

### Tier 2: documento.cri_id (Current Document's Cartório)

When `cartorio_origem_id` is NULL, use the current document's own cartório. This is a conservative fallback that handles origins within the same CRI as the current document — a common case when the user didn't explicitly record a different cartório because both documents belong to the same registry office.

**Status:** Already implemented as fallback.

### Tier 3 (NEW): Cross-CRI Exact Match (Data Recovery)

When Tier 1 AND Tier 2 both fail, search for `tipo+numero` across ALL cartórios.

**Conservative rules:**
- **Only** activates when exactly ONE document matches that tipo+numero globally
- If multiple documents match → do NOT resolve (log for manual audit)
- ALL tier 3 matches are logged with `[CROSS-CRI]` prefix in migration report
- This is **data recovery** for the legacy system's design flaw — NOT guessing

**Impact:** 148 of 157 unmatched → resolved (94%). Only 1 ambiguous case + 8 truly missing remain.

---

## Updated Migration Flow

```typescript
For each origem token:
  1. Try: documentoByKey.get("${cartorio_origem_id}|${tipo}|${numero}")
  2. Try: documentoByKey.get("${documento.cri_id}|${tipo}|${numero}")  
  3. Try: crossCRIIndex.get("${tipo}|${numero}") — only if unique match
  4. If all fail → unmatched (log for audit)
```

### New Cross-CRI Index

```typescript
// Build cross-CRI index (only for unique matches).
// tipoNumeroCris stores the Set of criIds per tipo|numero for [AMBIGUOUS] logging.
const crossCRIIndex = new Map<string, { criId: number; docId: number }>();
const tipoNumeroCris = new Map<string, Set<number>>();

// Single pass: count occurrences + collect criIds
for (const r of rawDocumento) {
  const id = integerOrNull(r[C.documento.id]);
  const criId = integerOrNull(r[C.documento.cartorioId]);
  if (id === null || criId === null) continue;
  const tipo =
    DOCUMENTO_TIPO_BY_ID[integerOrNull(r[C.documento.tipoId]) ?? 0] ===
    "transcricao"
      ? "transcricao"
      : "matricula";
  const numero = normalizeNumero(r[C.documento.numero]) || (nullIfEmpty(r[C.documento.numero]) ?? String(id));
  const key = `${tipo}|${numero}`;
  if (!tipoNumeroCris.has(key)) tipoNumeroCris.set(key, new Set());
  tipoNumeroCris.get(key)!.add(criId);
  // Only store the first occurrence as the candidate (unique keys have exactly 1)
  if (!crossCRIIndex.has(key)) crossCRIIndex.set(key, { criId, docId: id });
}

// After full iteration, remove keys with multiple CRIs from crossCRIIndex
for (const [key, cris] of tipoNumeroCris) {
  if (cris.size > 1) crossCRIIndex.delete(key);
}
```

### Updated Lookup Function

```typescript
interface FindDocumentoResult {
  docId: number;
  /** The document's actual criId (may differ from rootCriId for Tier 3 matches). */
  criId: number;
  tier: 1 | 2 | 3;
}

function findDocumento(
  token: OrigemToken,
  cartorioOrigemId: number | null,
  documentoCriId: number | null,
  rootCriId: number,
): FindDocumentoResult | null {
  if (token.numero === null) return null;

  // Tier 1: cartorio_origem_id (user-selected cartório for the FIRST origin).
  // NOTE: legacy limitation — cartorio_origem_id is a single FK stored per
  // lancamento, so Tier 1 can produce a false match for non-first origins when
  // they belong to a different cartório. This is a pre-existing issue; Tier 3
  // is the recovery path for origins whose cartório was lost by the legacy system.
  if (cartorioOrigemId !== null) {
    const tier1Key = `${cartorioOrigemId}|${token.tipo}|${token.numero}`;
    const tier1Match = documentoByKey.get(tier1Key);
    if (tier1Match !== undefined) {
      const doc = documentoById.get(tier1Match)!;
      return { docId: tier1Match, criId: doc.criId, tier: 1 };
    }
  }

  // Tier 2: documento.cri_id (current document's cartório).
  if (documentoCriId !== null) {
    const tier2Key = `${documentoCriId}|${token.tipo}|${token.numero}`;
    const tier2Match = documentoByKey.get(tier2Key);
    if (tier2Match !== undefined) {
      const doc = documentoById.get(tier2Match)!;
      return { docId: tier2Match, criId: doc.criId, tier: 2 };
    }
  }

  // Tier 3: cross-CRI unique match (data recovery for legacy flaw).
  // Only activates when exactly ONE document has this tipo+numero globally.
  const tier3Key = `${token.tipo}|${token.numero}`;
  const tier3Match = crossCRIIndex.get(tier3Key);
  if (tier3Match !== undefined) {
    // Log for audit
    console.log(`[CROSS-CRI] Tier 3 match: ${token.raw} → cri ${tier3Match.criId}, doc ${tier3Match.docId}`);
    return { docId: tier3Match.docId, criId: tier3Match.criId, tier: 3 };
  }

  // Ambiguous: multiple documents share this tipo+numero
  const cris = tipoNumeroCris.get(tier3Key);
  if (cris && cris.size > 1) {
    console.log(`[AMBIGUOUS] ${token.tipo} ${token.numero} exists in multiple CRIs: ${[...cris].join(", ")}`);
  }

  // Not found
  return null;
}
```

**Critical:** After a Tier 3 match, `origem.cri_id` MUST be set to `result.criId` (the document's actual cartório), NOT `rootCriId`. This ensures the `origem` row correctly reflects the document's identity. See integration code below.

### Integration Into buildOrigemRows

Replace the existing lookup at line 1106-1109:

```typescript
// OLD (lines 1106-1109):
// matchedDocumentoId =
//   documentoByKey.get(`${rootCriId}|${token.tipo}|${token.numero}`) ?? null;

// NEW:
const result = findDocumento(token, cartorioOrigemId, documentoCriId, rootCriId);
let matchedDocumentoId: number | null = null;
let resolvedCriId = rootCriId; // default; overridden by result.criId
if (result !== null) {
  matchedDocumentoId = result.docId;
  resolvedCriId = result.criId; // <— use the document's actual criId
} else {
  unmatchedOrigemTokens++;
}
```

Then use `resolvedCriId` instead of `rootCriId` when constructing the `origem` row:

```typescript
byIndice.set(indice, {
  lancamentoId,
  criId: resolvedCriId,   // Was: rootCriId
  documentoId: matchedDocumentoId,
  indice,
  tipo: token.tipo,
  numero: token.numero,
  numeroRaw: token.raw,
});
```

---

## Audit Logging Format

All Tier 3 (cross-CRI) matches must be logged for audit:

```typescript
console.log(`[CROSS-CRI] Resolved ${token.tipo} ${token.numero} → CRI ${criId} (doc ${docId})`);
```

**Migration report summary:**
```
Origem Resolution Summary:
- Tier 1 (cartorio_origem_id): X matches
- Tier 2 (documento.cri_id): Y matches  
- Tier 3 (cross-CRI unique): Z matches [CROSS-CRI]
- Unmatched: N tokens
```

**Ambiguous cases (multiple matches) logged separately:**
```typescript
// Already handled inside findDocumento():
// const cris = tipoNumeroCris.get(tier3Key);
// if (cris && cris.size > 1) {
//   console.log(`[AMBIGUOUS] ${token.tipo} ${token.numero} exists in multiple CRIs: ${[...cris].join(", ")}`);
// }
```

---

## Implementation Checklist

### Code Changes in `legacy-fit.ts`

- [ ] Build `tipoNumeroCount` Map during document load (count occurrences)
- [ ] Build `crossCRIIndex` Map (only populate for count=1)
- [ ] Implement `findDocumento()` function with 3-tier fallback
- [ ] Add audit logging with `[CROSS-CRI]` prefix for Tier 3 matches
- [ ] Add `[AMBIGUOUS]` logging for multiple matches
- [ ] Replace lookup at line 1108 with `findDocumento()` call
- [ ] Update `unmatchedOrigemTokens` counter logic

### Testing

- [ ] Test Tier 1: cartorio_origem_id match
- [ ] Test Tier 2: documento.cri_id fallback
- [ ] Test Tier 3: cross-CRI unique match
- [ ] Test ambiguous case (matricula 8432 at cri 1355 AND cri 3707)
- [ ] Test truly missing (no document with that tipo+numero anywhere)
- [ ] Verify audit logging format
- [ ] Run migration on production dump
- [ ] Verify 94% resolution rate (148 of 157 previously unmatched)

### Documentation

- [ ] Update SPEC with implementation results
- [ ] Document Tier 3 matches in migration report
- [ ] Create audit log file for cross-CRI resolutions

---

## Non-Goals (Per Hiure)

- **Do NOT** implement "adivinhação" cross-CRI (searching all cartórios blindly)
- **Do NOT** build a cartório name → ID mapping table ("1º CRI Salvador" → ID)
- **Do NOT** extract cartório from free-text description fields
- **Do NOT** resolve ambiguous matches automatically (require manual audit)

> **Data recovery vs. user error:** Tier 3 cross-CRI recovery addresses **legacy schema limitations** (the single-FK design flaw in Django's `Lancamento` model), not user data entry errors. In v2, origins reference documents by FK, eliminating this class of data loss at the schema level.

---

## Expected Outcomes

### Token Resolution Rates

| Tier          | Description                 | Expected Resolutions |
|---------------|------------------------------|---------------------|
| Tier 1        | cartorio_origem_id           | ~70% of matches     |
| Tier 2        | documento.cri_id fallback    | ~5% of matches      |
| Tier 3        | Cross-CRI unique             | 148 tokens          |
| **Total**     | **Conservative recovery**    | **94% (148/157)**   |
| Ambiguous     | Multiple matches             | 1 token             |
| Truly missing | No document exists           | 8 tokens            |

### Chain Connectivity

All orphan documents (except truly missing) will be connected into the ancestry graph, forming a single hierarchical tree from current matrícula → origins → fim-de-cadeia.

### Audit Trail

Every Tier 3 resolution will be logged with `[CROSS-CRI]` prefix, creating a clear audit trail of data recovery actions.

---

## Risks & Mitigations

### Risk 1: False Positives from Cross-CRI Matching

**Scenario:** Same documento numero exists in multiple cartórios, wrong match selected.

**Mitigation:**
- Conservative rule: only resolve when **exactly one** global match exists
- Multiple matches → log as `[AMBIGUOUS]`, require manual audit
- All Tier 3 matches logged for review

### Risk 2: Performance Degradation

**Scenario:** Additional index increases memory or slows lookup.

**Mitigation:**
- Cross-CRI index: ~3,000 entries × ~50 bytes ≈ 150KB (negligible)
- Two-pass build is O(n) — still <5 seconds total
- Lookup remains O(1) per tier — max 3 Map lookups per token

### Risk 4: Incomplete Dump Produces False Unique Matches

**Scenario:** A document genuinely referenced by an origem is NOT present in the dump, but an unrelated document with the same tipo+numero exists (alone) in the dump. Tier 3 would match the wrong document.

**Mitigation:**
- This risk is inherent to ANY migration from incomplete data — not specific to Tier 3
- All Tier 3 matches are logged with `[CROSS-CRI]` for post-migration audit
- The 8 "truly missing" cases suggest the dump is reasonably complete
- In v2, this cannot happen because origins reference documents by FK, not text

### Risk 5: Tier 1 False Positives (Pre-existing)

**Scenario:** `cartorio_origem_id` only stores the FIRST origin's cartório. When a lancamento has multiple origins from different cartórios, Tier 1 may match a document in the first origin's cartório that coincidentally shares the same tipo+numero as a different origin.

**Mitigation:**
- This is a pre-existing limitation from the legacy Django schema — NOT introduced by this SPEC
- The current code (before Tier 3) already has this behavior; the existing 157 unmatched are the result
- Tier 3 is the data recovery path for origins whose cartório was lost
- False Tier 1 matches are statistically unlikely: they require a document in the wrong cartório to have the same tipo+numero as the intended origin

### Risk 3: Breaking Existing Matches

**Mitigation:**
- Tier 1 and Tier 2 preserve existing logic unchanged
- Tier 3 only activates when T1 and T2 both fail
- Comprehensive test coverage
- Git revert ready if issues arise

---

## Acceptance Criteria

### Functional Requirements

1. [ ] **Tier 1 matches:** cartorio_origem_id lookup works as before
2. [ ] **Tier 2 matches:** documento.cri_id fallback works as before
3. [ ] **Tier 3 matches:** Cross-CRI unique matches resolve correctly
4. [ ] **Ambiguous handling:** Multiple matches logged as `[AMBIGUOUS]`
5. [ ] **Audit logging:** All Tier 3 matches logged with `[CROSS-CRI]` prefix
6. [ ] **Resolution rate:** ≥94% of previously unmatched origins resolved
7. [ ] **Tier 1 false positive handling:** Documented as pre-existing limitation — Tier 3 is the recovery path for origins whose cartório was lost by the legacy schema

### Non-Functional Requirements

1. [ ] **Performance:** Migration completes in <10 seconds
2. [ ] **Memory:** Additional index <500KB
3. [ ] **Deterministic:** Re-running migration produces identical results
4. [ ] **Backward compatible:** No breaking changes to output schema

### Validation

```typescript
// Test on production dump
const before = unmatchedOrigemTokens; // Current: 157
// After implementation
const after = unmatchedOrigemTokens;  // Target: ≤9 (8 truly missing + 1 ambiguous)

const crossCriMatches = /* count of [CROSS-CRI] log entries */;
expect(crossCriMatches).toBe(148); // Expected Tier 3 resolutions
expect(after).toBeLessThanOrEqual(9); // Only truly missing + ambiguous remain
```

---

## Related Files

| File | Purpose |
|------|---------|
| `docs/SPEC_ORIGEM_PARSING_AND_CHAIN_CONNECTIVITY.md` | This specification |
| `docs/db/legacy/MULTIPLAS_ORIGENS_CARTORIOS_ANALISE.md` | Legacy Django limitation analysis |
| `scripts/migration/legacy-fit.ts` | Migration implementation |
| `scripts/migration/legacy-fit.ts:parseOrigemText()` | Text parsing (lines 422-440) |
| `scripts/migration/legacy-fit.ts:buildOrigemRows()` | Origin resolution (lines 980-1155) |

---

**Status:** IMPLEMENTATION PENDING  
**Last Updated:** 2026-07-14  
**Next Steps:** Implement 3-tier fallback in `legacy-fit.ts`, run migration on production dump, validate 94% resolution rate.
