# Services and Business Logic

## ⚠️ v2 Cleanup Changes (PR #11)

**Service Layer Status:**

- The `hierarquia_arvore_service.py` file was **removed** from the main codebase as part of the v2 branch cleanup
- The final version of this service (351 lines) can be found in `old/dominial/services/hierarquia_arvore_service.py`
- Related backup files (`_backup.py`, `_corrigido.py`, `_melhorado.py`) were also moved to `old/`

**What Was Removed:**

- `dominial/services/hierarquia_arvore_service.py` - Main tree building service
- `dominial/services/hierarquia_arvore_service_backup.py` - Backup version
- `dominial/services/hierarquia_arvore_service_corrigido.py` - Corrected version
- `dominial/services/hierarquia_arvore_service_melhorado.py` - Improved version

**Rationale:**
These files were experimental versions created during development. The production code was consolidated into the main service file, which has been moved to `old/` as part of the Django → TypeScript migration.

## Service Layer Overview

The system implements a **Service Layer Pattern** where all complex business logic is extracted from views into specialized service classes. This provides:

- **Separation of Concerns**: Views handle HTTP, services handle business logic
- **Reusability**: Services can be used by multiple views
- **Testability**: Business logic can be tested independently
- **Maintainability**: Complex operations are isolated and well-organized

## Service Organization

**Note:** Services were located in `/dominial/services/` before the v2 cleanup. As of PR #11, the entire Django codebase has been moved to `old/`.

**Original Structure:**

```
old/dominial/services/
├── Hierarchy & Chain Services (7 files → 4 after cleanup)
├── Transaction Services (12 files)
├── Document Services (3 files)
├── Supporting Services (6 files)
└── Backup/Archive Files (3 files - removed)
```

**Removed in PR #11:**

- `hierarquia_arvore_service.py` (351 lines) - Tree building service
- `hierarquia_arvore_service_backup.py` - Backup version
- `hierarquia_arvore_service_corrigido.py` - Corrected version
- `hierarquia_arvore_service_melhorado.py` - Improved version

Total: **30+ service files** → **26 active services** after cleanup (~7,000 lines of business logic)

## Core Service Categories

### 1. Hierarchy & Chain Services

These services build and manage the property ownership chain (cadeia dominial).

#### HierarquiaService

**File:** `dominial/services/hierarquia_service.py`

**Purpose:** Core hierarchy calculations for property ownership chains.

**Key Methods:**

- `obter_tronco_principal(documento)` - Get main property chain
- `obter_troncos_secundarios(documento)` - Get secondary/branch chains
- `validar_hierarquia(documento)` - Validate chain integrity
- `calcular_nivel_documento(documento)` - Calculate hierarchy level

**Usage:**

```python
from dominial.services.hierarquia_service import HierarquiaService

# Get main chain for a document
tronco_principal = HierarquiaService.obter_tronco_principal(documento)

# Get all secondary chains
troncos_secundarios = HierarquiaService.obter_troncos_secundarios(documento)
```

**Algorithm:**

1. Start with current document
2. Follow `lancamento.documento_origem` links backwards
3. Build tree structure of ownership transfers
4. Calculate levels for visualization

---

#### HierarquiaArvoreService ~~(Removed in PR #11)~~

**Status:** REMOVED - Code moved to `old/dominial/services/`

**Original File:** `dominial/services/hierarquia_arvore_service.py` (351 lines)

**Purpose:** Built tree structure for D3.js visualization.

