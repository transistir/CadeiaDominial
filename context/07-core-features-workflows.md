# Core Features and Workflows

## Feature Overview

The system provides 10 major features organized around property ownership chain management for indigenous lands.

## 1. Indigenous Land Management

### Purpose
Register and manage indigenous territories (Terras Indígenas - TIs) that are subject to property ownership analysis.

### User Workflow

```
1. User navigates to home page
   ↓
2. Clicks "Nova Terra Indígena"
   ↓
3. Chooses option:
   a) Link to FUNAI reference data (auto-populate)
   OR
   b) Create manually
   ↓
4. Fills form:
   - Nome (name)
   - Código (unique code)
   - Etnia (indigenous people)
   - Estado(s) (state(s))
   - Área (area in hectares)
   ↓
5. Submits form
   ↓
6. System validates:
   - Unique code
   - Required fields
   ↓
7. Creates TI record
   ↓
8. Redirects to TI detail page
```

### Integration with FUNAI Data

**Reference Data Import:**
```bash
python manage.py importar_terras_indigenas
```

**Process:**
1. Fetches data from FUNAI API/database
2. Creates `TerraIndigenaReferencia` records
3. Available for linking when creating TIs
4. Auto-populates fields when linked

**Fields Auto-Populated:**
- Nome
- Código
- Etnia
- Estado
- Município
- Área (ha)
- Fase (administrative phase)
- Datas (regularizada, homologada, etc.)

---

## 2. Property Registration

### Purpose
Register properties (imóveis) within indigenous territories that have ownership documentation.

### User Workflow

```
1. From TI detail page, click "Adicionar Imóvel"
   ↓
2. Fill property form:
   - Nome (property name)
   - Matrícula (registration number - unique)
   - Tipo documento principal (matrícula/transcrição)
   - Proprietário (current owner - autocomplete)
   - Cartório (notary office - autocomplete)
   - Observações (notes)
   ↓
3. Select cartório:
   - Type city/state
   - Autocomplete suggests cartórios
   - If not found, can import or create
   ↓
4. Submit form
   ↓
5. System validates:
   - Unique matrícula
   - Proprietário exists
   - Cartório exists
   ↓
6. Creates Imovel record
   ↓
7. Redirects to property detail page
```

### Cartório Verification

**If Cartório Not Found:**

```
1. User types city/state
   ↓
2. System checks if cartórios exist for that city
   ↓
3. If no cartórios found:
   - Shows "Import Cartórios for State" button
   ↓
4. User clicks import
   ↓
5. System calls CNJ API
   ↓
6. Imports all cartórios for state
   ↓
7. User can now select from imported cartórios
```

**Manual Cartório Creation:**
```
1. Click "Create New Cartório"
   ↓
2. Fill cartório form:
   - Nome
   - CNS (unique code)
   - Cidade
   - Estado
   - Endereço, telefone, email (optional)
   ↓
3. Submit
   ↓
4. Cartório created and available for selection
```

---

## 3. Document Management

### Purpose
Create and manage property documents (matrículas and transcrições) that contain transaction records.

### Document Types

1. **Matrícula** - Modern property registration (post-1976)
2. **Transcrição** - Historical transcription (pre-1976)

### User Workflow

```
1. From property detail page, click "Novo Documento"
   ↓
2. Fill document form:
   - Tipo (matrícula/transcrição)
   - Número (document number)
   - Data (document date)
   - Cartório (notary office)
   - Livro (book number)
   - Folha (page number)
   - Origem (origin description)
   - Nível manual (hierarchy level 0-10, optional)
   - Classificação fim de cadeia (optional)
   - Sigla patrimônio público (if public property)
   ↓
3. Submit form
   ↓
4. System validates:
   - Unique (número, cartório) combination
   - Date is valid
   - Cartório exists
   ↓
5. Creates Documento record
   ↓
6. Redirects to document detail page
```

### Automatic Origin Document Creation

**When Referenced but Missing:**

```
1. User creates lançamento with origem referencing document X
   ↓
2. System parses origem text
   ↓
3. Identifies document number and cartório
   ↓
4. Searches for existing document
   ↓
5. If NOT found:
   - Offers to create automatically
   - User clicks "Create"
   ↓
6. System creates new Documento:
   - Sets cri_origem = cartório (marks as auto-created)
   - Minimal information from parsing
   ↓
7. Links to lancamento via documento_origem
   ↓
8. User can later edit to add full details
```

