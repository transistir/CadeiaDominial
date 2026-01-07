# Database Schema Reference
## Cadeia Dominial - Django 5.2 Application

**Generated:** 2025-01-07
**Database:** SQLite (development), PostgreSQL (production)
**Django App:** `dominial`

---

## Entity Relationship Overview

```
TerraIndigenaReferencia (Reference)
    └── TIs (Indigenous Lands)
        └── Imovel (Properties)
            ├── Cartorios (Registry Offices)
            ├── Pessoas (People/Owners)
            ├── Documento (Documents)
            │   ├── DocumentoTipo
            │   ├── Lancamento (Transactions)
            │   │   ├── LancamentoTipo
            │   │   ├── LancamentoPessoa
            │   │   ├── OrigemFimCadeia
            │   │   └── FimCadeia
            │   └── DocumentoImportado
            └── Alteracoes (Legacy - not actively used)
```

---

## Table Definitions

### 1. Terra Indígena (Indigenous Lands)

#### `dominial_terraindigenareferencia`
**Reference data for Indigenous Lands** - Imported from official sources

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| codigo | CharField(50) | UNIQUE | Official code |
| nome | CharField(255) | - | Name |
| etnia | CharField(255) | NULL | Ethnicity |
| estado | CharField(100) | NULL | State(s) |
| municipio | CharField(255) | NULL | Municipality |
| area_ha | FloatField | NULL | Area in hectares |
| fase | CharField(100) | NULL | Phase (regularization status) |
| modalidade | CharField(100) | NULL | Modality |
| coordenacao_regional | CharField(100) | NULL | Regional coordination |
| data_regularizada | DateField | NULL | Regularized date |
| data_homologada | DateField | NULL | Homologated date |
| data_declarada | DateField | NULL | Declared date |
| data_delimitada | DateField | NULL | Delimited date |
| data_em_estudo | DateField | NULL | Under study date |
| created_at | DateTimeField | AUTO | Creation timestamp |
| updated_at | DateTimeField | AUTO | Update timestamp |

**Indexes:**
- `nome` (ordering)

---

#### `dominial_tis`
**Indigenous Lands (TIs)** - Active records

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| terra_referencia | ForeignKey | PROTECT (NULL) | Reference to TerraIndigenaReferencia |
| nome | CharField(255) | - | Name (auto-populated from reference) |
| codigo | CharField(50) | UNIQUE | Code (auto-populated from reference) |
| etnia | CharField(255) | - | Ethnicity (auto-populated from reference) |
| estado | CharField(100) | NULL | State(s) - comma-separated |
| area | DecimalField(12,2) | NULL | Area in hectares |
| data_cadastro | DateField | AUTO | Registration date |

**Special Logic:**
- When `terra_referencia` is set, fields are auto-populated on save
- Multiple states can be stored (e.g., "AM, PA, MT")

---

### 2. Pessoas (People)

#### `dominial_pessoas`
**Property owners and transaction participants**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| nome | CharField(255) | - | Full name |
| cpf | CharField(11) | UNIQUE (NULL) | CPF (Brazilian tax ID) |
| rg | CharField(20) | NULL | RG (Identity document) |
| data_nascimento | DateField | NULL | Birth date |
| email | EmailField | NULL | Email address |
| telefone | CharField(15) | NULL | Phone number |

**Validation:**
- CPF must be unique if provided
- Used in transactions as transmitente and adquirente

---

### 3. Cartórios (Registry Offices)

#### `dominial_cartorios`
**Brazilian Registry Offices (Cartório de Registro de Imóveis)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| nome | CharField(200) | - | Name |
| cns | CharField(20) | UNIQUE | CNS (National Registry System) |
| endereco | CharField(200) | NULL | Address |
| telefone | CharField(20) | NULL | Phone |
| email | EmailField | NULL | Email |
| estado | CharField(2) | NULL | State (UF) |
| cidade | CharField(100) | NULL | City |
| tipo | CharField(10) | DEFAULT='CRI' | Type (CRI/OUTRO) |