**⚠️ Note:** This service was removed from the main codebase during the v2 cleanup (PR #11). The final version can be found in:

- `old/dominial/services/hierarquia_arvore_service.py` - Main service (351 lines)
- `old/dominial/services/hierarquia_arvore_service_backup.py` - Backup version
- `old/dominial/services/hierarquia_arvore_service_corrigido.py` - Corrected version
- `old/dominial/services/hierarquia_arvore_service_melhorado.py` - Improved version

**Original Key Methods:**

- `construir_arvore_cadeia_dominial(documento_id, origens_escolhidas=None)` - Main tree builder
- `processar_origens_identificadas(documento)` - Process automatic origin detection
- `construir_no_documento(documento)` - Build a single tree node
- `construir_no_fim_cadeia(tipo, classificacao)` - Build end-of-chain node

**Migration Note:** The tree building logic needs to be reimplemented in the new TypeScript stack using React-based visualization (see [../ARCHITECTURE_DECISIONS.md](../ARCHITECTURE_DECISIONS.md) - PD-001: Tree Visualization Library).

---

#### CadeiaDominialTabelaService

**File:** `dominial/services/cadeia_dominial_tabela_service.py` (554 lines - largest service)

**Purpose:** Generates table format view of property chain with complex filtering.

**Key Methods:**

- `obter_dados_tabela(documento_id, filtros)` - Main table data generator
- `aplicar_filtros(documentos, filtros)` - Apply user-selected filters
- `agrupar_por_documento(lancamentos)` - Group transactions by document
- `calcular_estatisticas(dados)` - Calculate summary statistics

**Features:**

- Session-based filter persistence
- Document grouping
- Transaction sorting
- Statistical aggregation
- Multiple view options (all documents, own only, shared only)

**Filter Options:**

```python
filtros = {
    'mostrar_documentos': 'todos',  # 'todos', 'proprios', 'compartilhados'
    'mostrar_lancamentos': 'todos',  # 'todos', 'registros', 'averbacoes'
    'ordenacao': 'data_desc',  # 'data_asc', 'data_desc', 'numero_asc'
}
```

**Usage:**

```python
from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService

# Get table data with filters
dados = CadeiaDominialTabelaService.obter_dados_tabela(
    documento_id=123,
    filtros={'mostrar_documentos': 'proprios'}
)
```

---

#### CadeiaCompletaService

**File:** `dominial/services/cadeia_completa_service.py` (423 lines)

**Purpose:** Combines all chain data for comprehensive reports (PDF, Excel).

**Key Methods:**

- `obter_cadeia_completa(documento_id)` - Get complete chain data
- `obter_tronco_principal_com_lancamentos(documento)` - Main chain with transactions
- `obter_troncos_secundarios_com_lancamentos(documento)` - Secondary chains
- `calcular_estatisticas_cadeia(dados)` - Calculate chain statistics

**Output Structure:**

```python
{
    'documento_principal': Documento,
    'tronco_principal': [
        {
            'documento': Documento,
            'lancamentos': [Lancamento, Lancamento, ...],
            'nivel': 0
        },
        ...
    ],
    'troncos_secundarios': [
        {
            'documento': Documento,
            'lancamentos': [...],
            'nivel': 1
        },
        ...
    ],
    'estatisticas': {
        'total_documentos': 15,
        'total_lancamentos': 48,
        'total_registros': 12,
        'total_averbacoes': 36,
        'profundidade_maxima': 5
    }
}
```

**Usage:**

```python
from dominial.services.cadeia_completa_service import CadeiaCompletaService

# Get complete chain for PDF/Excel export
cadeia_completa = CadeiaCompletaService.obter_cadeia_completa(documento_id=123)
```

---

#### HierarquiaOrigemService

**File:** `dominial/services/hierarquia_origem_service.py`

**Purpose:** Handles origin detection and selection logic.

**Key Methods:**

- `detectar_origens_automaticas(lancamento)` - Automatically detect origin documents
- `processar_escolha_origem(lancamento_id, origem_escolhida)` - Process user origin selection
- `validar_origem(documento_origem, documento_atual)` - Validate origin relationship

**Origin Detection Algorithm:**

1. Parse `lancamento.origem` field for document references
2. Search for matching documents by number and cartório
3. Return list of candidates
4. Store in session for user choice
5. Create `documento_origem` link when chosen

---

### 2. Transaction (Lançamento) Services

These services handle the complex creation, validation, and management of property transactions.

#### LancamentoCriacaoService

**File:** `dominial/services/lancamento_criacao_service.py` (423 lines)

**Purpose:** Orchestrates the complete transaction creation workflow.

**Key Methods:**

- `criar(dados, documento_id)` - Main creation method (orchestrator)
- `validar_dados(dados)` - Validate input data
- `verificar_duplicatas(dados)` - Check for duplicate transactions
- `processar_campos(dados, tipo)` - Process type-specific fields
- `criar_lancamento(dados_processados)` - Create database record
- `associar_pessoas(lancamento, dados)` - Link people to transaction

**Creation Workflow:**

```
1. Validate input data (LancamentoValidacaoService)
   ↓
2. Check for duplicates (LancamentoDuplicataService)
   ↓
3. Process fields by type (LancamentoCamposService)
   ↓
4. Determine origin (LancamentoOrigemService)
   ↓
5. Create Lancamento record
   ↓
6. Associate people (LancamentoPessoaService)
   ↓
7. Link origin document if applicable
   ↓
8. Return created Lancamento
```

**Usage:**

```python
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService

# Create new transaction
lancamento = LancamentoCriacaoService.criar(
    dados=form.cleaned_data,
    documento_id=123
)
```

---

#### LancamentoOrigemService

**File:** `dominial/services/lancamento_origem_service.py` (517 lines - 2nd largest service)

**Purpose:** Complex origin determination logic for property chains.

**Key Methods:**

- `processar_origem(lancamento, dados)` - Main origin processor
- `identificar_documento_origem(texto_origem, cartorio)` - Parse origin text
- `buscar_documento_origem(numero, cartorio)` - Search for origin document
- `criar_documento_origem_automatico(dados)` - Auto-create missing origin docs
- `validar_origem_circular(documento_origem, documento_atual)` - Prevent circular references

**Origin Identification Patterns:**

- Matrícula patterns: "M 12345", "Mat. 12345", "Matrícula 12345"
- Transcrição patterns: "T 999", "Trans. 999", "Transcrição 999"
- Livro/Folha patterns: "Livro 3, Folha 45"
- Cartório references: "1º CRI Salvador", "CRI Salvador"

**Automatic Origin Document Creation:**
When origin document doesn't exist but is referenced:

1. Parse origin information from text
2. Create new Documento record
3. Mark with `cri_origem` for tracking
4. Link to current transaction via `documento_origem`

**Usage:**

```python
from dominial.services.lancamento_origem_service import LancamentoOrigemService

# Process origin for a transaction
LancamentoOrigemService.processar_origem(
    lancamento=lancamento,
    dados={'origem': 'Matrícula 12345 do 1º CRI Salvador'}
)
```

---

#### LancamentoCamposService

**File:** `dominial/services/lancamento_campos_service.py` (352 lines)

**Purpose:** Dynamic field processing based on transaction type.

**Key Methods:**

- `obter_campos_obrigatorios(tipo_lancamento)` - Get required fields for type
- `obter_campos_opcionais(tipo_lancamento)` - Get optional fields
- `processar_campos_tipo(dados, tipo)` - Process type-specific fields
- `validar_campos_requeridos(dados, tipo)` - Validate required fields present

**Field Requirements by Type:**

**Averbação (Annotation):**

- Required: `tipo`, `data`, `descricao`
- Optional: `transmitente`, `adquirente`, `observacoes`

**Registro (Registration):**

- Required: `tipo`, `data`, `titulo`, `transmitente`, `adquirente`, `cartorio_transmissao`
- Optional: `valor_transacao`, `area`, `observacoes`

**Início de Matrícula (Start of Registration):**

- Required: `tipo`, `data`, `cartorio_origem`, `livro_origem`, `folha_origem`, `data_origem`
- Optional: `transmitente`, `adquirente`, `forma`, `titulo`, `area`

**Usage:**

```python
from dominial.services.lancamento_campos_service import LancamentoCamposService

# Get required fields
campos_obrigatorios = LancamentoCamposService.obter_campos_obrigatorios(
    tipo_lancamento='registro'
)

# Process fields for transaction type
dados_processados = LancamentoCamposService.processar_campos_tipo(
    dados=form.cleaned_data,
    tipo='averbacao'
)
```

---

#### LancamentoValidacaoService

**File:** `dominial/services/lancamento_validacao_service.py`

**Purpose:** Field validation beyond Django form validation.

**Key Methods:**

- `validar_lancamento(dados, tipo)` - Main validation orchestrator
- `validar_datas(dados)` - Validate dates are logical
- `validar_valores(dados)` - Validate numeric values
- `validar_pessoas(dados)` - Validate person references
- `validar_cartorios(dados)` - Validate cartório references
- `validar_origem(dados)` - Validate origin information

**Validation Rules:**

- Date cannot be in future
- Transaction date cannot be before document date
- Value must be positive if provided
- At least one person required for registrations
- Cartório must exist and be active
- Origin format must be parseable

---

#### LancamentoDuplicataService

**File:** `dominial/services/lancamento_duplicata_service.py` (252 lines)

**Purpose:** Sophisticated duplicate detection for transactions.

**Key Methods:**

- `verificar_duplicata(dados, documento_id)` - Main duplicate checker
- `encontrar_duplicatas_exatas(dados)` - Exact duplicate matching
- `encontrar_duplicatas_similares(dados)` - Fuzzy matching
- `calcular_similaridade(lanc1, lanc2)` - Similarity score (0-100%)

**Duplicate Detection Criteria:**

**Exact Match (100% duplicate):**

- Same document
- Same type
- Same date
- Same transmitter AND acquirer
- Same transaction value (if present)

**Similar Match (>80% similarity):**

- Same document
- Same type
- Date within 30 days
- Same transmitter OR acquirer
- Value within 10% (if present)

**Usage:**

```python
from dominial.services.lancamento_duplicata_service import LancamentoDuplicataService

# Check for duplicates before creating
duplicatas = LancamentoDuplicataService.verificar_duplicata(
    dados=form.cleaned_data,
    documento_id=123
)

if duplicatas['exatas']:
    raise ValidationError("Lançamento duplicado encontrado")
```

---

#### LancamentoPessoaService

**File:** `dominial/services/lancamento_pessoa_service.py`

**Purpose:** Manages multiple people associations with transactions.

**Key Methods:**

- `associar_transmitentes(lancamento, pessoas)` - Link sellers
- `associar_adquirentes(lancamento, pessoas)` - Link buyers
- `remover_pessoas(lancamento)` - Clear person associations
- `atualizar_pessoas(lancamento, dados)` - Update person associations

**Supports:**

- Single person per transaction (legacy)
- Multiple people per transaction (via LancamentoPessoa)
- Percentage ownership (future feature)
- Person creation on-the-fly if doesn't exist

---

#### LancamentoConsultaService

**File:** `dominial/services/lancamento_consulta_service.py`

**Purpose:** Complex queries for transactions.

**Key Methods:**

- `buscar_por_pessoa(pessoa_id)` - Find all transactions for a person
- `buscar_por_periodo(data_inicio, data_fim)` - Date range search
- `buscar_por_tipo(tipo)` - Filter by transaction type
- `buscar_com_origem(documento_id)` - Find transactions linking to document
- `obter_estatisticas(filters)` - Aggregate statistics

---

#### LancamentoFormService

**File:** `dominial/services/lancamento_form_service.py`

**Purpose:** Form data processing and preparation.

**Key Methods:**

- `preparar_dados_iniciais(lancamento)` - Prepare form initial data for edit
- `processar_form_data(post_data)` - Process submitted form data
- `limpar_campos_nao_utilizados(dados, tipo)` - Remove unused fields for type

---

#### LancamentoDocumentoService

**File:** `dominial/services/lancamento_documento_service.py`

**Purpose:** Manages relationship between transactions and documents.

**Key Methods:**

- `obter_lancamentos_documento(documento_id)` - Get all transactions for document
- `contar_lancamentos(documento_id)` - Count transactions
- `obter_primeiro_lancamento(documento_id)` - Get first transaction chronologically
- `obter_ultimo_lancamento(documento_id)` - Get most recent transaction

---

#### LancamentoService (Legacy)

**File:** `dominial/services/lancamento_service.py` (234 lines)

**Purpose:** Legacy service - being replaced by specialized services above.

**Status:** Deprecated - functionality split into specialized services

---

#### LancamentoHerancaService

**File:** `dominial/services/lancamento_heranca_service.py`

**Purpose:** Handles inheritance-related transactions (special case).

**Key Methods:**

- `processar_heranca(lancamento, dados_heranca)` - Process inheritance details
- `validar_heranca(dados)` - Validate inheritance data
- `calcular_percentuais_heranca(herdeiros)` - Calculate inheritance percentages

---

### 3. Document Services

#### DocumentoService

**File:** `dominial/services/documento_service.py` (230 lines)

**Purpose:** Basic document operations (CRUD).

**Key Methods:**

- `criar_documento(dados)` - Create new document
- `atualizar_documento(documento_id, dados)` - Update document
- `buscar_documento(numero, cartorio)` - Find document
- `listar_documentos_imovel(imovel_id)` - Get all documents for property

---

#### DocumentoService_Consolidado

**File:** `dominial/services/documento_service_consolidado.py` (230 lines)

**Purpose:** Consolidated document queries with related data.

**Key Methods:**

- `obter_documento_completo(documento_id)` - Get document with all relationships
- `obter_documentos_com_lancamentos(imovel_id)` - Documents with transaction counts
- `obter_documentos_com_estatisticas()` - Documents with aggregate statistics

**Returns:**

```python
{
    'documento': Documento,
    'imovel': Imovel,
    'ti': TIs,
    'lancamentos': [Lancamento, ...],
    'total_lancamentos': 15,
    'total_registros': 5,
    'total_averbacoes': 10,
    'primeiro_lancamento': Lancamento,
    'ultimo_lancamento': Lancamento
}
```

---

### 4. Supporting Services

#### DuplicataVerificacaoService

**File:** `dominial/services/duplicata_verificacao_service.py`

**Purpose:** System-wide duplicate verification (documents and transactions).

**Key Methods:**

- `verificar_documento_duplicado(numero, cartorio)` - Check document duplicates
- `verificar_lancamento_duplicado(dados)` - Check transaction duplicates
- `listar_duplicatas_sistema()` - Find all duplicates in database
- `resolver_duplicata(duplicata_id, acao)` - Merge or delete duplicates

**Usage:**

```python
from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService

# Find all system duplicates
duplicatas = DuplicataVerificacaoService.listar_duplicatas_sistema()
```

---

#### CartorioVerificacaoService

**File:** `dominial/services/cartorio_verificacao_service.py`

**Purpose:** Validates and verifies cartório information.

**Key Methods:**

- `verificar_cartorio(cidade, estado, nome_parcial)` - Find cartório
- `validar_cns(cns)` - Validate CNS code format
- `buscar_cartorio_por_cidade(cidade, estado)` - List cartórios in city
- `sugerir_cartorios(texto)` - Autocomplete suggestions

**Validation:**

- CNS format validation
- City/state validation
- Duplicate prevention
- Active status checking

---

#### CRIService

**File:** `dominial/services/cri_service.py`

**Purpose:** Specialized operations for Cartório de Registro de Imóveis.

**Key Methods:**

- `obter_cri_por_documento(documento)` - Get current CRI for document
- `transferir_documento_cri(documento, novo_cri)` - Transfer document between CRIs
- `listar_documentos_cri(cri_id)` - Get all documents at a CRI

---

#### CacheService

**File:** `dominial/services/cache_service.py`

**Purpose:** Caching layer for expensive operations.

**Key Methods:**

- `obter_ou_calcular(chave, funcao_calculo, timeout)` - Get cached or calculate
- `invalidar_cache(chave)` - Clear specific cache
- `invalidar_cache_documento(documento_id)` - Clear document-related caches

**Cached Operations:**

- Hierarchy calculations
- Tree building
- Table data generation
- Statistics aggregation

**Cache Keys:**

```python
import json

# Ensure keys are sorted for consistent hashing
origens_key = json.dumps(origens, sort_keys=True) if origens else ""
filtros_key = json.dumps(filtros, sort_keys=True) if filtros else ""

f"arvore_cadeia_{documento_id}_{hash(origens_key)}"
f"tabela_cadeia_{documento_id}_{hash(filtros_key)}"
f"estatisticas_cadeia_{documento_id}"
```

---

#### ImportacaoCadeiaService

**File:** `dominial/services/importacao_cadeia_service.py` (229 lines)

**Purpose:** Import complete property chains from external data.

**Key Methods:**

- `importar_cadeia_completa(arquivo)` - Import full chain from file
- `validar_dados_importacao(dados)` - Validate import data
- `processar_linha_importacao(linha)` - Process single import record
- `criar_objetos_importacao(dados)` - Create database objects from import

**Import Format Support:**

- CSV files
- Excel files
- JSON data

**Workflow:**

1. Parse import file
2. Validate data structure
3. Check for duplicates
4. Create TI/Imovel if needed
5. Create Documentos
6. Create Lancamentos
7. Link origins
8. Report summary

---

#### RegraPetreaService

**File:** `dominial/services/regra_petrea_service.py`

**Purpose:** Implements "Regra Pétrea" (immutable rules) for property law.

**Key Methods:**

- `validar_regra_petrea(lancamento)` - Validate against immutable rules
- `aplicar_restricoes(lancamento)` - Apply legal restrictions
- `verificar_restricoes_publicas(documento)` - Check public property restrictions

**Rules Implemented:**

- Public property cannot be sold (only through legal process)
- Indigenous land restrictions
- Government property special handling
- Legal origin requirements

---

## Service Dependencies

### Typical Service Call Chain

```
View
 └─> LancamentoCriacaoService.criar()
      ├─> LancamentoValidacaoService.validar()
      ├─> LancamentoDuplicataService.verificar()
      ├─> LancamentoCamposService.processar()
      ├─> LancamentoOrigemService.processar()
      │    ├─> DocumentoService.buscar()
      │    └─> DocumentoService.criar() [if needed]
      ├─> Model: Lancamento.objects.create()
      ├─> LancamentoPessoaService.associar()
      └─> CacheService.invalidar()
```

### Service Inter-Dependencies

**Note:** `HierarquiaArvoreService` was removed in PR #11. The dependencies below reflect the original structure.

```
HierarquiaService
 ├─ uses → LancamentoConsultaService
 └─ uses → DocumentoService

HierarquiaArvoreService ~~(REMOVED in PR #11)~~
 ├─ used → HierarquiaService
 ├─ used → LancamentoConsultaService
 └─ used → CacheService

CadeiaCompletaService
 ├─ uses → HierarquiaService
 ├─ ~~uses → HierarquiaArvoreService~~ (removed - needs replacement)
 └─ uses → DocumentoService_Consolidado

LancamentoCriacaoService
 ├─ uses → LancamentoValidacaoService
 ├─ uses → LancamentoDuplicataService
 ├─ uses → LancamentoCamposService
 ├─ uses → LancamentoOrigemService
 ├─ uses → LancamentoPessoaService
 └─ uses → CacheService
```

## Common Service Patterns

### 1. Static Methods Pattern

Most services use static methods (no instance state):

```python
class MyService:
    @staticmethod
    def fazer_algo(parametro):
        # Business logic
        return resultado
```

### 2. Validation Pattern

Services validate input before processing:

```python
@staticmethod
def processar(dados):
    # 1. Validate
    if not dados.get('campo_obrigatorio'):
        raise ValidationError("Campo obrigatório ausente")

    # 2. Process
    resultado = processar_dados(dados)

    # 3. Return
    return resultado
```

### 3. Try-Except Pattern

Services handle errors gracefully:

```python
@staticmethod
def operacao_complexa(dados):
    try:
        resultado = fazer_operacao(dados)
        return {'sucesso': True, 'resultado': resultado}
    except Exception as e:
        logger.error(f"Erro na operação: {str(e)}")
        return {'sucesso': False, 'erro': str(e)}
```

### 4. Cache Pattern

Expensive operations use caching:

```python
@staticmethod
def obter_dados_complexos(id):
    chave_cache = f"dados_{id}"

    # Try cache first
    dados = cache.get(chave_cache)
    if dados:
        return dados

    # Calculate if not cached
    dados = calcular_dados_complexos(id)
    cache.set(chave_cache, dados, timeout=3600)
    return dados
```

## Testing Services

Services are tested independently in `dominial/tests/`:

```python
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService

class TestLancamentoCriacaoService(TestCase):
    def test_criar_lancamento_valido(self):
        dados = {
            'tipo': 'registro',
            'data': '2020-01-15',
            # ...
        }
        lancamento = LancamentoCriacaoService.criar(dados, documento_id=123)
        self.assertIsNotNone(lancamento)
        self.assertEqual(lancamento.tipo.tipo, 'registro')
```

## Service Best Practices in This Project

1. **Single Responsibility**: Each service has a focused purpose
2. **Stateless**: Services don't maintain instance state (static methods)
3. **Composable**: Services call other services as needed
4. **Testable**: All services can be tested independently
5. **Documented**: Complex logic is commented
6. **Error Handling**: All services handle errors gracefully
7. **Logging**: Important operations are logged
8. **Caching**: Expensive operations are cached

## Performance Considerations

- **Database Queries**: Services use `select_related()` and `prefetch_related()` to minimize queries
- **Caching**: Frequently accessed data is cached (hierarchy, trees)
- **Lazy Loading**: Data loaded only when needed
- **Batch Operations**: Multiple records processed in batches when possible

## Migration from Views to Services

The project has systematically moved business logic from views to services:

**Before (logic in views):**

```python
def criar_lancamento(request):
    # Validation logic
    # Duplicate checking logic
    # Field processing logic
    # Database operations
    # Error handling
    # All mixed together in view
```

**After (logic in services):**

```python
def criar_lancamento(request):
    # View only handles HTTP
    if request.method == 'POST':
        form = LancamentoForm(request.POST)
        if form.is_valid():
            # Delegate to service
            lancamento = LancamentoCriacaoService.criar(
                dados=form.cleaned_data,
                documento_id=documento_id
            )
            return redirect('lancamento_detail', pk=lancamento.pk)
```

This results in:

- Thinner views (easier to read)
- Reusable business logic
- Better testability
- Clearer separation of concerns
