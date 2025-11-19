# Database Models and Relationships

## Model Overview

The system has **13 core models** organized into **7 domain-specific modules**:

| Module | Models | Purpose |
|--------|--------|---------|
| `tis_models.py` | TIs, TerraIndigenaReferencia, TIs_Imovel | Indigenous lands |
| `pessoa_models.py` | Pessoas | People/persons |
| `imovel_models.py` | Imovel, Cartorios, ImportacaoCartorios | Properties and notary offices |
| `documento_models.py` | Documento, DocumentoTipo | Property documents |
| `lancamento_models.py` | Lancamento, LancamentoTipo, LancamentoPessoa, OrigemFimCadeia, FimCadeia | Transactions/registrations |
| `alteracao_models.py` | Alteracoes, AlteracoesTipo, RegistroTipo, AverbacoesTipo | Alterations |
| `documento_importado_models.py` | DocumentoImportado | Imported documents |

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                  TerraIndigenaReferencia                            │
│  (External reference data from FUNAI)                               │
│  - codigo (unique)                                                  │
│  - nome, etnia, estado, municipio                                  │
│  - area_ha, fase, modalidade                                       │
│  - dates (regularizada, homologada, etc.)                          │
└──────────────────┬──────────────────────────────────────────────────┘
                   │ FK: terra_referencia
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           TIs                                        │
│  (Indigenous Territories - Main working table)                      │
│  - id (PK)                                                          │
│  - terra_referencia (FK → TerraIndigenaReferencia) [optional]      │
│  - codigo (unique)                                                  │
│  - nome, etnia, estado, area                                       │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   │ Many-to-Many via TIs_Imovel
                   │
                   ├─────────────────────────────────────┐
                   │                                      │
                   ▼                                      ▼
┌──────────────────────────────┐      ┌──────────────────────────────┐
│       TIs_Imovel             │      │         Pessoas              │
│  (Junction table)            │      │  (People/Persons)            │
│  - tis_codigo (FK → TIs)     │      │  - id (PK)                   │
│  - imovel (FK → Imovel)      │      │  - nome                      │
└──────────────────┬───────────┘      │  - cpf (unique)              │
                   │                   │  - rg, data_nascimento       │
                   │                   │  - email, telefone           │
                   ▼                   └───────┬──────────────────────┘
┌─────────────────────────────────────────────│──────────────────────┐
│                        Imovel                │                       │
│  (Properties)                                │                       │
│  - id (PK)                                   │                       │
│  - terra_indigena_id (FK → TIs)              │                       │
│  - proprietario (FK → Pessoas) ──────────────┘                      │
│  - nome, matricula (unique)                                         │
│  - tipo_documento_principal                                         │
│  - cartorio (FK → Cartorios)                                        │
│  - observacoes, data_cadastro, arquivado                            │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   │ One-to-Many
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Documento                                      │
│  (Property Documents: Matrículas/Transcrições)                      │
│  - id (PK)                                                          │
│  - imovel (FK → Imovel)                                             │
│  - tipo (FK → DocumentoTipo)                                        │
│  - numero (unique with cartorio)                                    │
│  - data, cartorio (FK → Cartorios)                                  │
│  - livro, folha, origem, observacoes                                │
│  - nivel_manual (0-10)                                              │
│  - classificacao_fim_cadeia                                         │
│  - sigla_patrimonio_publico                                         │
│  - cri_atual (FK → Cartorios)                                       │
│  - cri_origem (FK → Cartorios)                                      │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   │ One-to-Many
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Lancamento                                      │
│  (Transactions/Registrations on Documents)                          │
│  - id (PK)                                                          │
│  - documento (FK → Documento)                                       │
│  - tipo (FK → LancamentoTipo)                                       │
│  - numero_lancamento, data                                          │
│  - transmitente (FK → Pessoas) [optional]                           │
│  - adquirente (FK → Pessoas) [optional]                             │
│  - valor_transacao, area                                            │
│  - forma, descricao, titulo                                         │
│  - cartorio_origem (FK → Cartorios)                                 │
│  - cartorio_transmissao (FK → Cartorios)                            │
│  - livro_transacao, folha_transacao, data_transacao                 │
│  - livro_origem, folha_origem, data_origem                          │
│  - eh_inicio_matricula (boolean)                                    │
│  - documento_origem (FK → Documento) [CHAIN LINK]                   │
└──────────────┬─────────────────────┬────────────────────────────────┘
               │                     │
               │ One-to-Many         │ One-to-Many
               ▼                     ▼