**Type Choices:**
- `CRI` - Cartório de Registro de Imóveis (default)
- `OUTRO` - Other

**Indexes:**
- `['tipo', 'estado', 'cidade', 'nome']` (ordering)

---

#### `dominial_importacaocartorios`
**Track cartório import operations**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| estado | CharField(2) | - | State (UF) |
| data_inicio | DateTimeField | AUTO | Start timestamp |
| data_fim | DateTimeField | NULL | End timestamp |
| total_cartorios | IntegerField | DEFAULT=0 | Total imported |
| status | CharField(20) | DEFAULT='pendente' | Status |
| erro | TextField | NULL | Error message |

**Status Choices:**
- `pendente` - Pending
- `em_andamento` - In progress
- `concluido` - Completed
- `erro` - Error

---

### 4. Imóveis (Properties)

#### `dominial_imovel`
**Properties belonging to Indigenous Lands**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| terra_indigena_id | ForeignKey | PROTECT | Reference to TIs |
| nome | CharField(100) | - | Property name |
| proprietario | ForeignKey | PROTECT | Owner (Pessoas) |
| matricula | CharField(50) | - | Registration number |
| tipo_documento_principal | CharField(20) | DEFAULT='matricula' | Document type |
| observacoes | TextField | NULL | Notes |
| cartorio | ForeignKey | PROTECT (NULL) | Registry office |
| data_cadastro | DateField | AUTO | Registration date |
| arquivado | BooleanField | DEFAULT=False | Archived status |

**Type Choices:**
- `matricula` - Matrícula (default)
- `transcricao` - Transcrição

**Constraints:**
- `unique_together = ['matricula', 'cartorio']`
- Index: `['matricula', 'cartorio']`

**Important:**
- Matrícula must be unique per cartório, not globally
- This allows different cartórios to have properties with the same matrícula

---

#### `dominial_tis_imovel`
**Many-to-many relationship between TIs and Imóveis**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| tis_codigo | ForeignKey | CASCADE | Reference to TIs |
| imovel | ForeignKey | CASCADE | Reference to Imovel |

---

### 5. Documentos (Documents)

#### `dominial_documentotipo`
**Document types**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| tipo | CharField(50) | - | Type |

**Type Choices:**
- `transcricao` - Transcrição
- `matricula` - Matrícula

---

#### `dominial_documento`
**Property documents (matrículas/transcrições)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| imovel | ForeignKey | CASCADE | Property (Imovel) |
| tipo | ForeignKey | PROTECT | Document type |
| numero | CharField(50) | - | Document number |
| data | DateField | - | Document date |
| cartorio | ForeignKey | PROTECT | Registry office |
| livro | CharField(50) | - | Book |
| folha | CharField(50) | - | Folha (page) |
| origem | TextField | NULL | Origin information |
| observacoes | TextField | NULL | Notes |
| data_cadastro | DateField | AUTO | Registration date |
| nivel_manual | IntegerField | NULL | Manual level (0-10) |
| classificacao_fim_cadeia | CharField(50) | NULL | Chain end classification |
| sigla_patrimonio_publico | CharField(50) | NULL | Public property sigla |
| cri_atual | ForeignKey | PROTECT (NULL) | Current CRI |
| cri_origem | ForeignKey | PROTECT (NULL) | Origin CRI |

**Classification Choices:**
- `origem_lidima` - Imóvel com Origem Lídima
- `sem_origem` - Imóvel sem Origem
- `inconclusa` - Situação Inconclusa

**Constraints:**
- `unique_together = ['numero', 'cartorio']`

**Indexes:**
- `['-data']` (ordering)

---

#### `dominial_documentoimportado`
**Track documents imported from other chains**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| documento | ForeignKey | CASCADE | Document reference |
| imovel_origem | ForeignKey | CASCADE | Source property |
| data_importacao | DateTimeField | AUTO | Import timestamp |
| importado_por | ForeignKey | PROTECT (NULL) | User who imported |

**Constraints:**
- `unique_together = ['documento', 'imovel_origem']`