---

## 4. Transaction/Registration Tracking

### Purpose
Record all transactions (lançamentos) on documents: averbações, registros, and início de matrícula.

### Transaction Types

1. **Averbação** - Annotation (non-ownership changes)
   - Examples: liens, restrictions, corrections
   - Required: descricao
   - Optional: transmitente, adquirente

2. **Registro** - Registration (ownership transfers)
   - Examples: sale, donation, inheritance
   - Required: transmitente, adquirente, titulo, cartorio_transmissao
   - Optional: valor_transacao, area

3. **Início de Matrícula** - Start of registration
   - Links transcrição to matrícula
   - Required: cartorio_origem, livro_origem, folha_origem, data_origem
   - Optional: transmitente, adquirente

### User Workflow

```
1. From property detail, click "Novo Lançamento"
   ↓
2. Select document (or pre-selected)
   ↓
3. Select transaction type
   ↓
4. Form dynamically shows type-specific fields
   ↓
5. Fill required fields:

   FOR AVERBAÇÃO:
   - Data
   - Descrição
   - Observações

   FOR REGISTRO:
   - Data
   - Título (transaction type)
   - Transmitente (seller - autocomplete)
   - Adquirente (buyer - autocomplete)
   - Cartório de transmissão
   - Valor da transação (optional)
   - Área (optional)

   FOR INÍCIO DE MATRÍCULA:
   - Data
   - Cartório de origem
   - Livro de origem
   - Folha de origem
   - Data de origem
   - Transmitente/Adquirente (optional)
   ↓
6. Submit form
   ↓
7. System processes:
   a) Validates fields (LancamentoValidacaoService)
   b) Checks for duplicates (LancamentoDuplicataService)
   c) Processes fields (LancamentoCamposService)
   d) Determines origin (LancamentoOrigemService)
   e) Creates transaction (LancamentoCriacaoService)
   f) Associates people (LancamentoPessoaService)
   ↓
8. If duplicate found:
   - Shows warning
   - User can:
     a) Cancel creation
     b) Proceed anyway
     c) Edit to differentiate
   ↓
9. Creates Lancamento record
   ↓
10. Redirects to transaction detail page
```

### Person Autocomplete

**During Transaction Creation:**

```
1. User types person name in transmitente/adquirente field
   ↓
2. Autocomplete searches Pessoas table
   ↓
3. Matches by:
   - Nome (partial match)
   - CPF (if entered)
   ↓
4. Shows top 20 matches
   ↓
5. User selects or creates new:

   IF NOT FOUND:
   - Click "Add Person"
   - Quick-create modal appears
   - Fill: nome, cpf (optional)
   - Submit
   - Person created and selected
```

### Origin Processing

**Automatic Origin Detection:**

```
1. User enters origem text:
   "Matrícula 12345 do 1º CRI Salvador"
   ↓
2. System parses text (LancamentoOrigemService):
   - Identifies type: "Matrícula"
   - Extracts number: "12345"
   - Extracts cartório: "1º CRI Salvador"
   ↓
3. Searches for matching document:
   - Number = 12345
   - Cartório like "Salvador"
   ↓
4. If found:
   - Links documento_origem automatically
   ↓
5. If multiple matches:
   - Stores in session
   - User chooses correct one later
   ↓
6. If not found:
   - Offers to create automatically
```

---

## 5. Property Chain Visualization

### Purpose
Visualize complete property ownership history from origin to current state in multiple formats.

### Visualization Modes

1. **D3 Tree (Primary)** - Interactive tree diagram
2. **Table View** - Structured table format
3. **PDF Export** - Printable report
4. **Excel Export** - Spreadsheet format

### Tree Visualization Workflow

```
1. From property detail, click "Ver Cadeia Dominial"
   ↓
2. System builds tree:
   a) Gets documento_principal from imovel
   b) Calls HierarquiaArvoreService.construir_arvore_cadeia_dominial()
   c) Traverses documento_origem links backwards
   d) Builds hierarchical JSON structure
   ↓
3. Passes JSON to template
   ↓
4. D3.js renders interactive tree:
   - Nodes = documents (rectangles)
   - Links = origem relationships (curved lines)
   - Color-coded by type
   - Dynamic sizing based on transaction count
   ↓
5. User interacts:
   - Click node to see details
   - Zoom in/out
   - Pan around
   - Click "Export PDF" or "Export Excel"
```