┌──────────────────────────┐  ┌──────────────────────────────────────┐
│   LancamentoPessoa       │  │      OrigemFimCadeia                 │
│  (Multiple people per    │  │  (End-of-chain per origin)           │
│   transaction)           │  │  - lancamento (FK → Lancamento)      │
│  - lancamento (FK)       │  │  - indice_origem                     │
│  - pessoa (FK → Pessoas) │  │  - fim_cadeia (boolean)              │
│  - tipo (transmitente/   │  │  - tipo_fim_cadeia                   │
│    adquirente)           │  │  - especificacao_fim_cadeia          │
│  - nome_digitado         │  │  - classificacao_fim_cadeia          │
└──────────────────────────┘  └──────────────────────────────────────┘

┌──────────────────────────┐  ┌──────────────────────────────────────┐
│     DocumentoTipo        │  │       LancamentoTipo                 │
│  (Document Types)        │  │  (Transaction Types)                 │
│  - id (PK)               │  │  - id (PK)                           │
│  - tipo:                 │  │  - tipo:                             │
│    * transcricao         │  │    * averbacao                       │
│    * matricula           │  │    * registro                        │
└──────────────────────────┘  │    * inicio_matricula                │
                              │  - requer_* (field requirements)     │
┌──────────────────────────┐  └──────────────────────────────────────┘
│      Cartorios           │
│  (Notary Offices/CRIs)   │  ┌──────────────────────────────────────┐
│  - nome, cns (unique)    │  │         FimCadeia                    │
│  - endereco, telefone    │  │  (End-of-chain definitions)          │
│  - estado, cidade        │  │  - nome, tipo, classificacao         │
│  - tipo (CRI/OUTRO)      │  │  - sigla, descricao                  │
└──────────────────────────┘  │  - ativo, dates                      │
                              └──────────────────────────────────────┘