**Indexes:**
- `['documento']`
- `['imovel_origem']`
- `['data_importacao']`
- `['importado_por']`

---

### 6. Lançamentos (Transactions)

#### `dominial_lancamentotipo`
**Transaction types**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| tipo | CharField(50) | - | Type |
| requer_transmissao | BooleanField | DEFAULT=False | Requires transmission |
| requer_detalhes | BooleanField | DEFAULT=False | Requires details |
| requer_titulo | BooleanField | DEFAULT=False | Requires title |
| requer_cartorio_origem | BooleanField | DEFAULT=False | Requires origin cartório |
| requer_livro_origem | BooleanField | DEFAULT=False | Requires origin book |
| requer_folha_origem | BooleanField | DEFAULT=False | Requires origin folha |
| requer_data_origem | BooleanField | DEFAULT=False | Requires origin date |
| requer_forma | BooleanField | DEFAULT=False | Requires form |
| requer_descricao | BooleanField | DEFAULT=False | Requires description |
| requer_observacao | BooleanField | DEFAULT=True | Requires observation |

**Type Choices:**
- `averbacao` - Averbação
- `registro` - Registro
- `inicio_matricula` - Início de Matrícula

**Validation:**
- Registros must require cartório_origem and titulo
- Averbações must require descricao

---

#### `dominial_lancamento`
**Transaction annotations on documents**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| documento | ForeignKey | CASCADE | Document |
| tipo | ForeignKey | PROTECT | Transaction type |
| numero_lancamento | CharField(50) | NULL | Transaction number |
| data | DateField | - | Transaction date |
| transmitente | ForeignKey | PROTECT (NULL) | Transferor (Pessoas) |
| adquirente | ForeignKey | PROTECT (NULL) | Acquirer (Pessoas) |
| valor_transacao | DecimalField(10,2) | NULL | Transaction value |
| area | DecimalField(12,4) | NULL | Area |
| origem | CharField(255) | NULL | Origin |
| detalhes | TextField | NULL | Details |
| observacoes | TextField | NULL | Notes |
| data_cadastro | DateField | AUTO | Registration date |
| forma | CharField(100) | NULL | Form |
| descricao | TextField | NULL | Description |
| titulo | CharField(255) | NULL | Title |
| cartorio_origem | ForeignKey | PROTECT (NULL) | Origin cartório |
| cartorio_transacao | ForeignKey | PROTECT (NULL) | Transaction cartório (legacy) |
| cartorio_transmissao | ForeignKey | PROTECT (NULL) | Transmission cartório (new) |
| livro_transacao | CharField(50) | NULL | Transaction book |
| folha_transacao | CharField(50) | NULL | Transaction folha |
| data_transacao | DateField | NULL | Transaction date |
| livro_origem | CharField(50) | NULL | Origin book |
| folha_origem | CharField(50) | NULL | Origin folha |
| data_origem | DateField | NULL | Origin date |
| eh_inicio_matricula | BooleanField | DEFAULT=False | Is matrícula start |
| documento_origem | ForeignKey | PROTECT (NULL) | Origin document |

**Indexes:**
- `['id']` (ordering)

**Properties:**
- `cartorio_transmissao_compat` - Returns cartorio_transmissao or cartorio_transacao (fallback)

---

#### `dominial_lancamentopessoa`
**Multiple people per transaction (many-to-many)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| lancamento | ForeignKey | CASCADE | Transaction |
| pessoa | ForeignKey | PROTECT | Person |
| tipo | CharField(20) | - | Type |
| nome_digitado | CharField(255) | NULL | Manually entered name |

**Type Choices:**
- `transmitente` - Transmitente
- `adquirente` - Adquirente

**Constraints:**
- `unique_together = ['lancamento', 'pessoa', 'tipo']`

---

#### `dominial_origemfimcadeia`
**Chain end tracking per origin**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| lancamento | ForeignKey | CASCADE | Transaction |
| indice_origem | IntegerField | - | Origin index (0, 1, 2, ...) |
| fim_cadeia | BooleanField | DEFAULT=False | Is chain end |
| tipo_fim_cadeia | CharField(50) | NULL | Chain end type |
| especificacao_fim_cadeia | TextField | NULL | Specification |
| classificacao_fim_cadeia | CharField(50) | NULL | Classification |