### Origin Selection

**When Multiple Origins Exist:**

```
1. Document has multiple possible origins
   ↓
2. Tree shows all branches
   ↓
3. User clicks node with multiple origins
   ↓
4. Modal appears with origin options
   ↓
5. User selects preferred origin
   ↓
6. System stores choice in session
   ↓
7. Tree rebuilds with selected origin
   ↓
8. Choice persists for session
   ↓
9. Can clear choices to see all branches again
```

### Table View Workflow

```
1. User clicks "View as Table"
   ↓
2. System generates table (CadeiaDominialTabelaService):
   a) Gets complete chain
   b) Groups by document
   c) Lists all transactions per document
   d) Applies filters from session
   ↓
3. User can filter:
   - Document type (own, shared, all)
   - Transaction type (registros, averbações, all)
   - Sort order (date asc/desc)
   ↓
4. Filters stored in session
   ↓
5. Table updates dynamically
```

### PDF Export Workflow

```
1. User clicks "Export PDF"
   ↓
2. System generates PDF:
   a) Calls CadeiaCompletaService.obter_cadeia_completa()
   b) Gets main chain + secondary chains
   c) Calculates statistics
   d) Renders cadeia_completa_pdf.html template
   e) WeasyPrint converts HTML to PDF
   ↓
3. PDF includes:
   - TI and property information
   - Complete chain (all documents and transactions)
   - Statistics summary
   - Professional formatting
   ↓
4. Browser downloads PDF:
   "cadeia_dominial_{matricula}.pdf"
```

### Excel Export Workflow

```
1. User clicks "Export Excel"
   ↓
2. System generates Excel:
   a) Calls CadeiaCompletaService.obter_cadeia_completa()
   b) Creates openpyxl workbook
   c) Creates sheets:
      - Summary
      - Main Chain
      - Secondary Chains
   d) Formats with borders, colors, fonts
   e) Adds statistics
   ↓
3. Browser downloads Excel:
   "cadeia_dominial_{matricula}.xlsx"
```

---

## 6. Duplicate Detection

### Purpose
Prevent duplicate documents and transactions from being created, especially when importing data.

### Document Duplicate Detection

```
1. User creates document with número X, cartório Y
   ↓
2. System checks:
   - Documento.objects.filter(numero=X, cartorio=Y).exists()
   ↓
3. If exists:
   - Shows warning
   - Lists existing document(s)
   - Offers options:
     a) Cancel creation
     b) Edit to differentiate
     c) Import transactions from existing
   ↓
4. If user chooses import:
   - Copies all lançamentos from duplicate
   - Links origem documents
   - Marks original as "merged"
```

### Transaction Duplicate Detection

**Duplicate Criteria:**

**Exact Match (100%):**
- Same document
- Same type
- Same date
- Same transmitente AND adquirente
- Same valor_transacao (if present)

**Similar Match (>80%):**
- Same document
- Same type
- Date within 30 days
- Same transmitente OR adquirente
- Valor within 10% (if present)

**Workflow:**

```
1. User submits transaction form
   ↓
2. Before creation, system calls:
   LancamentoDuplicataService.verificar_duplicata()
   ↓
3. Searches for:
   a) Exact matches
   b) Similar matches
   ↓
4. If exact match found:
   - Shows error
   - Prevents creation
   - Lists duplicate
   ↓
5. If similar match found:
   - Shows warning
   - User can:
     a) Cancel
     b) Proceed anyway (with confirmation)
     c) Edit to differentiate
```

---

## 7. Advanced Search & Navigation

### Person Search

```
Feature: Search people across all transactions
Location: /pessoas/

Workflow:
1. User navigates to "Pessoas" page
   ↓
2. Can search by:
   - Nome (partial match)
   - CPF
   ↓
3. Results show:
   - Person details
   - Count of transactions as transmitente
   - Count of transactions as adquirente
   - Link to view all transactions
```

### Cartório Search