```

## Detailed Model Descriptions

### 1. TIs (Indigenous Territories)

**File:** `dominial/models/tis_models.py:4`

**Purpose:** Represents indigenous lands that are being analyzed for property ownership chains.

**Key Fields:**
- `id` - Primary key (auto)
- `terra_referencia` - FK to TerraIndigenaReferencia (optional - can be manually created)
- `codigo` - Unique code for the territory
- `nome` - Name of the indigenous land
- `etnia` - Indigenous ethnicity/people
- `estado` - States (comma-separated, e.g., "AM, PA, MT")
- `area` - Area in hectares (decimal)
- `data_cadastro` - Auto-generated creation date

**Behavior:**
- When linked to `TerraIndigenaReferencia`, automatically copies reference data on save
- Can exist independently for custom territories

**Related Models:**
- Many-to-Many with `Imovel` via `TIs_Imovel`

---

### 2. TerraIndigenaReferencia (Indigenous Land Reference)

**File:** `dominial/models/tis_models.py:31`

**Purpose:** External reference data imported from FUNAI (government agency).

**Key Fields:**
- `codigo` - Unique FUNAI code
- `nome` - Official territory name
- `etnia` - Ethnicity
- `estado`, `municipio` - Geographic location
- `area_ha` - Area in hectares
- `fase` - Administrative phase (regularizada, homologada, etc.)
- `modalidade` - Type of land recognition
- `coordenacao_regional` - Regional coordination office
- Date fields for each phase: `data_regularizada`, `data_homologada`, `data_declarada`, `data_delimitada`, `data_em_estudo`

**Usage:**
- Read-only reference data
- Used to auto-populate TIs records
- Imported via management command `importar_terras_indigenas.py`

---

### 3. TIs_Imovel (Junction Table)

**File:** `dominial/models/tis_models.py:58`

**Purpose:** Links indigenous territories to properties (many-to-many relationship).

**Key Fields:**
- `tis_codigo` - FK to TIs
- `imovel` - FK to Imovel

**Usage:**
- A single TI can have multiple properties
- A property can overlap multiple TIs (rare but possible)

---

### 4. Pessoas (People/Persons)

**File:** `dominial/models/pessoa_models.py:4`

**Purpose:** Represents individuals involved in property transactions (buyers, sellers).

**Key Fields:**
- `id` - Primary key (auto)
- `nome` - Full name (required)
- `cpf` - CPF number (unique, optional)
- `rg` - RG number (optional)
- `data_nascimento` - Birth date (optional)
- `email` - Email address (optional)
- `telefone` - Phone number (optional)

**Constraints:**
- CPF must be unique when provided
- At minimum, name is required

**Usage:**
- Referenced by `Imovel.proprietario` (property owner)
- Referenced by `Lancamento.transmitente` (seller)
- Referenced by `Lancamento.adquirente` (buyer)
- Can have multiple transactions via `LancamentoPessoa`

---

### 5. Imovel (Property)

**File:** `dominial/models/imovel_models.py:4`

**Purpose:** Represents a property/real estate linked to an indigenous territory.

**Key Fields:**
- `id` - Primary key (auto)
- `terra_indigena_id` - FK to TIs (required - PROTECT on delete)
- `nome` - Property name
- `proprietario` - FK to Pessoas (current/main owner - PROTECT on delete)
- `matricula` - Registration number (unique identifier)
- `tipo_documento_principal` - Type: 'matricula' or 'transcricao'
- `cartorio` - FK to Cartorios (where registered)
- `observacoes` - Additional notes (optional)
- `data_cadastro` - Auto-generated creation date
- `arquivado` - Boolean flag to archive properties

**Methods:**
- `get_sigla_formatada()` - Returns "M{number}" for matrícula or "T{number}" for transcrição

**Relationships:**
- One-to-Many with `Documento` (a property has multiple documents)

---

### 6. Cartorios (Notary Offices)

**File:** `dominial/models/imovel_models.py:46`

**Purpose:** Represents notary offices (Cartório de Registro de Imóveis - CRI) where property documents are registered.

**Key Fields:**
- `nome` - Name of the notary office
- `cns` - CNS code (unique national identifier)
- `endereco` - Address (optional)
- `telefone` - Phone (optional)
- `email` - Email (optional)
- `estado` - State (2-letter code)
- `cidade` - City name
- `tipo` - Type: 'CRI' (default) or 'OUTRO'

**Display:**
- String representation: "{nome} - {cidade}/{estado}"

**Ordering:**
- By tipo, estado, cidade, nome

**Usage:**
- Referenced by `Imovel.cartorio`
- Referenced by `Documento.cartorio`, `Documento.cri_atual`, `Documento.cri_origem`
- Referenced by `Lancamento.cartorio_origem`, `Lancamento.cartorio_transmissao`
- Can be imported via management command `importar_cartorios_estado.py`

---

### 7. ImportacaoCartorios (Cartório Import Tracking)

**File:** `dominial/models/imovel_models.py:75`

**Purpose:** Tracks bulk cartório import operations by state.

**Key Fields:**
- `estado` - State being imported
- `data_inicio` - Start timestamp (auto)
- `data_fim` - End timestamp (optional)
- `total_cartorios` - Count of imported cartórios
- `status` - Status: 'pendente', 'em_andamento', 'concluido', 'erro'
- `erro` - Error message (optional)

**Usage:**
- Administrative tracking
- Prevents duplicate imports
- Debugging import issues

---

### 8. DocumentoTipo (Document Type)

**File:** `dominial/models/documento_models.py:5`

**Purpose:** Defines types of property documents.

**Types:**
- `transcricao` - Historical transcription (pre-1976 Brazilian property law)
- `matricula` - Modern property registration (post-1976)

**Usage:**
- Simple lookup table
- Created via management command `criar_tipos_documento.py`

---

### 9. Documento (Property Document)

**File:** `dominial/models/documento_models.py:21`

**Purpose:** Represents a property document (matrícula or transcrição) that contains transactions.

**Key Fields:**

*Basic Information:*
- `id` - Primary key (auto)
- `imovel` - FK to Imovel (CASCADE on delete)
- `tipo` - FK to DocumentoTipo (matrícula or transcrição)
- `numero` - Document number
- `data` - Document date
- `cartorio` - FK to Cartorios (where registered)
- `livro`, `folha` - Book and page numbers
- `origem` - Origin description (text)
- `observacoes` - Additional notes
- `data_cadastro` - Auto-generated creation date

*Advanced Fields:*
- `nivel_manual` - Manual hierarchy level (0-10) for visualization
- `classificacao_fim_cadeia` - End-of-chain classification:
  - `origem_lidima` - Legitimate origin
  - `sem_origem` - No origin
  - `inconclusa` - Inconclusive situation
- `sigla_patrimonio_publico` - Public property signature (e.g., "INCRA", "Estado")

*CRI Fields:*
- `cri_atual` - FK to Cartorios (current CRI)
- `cri_origem` - FK to Cartorios (origin CRI for auto-created documents)

**Constraints:**
- `unique_together = ('numero', 'cartorio')` - A document number must be unique per cartório

**Ordering:**
- By date (descending - newest first)

**Relationships:**
- One-to-Many with `Lancamento` (a document has multiple transactions)
- Self-referential via `Lancamento.documento_origem` (chain linking)

---

### 10. LancamentoTipo (Transaction Type)

**File:** `dominial/models/lancamento_models.py:5`

**Purpose:** Defines types of transactions/registrations with their field requirements.

**Types:**
- `averbacao` - Annotation (non-ownership changes: liens, restrictions, etc.)
- `registro` - Registration (ownership transfers)
- `inicio_matricula` - Start of registration (initial property registration)

**Field Requirements (Boolean flags):**
- `requer_transmissao` - Requires transmission data
- `requer_detalhes` - Requires details field
- `requer_titulo` - Requires title/document type
- `requer_cartorio_origem` - Requires origin cartório
- `requer_livro_origem` - Requires origin book
- `requer_folha_origem` - Requires origin page
- `requer_data_origem` - Requires origin date
- `requer_forma` - Requires form/method
- `requer_descricao` - Requires description
- `requer_observacao` - Requires observations (default: True)

**Validation:**
- `clean()` method enforces type-specific requirements
- Registrations must require cartório and título
- Averbações must require description

**Usage:**
- Created via management command `criar_tipos_lancamento.py`
- Used by `LancamentoCamposService` to determine required fields dynamically

---

### 11. Lancamento (Transaction/Registration)

**File:** `dominial/models/lancamento_models.py:43`

**Purpose:** Core model representing a transaction or registration entry on a document. This is the **heart of the property chain system**.

**Key Fields:**

*Basic Information:*
- `id` - Primary key (auto)
- `documento` - FK to Documento (CASCADE on delete)
- `tipo` - FK to LancamentoTipo (averbação, registro, or início de matrícula)
- `numero_lancamento` - Transaction number from cartório
- `data` - Transaction date
- `data_cadastro` - Auto-generated creation date

*People Involved:*
- `transmitente` - FK to Pessoas (seller/transferor - optional)
- `adquirente` - FK to Pessoas (buyer/acquirer - optional)
  - Note: Use `LancamentoPessoa` for multiple people per transaction

*Transaction Details:*
- `valor_transacao` - Transaction value (decimal)
- `area` - Property area in this transaction (decimal with 4 decimal places)
- `origem` - Origin description (text)
- `detalhes` - Additional details (text)
- `observacoes` - Observations (text)

*Type-Specific Fields:*
- `forma` - Form/method (e.g., "compra e venda", "doação")
- `descricao` - Description (required for averbações)
- `titulo` - Title/document type (required for registrations)

*Cartório References:*
- `cartorio_origem` - FK to Cartorios (origin cartório for início de matrícula)
- `cartorio_transmissao` - FK to Cartorios (where transmission was registered)
- `cartorio_transacao` - FK to Cartorios (legacy field - being phased out)

*Transaction Information:*
- `livro_transacao`, `folha_transacao`, `data_transacao` - Transaction location

*Origin Information (for início de matrícula):*
- `livro_origem`, `folha_origem`, `data_origem` - Origin document location

*Chain Linking (Critical):*
- `eh_inicio_matricula` - Boolean flag indicating this starts a new matrícula
- **`documento_origem`** - FK to Documento (links to previous document in chain)
  - This is the key field that connects the entire property ownership chain

**Methods:**
- `transmitentes` (property) - Returns all transmitters via `LancamentoPessoa`
- `adquirentes` (property) - Returns all acquirers via `LancamentoPessoa`
- `cartorio_transmissao_compat` (property) - Compatibility layer for legacy field

**Validation:**
- `clean()` method validates required fields based on `LancamentoTipo` requirements
- Special validation for início de matrícula (requires cartorio_origem)

**Relationships:**
- One-to-Many with `LancamentoPessoa` (multiple people per transaction)
- One-to-Many with `OrigemFimCadeia` (multiple origins with end-of-chain info)

**Ordering:**
- By id (ascending)

---

### 12. LancamentoPessoa (Transaction Person)

**File:** `dominial/models/lancamento_models.py:130`

**Purpose:** Allows multiple people (with percentages) per transaction as transmitters or acquirers.

**Key Fields:**
- `lancamento` - FK to Lancamento (CASCADE on delete)
- `pessoa` - FK to Pessoas (PROTECT on delete)
- `tipo` - Type: 'transmitente' or 'adquirente'
- `nome_digitado` - Name typed if person didn't exist in database (optional)

**Constraints:**
- `unique_together = ('lancamento', 'pessoa', 'tipo')` - Prevent duplicate person associations

**Usage:**
- When a transaction has multiple sellers or buyers
- Accessed via `lancamento.pessoas.filter(tipo='transmitente')`

---

### 13. OrigemFimCadeia (Origin End-of-Chain)

**File:** `dominial/models/lancamento_models.py:151`

**Purpose:** Stores end-of-chain information for each individual origin when a transaction has multiple origins.

**Key Fields:**
- `lancamento` - FK to Lancamento (CASCADE on delete)
- `indice_origem` - Index of this origin in the origins array (0, 1, 2, ...)
- `fim_cadeia` - Boolean flag indicating if this origin marks the end of the chain
- `tipo_fim_cadeia` - Type of end:
  - `destacamento_publico` - Public property separation
  - `outra` - Other
  - `sem_origem` - No origin
- `especificacao_fim_cadeia` - Specification when type is 'Outra'
- `classificacao_fim_cadeia` - Classification:
  - `origem_lidima` - Legitimate origin
  - `sem_origem` - No origin
  - `inconclusa` - Inconclusive

**Constraints:**
- `unique_together = ['lancamento', 'indice_origem']`

**Validation:**
- When `fim_cadeia` is True, requires `tipo_fim_cadeia` and `classificacao_fim_cadeia`
- When type is 'outra', requires `especificacao_fim_cadeia`

**Usage:**
- Complex chains with multiple branches
- Tracking which specific origin terminates each chain branch

---

### 14. FimCadeia (End-of-Chain Definitions)

**File:** `dominial/models/lancamento_models.py:204`

**Purpose:** Manages predefined end-of-chain types that appear in the D3 tree visualization.

**Key Fields:**
- `id` - Primary key (auto)
- `nome` - Name (unique, e.g., "Estado da Bahia", "INCRA")
- `tipo` - Type: 'destacamento_publico', 'outra', 'sem_origem'
- `classificacao` - Classification: 'origem_lidima', 'sem_origem', 'inconclusa'
- `sigla` - Abbreviation (e.g., "INCRA", "SPU")
- `descricao` - Detailed description
- `ativo` - Boolean flag if active
- `data_criacao`, `data_atualizacao` - Timestamps

**Methods:**
- `get_cor_css()` - Returns CSS color based on classification:
  - Green (#28a745) for origem_lidima
  - Red (#dc3545) for sem_origem
  - Yellow (#ffc107) for inconclusa
- `get_cor_borda_css()` - Returns darker border color

**Usage:**
- Visualization in D3 tree
- Consistent styling and classification
- Pre-defined government entities (INCRA, state governments, etc.)

**Ordering:**
- By name (alphabetical)

---

## Key Relationships and Data Flow

### Property Chain Structure

The property ownership chain is built through these relationships:

1. **TI → Imovel**: An indigenous territory has multiple properties
2. **Imovel → Documento**: A property has multiple documents over time
3. **Documento → Lancamento**: A document has multiple transaction entries
4. **Lancamento → Documento** (via `documento_origem`): Transactions link back to origin documents

### Chain Traversal Example

```
TI: "Terra Indígena Xingu"
  └─ Imovel: "Fazenda ABC" (Matrícula 12345)
      ├─ Documento: Matrícula 12345 (current)
      │   ├─ Lancamento: R-1 (Registro) → documento_origem: Matrícula 99999
      │   ├─ Lancamento: Av-1 (Averbação) → no origin
      │   └─ Lancamento: R-2 (Registro) → documento_origem: Matrícula 12345
      │
      └─ Documento: Matrícula 99999 (origin - auto-created)
          └─ Lancamento: IM-1 (Início de Matrícula) → origem: "INCRA"