**Type Choices:**
- `destacamento_publico` - Destacamento do Patrimônio Público
- `outra` - Outra
- `sem_origem` - Sem Origem

**Classification Choices:**
- `origem_lidima` - Imóvel com Origem Lídima
- `sem_origem` - Imóvel sem Origem
- `inconclusa` - Situação Inconclusa

**Constraints:**
- `unique_together = ['lancamento', 'indice_origem']`

**Validation:**
- If `fim_cadeia=True`, then `tipo_fim_cadeia` and `classificacao_fim_cadeia` are required
- If `tipo_fim_cadeia='outra'`, then `especificacao_fim_cadeia` is required

---

#### `dominial_fimcadeia`
**Chain end types (managed in admin)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| nome | CharField(100) | UNIQUE | Name |
| tipo | CharField(50) | DEFAULT='destacamento_publico' | Type |
| classificacao | CharField(50) | DEFAULT='origem_lidima' | Classification |
| sigla | CharField(50) | NULL | Abbreviation |
| descricao | TextField | NULL | Description |
| ativo | BooleanField | DEFAULT=True | Active |
| data_criacao | DateTimeField | AUTO | Creation timestamp |
| data_atualizacao | DateTimeField | AUTO | Update timestamp |

**Methods:**
- `get_cor_css()` - Returns CSS color based on classification
- `get_cor_borda_css()` - Returns border CSS color