```
Feature: Search cartórios by location
Location: /cartorios/

Workflow:
1. User navigates to "Cartórios" page
   ↓
2. Can filter by:
   - Estado (state)
   - Cidade (city)
   - Nome (name)
   - CNS (code)
   ↓
3. Results show:
   - Cartório details
   - Count of documents
   - Import status (if imported)
```

### Transaction Search

```
Feature: Search all transactions
Location: /lancamentos/

Workflow:
1. User navigates to "Lançamentos" page
   ↓
2. Can filter by:
   - Tipo (averbação/registro/início)
   - Date range
   - Person (transmitente/adquirente)
   - Documento
   - TI
   ↓
3. Results show:
   - Transaction details
   - Document link
   - Property link
   - TI link
```

---

## 8. Cartório Management

### Import Cartórios by State

```
1. User needs cartório not in database
   ↓
2. Goes to import page or clicks "Import" button
   ↓
3. Selects estado (state)
   ↓
4. Clicks "Import"
   ↓
5. System:
   a) Creates ImportacaoCartorios record (status: pendente)
   b) Calls CNJ API for state
   c) Updates status to em_andamento
   d) Parses response
   e) Creates Cartorios records
   f) Updates status to concluido
   g) Records total_cartorios imported
   ↓
6. Shows success message with count
   ↓
7. Cartórios now available in autocomplete
```

### Cartório Verification

```
Feature: Validate cartório information
Service: CartorioVerificacaoService

Workflow:
1. User enters cidade, estado in form
   ↓
2. System searches for cartórios in that city
   ↓
3. If found:
   - Autocomplete shows options
   ↓
4. If not found:
   - Shows "No cartórios found for {cidade}/{estado}"
   - Offers to import or create manually
   ↓
5. CNS validation:
   - Format: XX####
   - XX = state code
   - #### = sequential number
```

---

## 9. Data Integrity & Validation

### Validation Layers

**1. Model-Level Validation:**
```python
# In models
def clean(self):
    if self.tipo == 'registro' and not self.transmitente:
        raise ValidationError("Transmitente é obrigatório para registro")
```

**2. Form-Level Validation:**
```python
# In forms
def clean(self):
    cleaned_data = super().clean()
    if cleaned_data.get('tipo') == 'registro':
        if not cleaned_data.get('transmitente'):
            raise ValidationError("Transmitente é obrigatório")
    return cleaned_data
```

**3. Service-Level Validation:**
```python
# In services
def validar_lancamento(dados):
    if dados['tipo'] == 'registro':
        if not dados.get('transmitente'):
            raise ValidationError("Transmitente é obrigatório")
```

**4. Database Constraints:**
```python
class Meta:
    unique_together = ('numero', 'cartorio')  # Prevent duplicate documents
```

### Constraint Enforcement

**1. Unique Constraints:**
- TIs.codigo - Unique territory code
- Pessoas.cpf - Unique CPF per person
- Imovel.matricula - Unique property number
- Cartorios.cns - Unique CNS code
- Documento (numero, cartorio) - Unique document per cartório

**2. Foreign Key Constraints:**
- PROTECT: Prevent deletion if referenced (most FKs)
- CASCADE: Delete children when parent deleted (Documento → Lancamento)

**3. Field Validation:**
- Date not in future
- Positive values for area, valor_transacao
- Required fields by transaction type

---

## 10. Administrative Features

### Django Admin Customization

**Access:** `/admin/`

**Customized Admin for:**

1. **Documentos:**
   - List filters: tipo, cartorio, data
   - Search: numero, cartorio__nome
   - Display: lancamento count
   - Actions: "Check for duplicates"

2. **Lancamentos:**
   - List filters: tipo, data, documento__imovel__terra_indigena_id
   - Search: documento__numero, transmitente__nome, adquirente__nome
   - Inline editing of LancamentoPessoa

3. **Cartorios:**
   - List filters: estado, cidade, tipo
   - Search: nome, cns, cidade
   - Import action by state

4. **TIs:**
   - List filters: estado, etnia
   - Search: nome, codigo
   - Display: property count, area

### Bulk Operations

**Via Management Commands:**