```

### Critical Foreign Keys for Chain Building

1. **`Lancamento.documento_origem`** - Links transaction to origin document
2. **`Lancamento.eh_inicio_matricula`** - Marks start of chain
3. **`Lancamento.tipo`** - Determines if transaction transfers ownership
4. **`Documento.cri_origem`** - Tracks auto-created origin documents

## Database Constraints

### Unique Constraints
- `TIs.codigo` - Unique territory code
- `Pessoas.cpf` - Unique CPF per person
- `Imovel.matricula` - Unique property registration number
- `Cartorios.cns` - Unique CNS code per cartório
- `Documento (numero, cartorio)` - Unique document per cartório
- `LancamentoPessoa (lancamento, pessoa, tipo)` - Unique person per transaction type
- `OrigemFimCadeia (lancamento, indice_origem)` - Unique origin index per transaction

### Foreign Key Constraints

**PROTECT (prevent deletion if referenced):**
- `TIs.terra_referencia` → TerraIndigenaReferencia
- `Imovel.terra_indigena_id` → TIs
- `Imovel.proprietario` → Pessoas
- `Imovel.cartorio` → Cartorios
- `Documento.tipo` → DocumentoTipo
- `Documento.cartorio` → Cartorios
- All `Lancamento` FKs to Pessoas and Cartorios

**CASCADE (delete children when parent deleted):**
- `TIs_Imovel.tis_codigo` → TIs
- `TIs_Imovel.imovel` → Imovel
- `Documento.imovel` → Imovel
- `Lancamento.documento` → Documento
- `LancamentoPessoa.lancamento` → Lancamento
- `OrigemFimCadeia.lancamento` → Lancamento

## Indexing Strategy

Django automatically creates indexes on:
- Primary keys (all `id` fields)
- Foreign keys (all FK fields)
- Unique fields (codigo, cpf, matricula, cns, etc.)

Additional indexes should be considered for:
- `Documento.data` (frequently used in ordering)
- `Lancamento.data` (frequently queried)
- `Lancamento.eh_inicio_matricula` (filtered often)
- `Cartorios (estado, cidade)` (used in autocomplete)

## Data Integrity Rules

1. **CPF Uniqueness**: Each person can have only one CPF
2. **Document Uniqueness**: A document number is unique per cartório
3. **Property Uniqueness**: Each matrícula number is globally unique
4. **Cascading Deletes**: Deleting a property deletes all its documents and transactions
5. **Protected References**: Cannot delete a person if they're referenced in transactions
6. **End-of-Chain Validation**: End-of-chain markers require type and classification

## Common Query Patterns

### Get all documents for a property
```python
property = Imovel.objects.get(matricula='12345')
documents = property.documentos.all()
```

### Get all transactions for a document
```python
document = Documento.objects.get(id=1)
transactions = document.lancamentos.all()
```

### Get origin document for a transaction
```python
transaction = Lancamento.objects.get(id=1)
if transaction.documento_origem:
    origin_document = transaction.documento_origem
```

### Find all properties in an indigenous territory
```python
ti = TIs.objects.get(codigo='BA001')
properties = Imovel.objects.filter(terra_indigena_id=ti)
```

### Get all transactions by a person
```python
person = Pessoas.objects.get(cpf='12345678901')
as_seller = person.transmitente_lancamento.all()
as_buyer = person.adquirente_lancamento.all()
```

## Migration Strategy

Models are versioned through Django migrations in `dominial/migrations/`:
- Migrations are auto-generated via `python manage.py makemigrations`
- Applied via `python manage.py migrate`
- Can be rolled back if needed
- Current migration count: 40+ migrations

## Data Initialization

Several management commands initialize reference data:
- `criar_tipos_documento.py` - Creates DocumentoTipo entries
- `criar_tipos_lancamento.py` - Creates LancamentoTipo entries
- `importar_terras_indigenas.py` - Imports TerraIndigenaReferencia from government data
- `importar_cartorios_estado.py` - Imports Cartorios by state from CNJ API