**Color Mapping:**
- `origem_lidima`: Green (#28a745)
- `sem_origem`: Red (#dc3545)
- `inconclusa`: Yellow (#ffc107)

---

### 7. Alterações (Legacy - Not Actively Used)

#### `dominial_alteracoestipo`
**Alteration types**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| tipo | CharField(50) | - | Type |

---

#### `dominial_registrotipo`
**Registration types**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| tipo | CharField(100) | - | Type |

---

#### `dominial_averbacoe tipo`
**Averbação types**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| tipo | CharField(100) | - | Type |

---

#### `dominial_alteracoes`
**Property alterations (legacy model)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | AutoField | PK | Primary key |
| imovel_id | ForeignKey | CASCADE | Property |
| tipo_alteracao_id | ForeignKey | CASCADE | Alteration type |
| livro | CharField(50) | NULL | Book |
| folha | CharField(50) | NULL | Folha |
| cartorio | ForeignKey | CASCADE | Registry office |
| data_alteracao | DateField | NULL | Alteration date |
| registro_tipo | ForeignKey | CASCADE (NULL) | Registration type |
| averbacao_tipo | ForeignKey | CASCADE (NULL) | Averbação type |
| titulo | CharField(255) | NULL | Title |
| cartorio_origem | ForeignKey | CASCADE | Origin cartório |
| livro_origem | CharField(50) | NULL | Origin book |
| folha_origem | CharField(50) | NULL | Origin folha |
| data_origem | DateField | NULL | Origin date |
| transmitente | ForeignKey | CASCADE (NULL) | Transferor |
| adquirente | ForeignKey | CASCADE (NULL) | Acquirer |
| valor_transacao | DecimalField(10,2) | NULL | Transaction value |
| area | DecimalField(12,4) | NULL | Area |
| observacoes | TextField | NULL | Notes |
| data_cadastro | DateField | AUTO | Registration date |

**Note:** This model appears to be legacy and is replaced by the Lancamento system.

---

## Database Constraints Summary

### Unique Constraints

1. **TerraIndigenaReferencia**: `codigo`
2. **Pessoas**: `cpf` (if provided)
3. **Cartorios**: `cns`
4. **Imovel**: `['matricula', 'cartorio']`
5. **Documento**: `['numero', 'cartorio']`
6. **DocumentoImportado**: `['documento', 'imovel_origem']`
7. **LancamentoPessoa**: `['lancamento', 'pessoa', 'tipo']`
8. **OrigemFimCadeia**: `['lancamento', 'indice_origem']`
9. **FimCadeia**: `nome`

### Foreign Key Relationships

**CASCADE** (deletes related records):
- TIs → Imovel (through terra_indigena_id)
- Documento → Lancamento
- Imovel → Documento
- Lancamento → LancamentoPessoa
- Lancamento → OrigemFimCadeia
- DocumentoImportado → Documento
- Many legacy Alteracoes relationships

**PROTECT** (prevents deletion if referenced):
- TIs → TerraIndigenaReferencia
- Imovel → TIs
- Imovel → Cartorios
- Imovel → Pessoas
- Documento → Imovel
- Documento → DocumentoTipo
- Documento → Cartorios
- Lancamento → Documento
- Lancamento → LancamentoTipo
- Lancamento → Pessoas
- And many more...

---

## Database Indexes

### Performance Indexes

1. **Imovel**: `['matricula', 'cartorio']` → `dom_imovel_mat_cart_idx`
2. **Documento**: Ordering by `['-data']`
3. **Cartorios**: Ordering by `['tipo', 'estado', 'cidade', 'nome']`
4. **DocumentoImportado**: `['documento']`, `['imovel_origem']`, `['data_importacao']`, `['importado_por']`
5. **TerraIndigenaReferencia**: Ordering by `['nome']`
6. **FimCadeia**: Ordering by `['nome']`

---

## Data Integrity Rules

### Business Logic

1. **Matrícula Uniqueness**: Must be unique per cartório, not globally
2. **Document Chain**: Documents form a chain through `documento_origem` relationships
3. **Transaction Validation**: Required fields vary by LancamentoTipo
4. **Chain End Detection**: Tracked through OrigemFimCadeia records
5. **Import Tracking**: DocumentoImportado prevents duplicate imports

### Validation Rules

1. **LancamentoTipo**:
   - Registros must require `cartorio_origem` and `titulo`
   - Averbações must require `descricao`

2. **Lancamento**:
   - Fields required based on LancamentoTipo settings
   - Início de matrícula always requires `cartorio_origem`

3. **OrigemFimCadeia**:
   - If `fim_cadeia=True`, requires `tipo_fim_cadeia` and `classificacao_fim_cadeia`
   - If `tipo_fim_cadeia='outra'`, requires `especificacao_fim_cadeia`

4. **FimCadeia**:
   - Nome must be unique
   - Managed through Django admin interface

---

## Migration Notes

### Important Changes

1. **Matrícula Constraint**: Changed from global uniqueness to per-cartório uniqueness
2. **CRI Fields**: Added `cri_atual` and `cri_origem` to Documento
3. **Transmission Fields**: Added `cartorio_transmissao` (new) alongside `cartorio_transacao` (legacy)
4. **Chain End Classification**: Added fields to track chain end status
5. **Import Tracking**: Added DocumentoImportado model to prevent duplicate imports

### Legacy vs Current Models

- **Alteracoes** appears to be a legacy model, largely replaced by Lancamento
- **Lancamento** is the current system for tracking all transactions
- **DocumentoImportado** is used for tracking cross-chain imports

---

## Query Patterns

### Common Joins

```python
# Property with all related data
Imovel.objects.select_related(
    'terra_indigena_id',
    'proprietario',
    'cartorio'
).prefetch_related(
    'documentos',
    'documentos__lancamentos'
)

# Document with transactions
Documento.objects.select_related(
    'imovel',
    'cartorio',
    'tipo'
).prefetch_related(
    'lancamentos',
    'lancamentos__tipo'
)

# Transaction chain
Lancamento.objects.select_related(
    'documento',
    'tipo',
    'transmitente',
    'adquirente'
)
```

---

## Summary Statistics

- **Total Tables**: 17
- **Primary Keys**: 17 (all AutoFields)
- **Foreign Keys**: 50+
- **Unique Constraints**: 9
- **Indexes**: 10+
- **Many-to-Many Tables**: 1 (TIs_Imovel)

---

**End of Schema Reference**