```bash
# Import reference data
python manage.py importar_terras_indigenas

# Import cartórios for specific state
python manage.py importar_cartorios_estado --estado BA

# Check for duplicates system-wide
python manage.py investigar_duplicatas

# Data cleanup
python manage.py corrigir_dados_inconsistentes
```

---

## Common Workflow Patterns

### Pattern 1: Create Complete Property Chain

```
1. Create TI
   ↓
2. Create Imovel linked to TI
   ↓
3. Create documento_principal (current matrícula)
   ↓
4. Create início de matrícula lançamento
   - References origem (transcrição)
   ↓
5. System creates origem document automatically
   ↓
6. Add more lançamentos to document
   ↓
7. View complete chain in tree view
```

### Pattern 2: Import Existing Property Chain

```
1. Prepare CSV/Excel with:
   - TI info
   - Property info
   - Documents info
   - Transactions info
   ↓
2. Run import command:
   python manage.py importar_cadeia_completa arquivo.csv
   ↓
3. System:
   a) Validates data
   b) Checks for duplicates
   c) Creates TI/Imovel if needed
   d) Creates all documents
   e) Creates all transactions
   f) Links origins
   ↓
4. Reports:
   - Created: X TIs, Y properties, Z documents, W transactions
   - Errors: List of validation errors
   - Duplicates: List of duplicate warnings
```

### Pattern 3: Merge Duplicate Documents

```
1. User creates document that's a duplicate
   ↓
2. System detects duplicate
   ↓
3. Shows modal with duplicate details
   ↓
4. User clicks "Merge"
   ↓
5. System:
   a) Copies all lancamentos from duplicate to new
   b) Updates documento_origem links
   c) Marks duplicate as "merged"
   d) Prevents future access to duplicate
   ↓
6. Redirects to merged document
```

---

## Error Handling Workflows

### User-Facing Errors

**Validation Errors:**
```
User submits invalid form
   ↓
System validates
   ↓
Shows field-specific errors:
- "Este campo é obrigatório"
- "CPF já cadastrado"
- "Data não pode ser futura"
   ↓
User corrects and resubmits
```

**Duplicate Errors:**
```
User creates duplicate
   ↓
System detects
   ↓
Shows warning with options:
- "Documento já existe"
- Option 1: Cancel
- Option 2: Import transactions
- Option 3: Edit to differentiate
   ↓
User chooses option
```

**Permission Errors:**
```
Unauthenticated user tries to access page
   ↓
Middleware intercepts
   ↓
Redirects to login page
   ↓
After login, redirects to original page
```

---

## Performance Considerations

### Query Optimization

**N+1 Query Prevention:**
```python
# Bad (N+1 queries)
documentos = Documento.objects.all()
for doc in documentos:
    print(doc.cartorio.nome)  # Query per document

# Good (2 queries total)
documentos = Documento.objects.select_related('cartorio').all()
for doc in documentos:
    print(doc.cartorio.nome)  # No extra query
```

### Caching Strategy

**Expensive Operations Cached:**
1. Hierarchy calculations (1 hour)
2. Tree building (1 hour)
3. Table data (30 minutes)
4. Statistics (15 minutes)

**Cache Invalidation:**
- When document created/edited
- When transaction created/edited
- When origin link changed

---

## Security Workflows

### Authentication Required

All pages except login require authentication:
```
User requests /tis/123/
   ↓
Middleware checks: user.is_authenticated
   ↓
If False:
   - Redirect to /accounts/login/?next=/tis/123/
   ↓
After successful login:
   - Redirect to /tis/123/
```

### CSRF Protection

All POST requests require CSRF token:
```html
<form method="post">
    {% csrf_token %}
    <!-- form fields -->
</form>
```

### SQL Injection Prevention

Django ORM parameterizes all queries:
```python
# Safe - parameterized
Documento.objects.filter(numero=user_input)

# Unsafe - raw SQL (avoided)
Documento.objects.raw(f"SELECT * FROM documento WHERE numero = '{user_input}'")
```

---

## Summary

The system provides comprehensive features for managing indigenous land property ownership chains with:

- **10 major feature areas**
- **Multiple visualization formats**
- **Robust duplicate detection**
- **Advanced search capabilities**
- **Data validation at all layers**
- **Administrative bulk operations**
- **Export to PDF and Excel**
- **Interactive tree visualization**
