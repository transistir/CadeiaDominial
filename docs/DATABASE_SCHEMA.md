# Database Schema Documentation

## Overview

The **Sistema de Cadeia Dominial** is a web application for managing and visualizing property chain data (cadeia dominial) related to Indigenous lands (Terras Indigenas) in Brazil. The system tracks property registrations, document chains, and ownership transfers through the Brazilian cartorio (registry office) system.

### Technology Stack

- **Development**: SQLite (local file-based)
- **Production**: PostgreSQL 15+
- **ORM**: Django 5.2.3 (Python) with optional Drizzle ORM (TypeScript)
- **Extensions**: `uuid-ossp`, `pg_trgm` (trigram for full-text search)

---

## Entity-Relationship Diagram

```
+------------------------+                    +----------------------+
|  TerraIndigenaRef      |                    |      Cartorios       |
+------------------------+                    +----------------------+
            |                                     /    |    \
            | 1:N                                /     |     \
            v                                   /      |      \
+----------+         +--------+         +---------+    |       |
| Pessoas  |<--------| Imovel |-------->|   TIs   |    |       |
+----------+   N:1   +--------+   N:1   +---------+    |       |
     |         (proprietario)  \              |        |       |
     |                   |      \             |        |       |
     |              1:N  |       \            |        |       |
     |                   v        \           |        |       |
     |            +----------+     +----------+--------+       |
     |            | Documento|<----+ (cartorio, cri_atual,     |
     |            +----------+       cri_origem)               |
     |                   |                                     |
     |              1:N  |                                     |
     |                   v                                     |
     +------------>+-----------+-------------------------------+
         N:1       | Lancamento|  (cartorio_origem, cartorio_transmissao)
                   +-----------+
                     |       \
                1:N  |        \ 1:N
                     v         v
    +------------------+    +------------------+
    | LancamentoPessoa |    | OrigemFimCadeia  |
    +------------------+    +------------------+

+------------+            +------------+
| Alteracoes |----------->| TIs_Imovel | (Junction M:N)
+------------+ (to Imovel)+------------+
                                |
                                v
                           TIs <-> Imovel

Lookup Tables:
  - DocumentoTipo (matricula, transcricao)
  - LancamentoTipo (averbacao, registro, inicio_matricula)
  - AlteracoesTipo (registro, averbacao, nao_classificado)
  - RegistroTipo, AverbacoesTipo (dynamic values)
  - FimCadeia (master list of end-of-chain types)
  - ImportacaoCartorios (import log)
  - DocumentoImportado (tracks imported documents)
```

---

## Tables Reference

### Core Models

#### 1. `dominial_terraindigenareferencia` - Indigenous Land Reference Data

Official reference data for Indigenous lands imported from government sources.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `codigo` | VARCHAR(50) | UNIQUE, NOT NULL | Official land code |
| `nome` | VARCHAR(255) | NOT NULL | Land name |
| `etnia` | VARCHAR(255) | NULL | Ethnic group |
| `estado` | VARCHAR(100) | NULL | State(s) |
| `municipio` | VARCHAR(255) | NULL | Municipality |
| `area_ha` | FLOAT | NULL | Area in hectares |
| `fase` | VARCHAR(100) | NULL | Current legal phase |
| `modalidade` | VARCHAR(100) | NULL | Type/modality |
| `coordenacao_regional` | VARCHAR(100) | NULL | Regional coordination |
| `data_regularizada` | DATE | NULL | Regularization date |
| `data_homologada` | DATE | NULL | Homologation date |
| `data_declarada` | DATE | NULL | Declaration date |
| `data_delimitada` | DATE | NULL | Delimitation date |
| `data_em_estudo` | DATE | NULL | Study start date |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | AUTO UPDATE | Last update timestamp |

---

#### 2. `dominial_tis` - Indigenous Lands (Working Data)

Working records for Indigenous lands being analyzed in the system.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `terra_referencia_id` | INTEGER | FK -> terraindigenareferencia | Reference to official data |
| `nome` | VARCHAR(255) | NOT NULL | Land name |
| `codigo` | VARCHAR(50) | UNIQUE, NOT NULL | Land code |
| `etnia` | VARCHAR(255) | NOT NULL | Ethnic group |
| `estado` | VARCHAR(100) | NULL | State(s), comma-separated |
| `area` | DECIMAL(12,2) | NULL | Area in hectares |
| `data_cadastro` | DATE | DEFAULT CURRENT_DATE | Registration date |

---

#### 3. `dominial_pessoas` - People/Persons

Natural or legal persons involved in property transactions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `nome` | VARCHAR(255) | NOT NULL | Full name |
| `cpf` | VARCHAR(11) | UNIQUE, NULL | Brazilian tax ID (CPF) |
| `rg` | VARCHAR(20) | NULL | ID document (RG) |
| `data_nascimento` | DATE | NULL | Birth date |
| `email` | VARCHAR(254) | NULL | Email address |
| `telefone` | VARCHAR(15) | NULL | Phone number |

---

#### 4. `dominial_cartorios` - Registry Offices

Brazilian registry offices (cartorios) where properties are registered.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `nome` | VARCHAR(200) | NOT NULL | Office name |
| `cns` | VARCHAR(20) | UNIQUE, NOT NULL | National registry code |
| `endereco` | VARCHAR(200) | NULL | Address |
| `telefone` | VARCHAR(20) | NULL | Phone |
| `email` | VARCHAR(254) | NULL | Email |
| `estado` | VARCHAR(2) | NULL | State code (e.g., BA, SP) |
| `cidade` | VARCHAR(100) | NULL | City |
| `tipo` | VARCHAR(10) | NOT NULL, DEFAULT 'CRI' | Type: 'CRI' or 'OUTRO' |

**Values for `tipo`:**
- `CRI`: Cartorio de Registro de Imoveis (Real Estate Registry)
- `OUTRO`: Other type

---

#### 5. `dominial_imovel` - Properties

Real estate properties being tracked in the system.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `terra_indigena_id_id` | INTEGER | FK -> tis, NOT NULL | Associated Indigenous land |
| `nome` | VARCHAR(100) | NOT NULL | Property name |
| `proprietario_id` | INTEGER | FK -> pessoas, NOT NULL | Current owner |
| `matricula` | VARCHAR(50) | NOT NULL | Registration number |
| `tipo_documento_principal` | VARCHAR(20) | NOT NULL, DEFAULT 'matricula' | 'matricula' or 'transcricao' |
| `observacoes` | TEXT | NULL | Notes |
| `cartorio_id` | INTEGER | FK -> cartorios, NULL | Registry office |
| `data_cadastro` | DATE | DEFAULT CURRENT_DATE | Registration date |
| `arquivado` | BOOLEAN | DEFAULT FALSE | Archived flag |

**Constraints:**
- `unique_matricula_por_cartorio`: UNIQUE(matricula, cartorio_id)

**Indexes:**
- `dom_imovel_mat_cart_idx`: INDEX(matricula, cartorio_id)

---

#### 6. `dominial_tis_imovel` - TI-Property Junction

Many-to-many relationship between Indigenous lands and properties.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `tis_codigo_id` | INTEGER | FK -> tis, NOT NULL | Indigenous land |
| `imovel_id` | INTEGER | FK -> imovel, NOT NULL | Property |

---

### Document Models

#### 7. `dominial_documentotipo` - Document Types

Types of documents in the system.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `tipo` | VARCHAR(50) | NOT NULL | 'transcricao' or 'matricula' |

---

#### 8. `dominial_documento` - Documents

Registration documents (matriculas and transcricoes).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `imovel_id` | INTEGER | FK -> imovel, NOT NULL | Associated property |
| `tipo_id` | INTEGER | FK -> documentotipo, NOT NULL | Document type |
| `numero` | VARCHAR(50) | NOT NULL | Document number |
| `data` | DATE | NOT NULL | Document date |
| `cartorio_id` | INTEGER | FK -> cartorios, NOT NULL | Registry office |
| `livro` | VARCHAR(50) | NOT NULL | Book number |
| `folha` | VARCHAR(50) | NOT NULL | Page number |
| `origem` | TEXT | NULL | Origin description |
| `observacoes` | TEXT | NULL | Notes |
| `data_cadastro` | DATE | DEFAULT CURRENT_DATE | Registration date |
| `nivel_manual` | INTEGER | NULL | Manual hierarchy level (0-10) |
| `classificacao_fim_cadeia` | VARCHAR(50) | NULL | End-of-chain classification |
| `sigla_patrimonio_publico` | VARCHAR(50) | NULL | Public patrimony acronym |
| `cri_atual_id` | INTEGER | FK -> cartorios, NULL | Current CRI |
| `cri_origem_id` | INTEGER | FK -> cartorios, NULL | Origin CRI |

**Values for `classificacao_fim_cadeia`:**
- `origem_lidima`: Property with legitimate origin
- `sem_origem`: Property without origin
- `inconclusa`: Inconclusive situation

**Constraints:**
- UNIQUE(numero, cartorio_id)

---

#### 9. `dominial_documentoimportado` - Imported Documents

Tracks documents imported from other property chains.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `documento_id` | INTEGER | FK -> documento, NOT NULL | Imported document |
| `imovel_origem_id` | INTEGER | FK -> imovel, NOT NULL | Source property |
| `data_importacao` | TIMESTAMP | DEFAULT NOW() | Import timestamp |
| `importado_por_id` | INTEGER | FK -> auth_user, NULL | Importing user |

**Constraints:**
- UNIQUE(documento_id, imovel_origem_id)

**Indexes:**
- INDEX(documento_id)
- INDEX(imovel_origem_id)
- INDEX(data_importacao)
- INDEX(importado_por_id)

---

### Recording/Transaction Models

#### 10. `dominial_lancamentotipo` - Recording Types

Types of recordings/transactions in documents.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `tipo` | VARCHAR(50) | NOT NULL | Type identifier |
| `requer_transmissao` | BOOLEAN | DEFAULT FALSE | Requires transmission |
| `requer_detalhes` | BOOLEAN | DEFAULT FALSE | Requires details |
| `requer_titulo` | BOOLEAN | DEFAULT FALSE | Requires title |
| `requer_cartorio_origem` | BOOLEAN | DEFAULT FALSE | Requires origin registry |
| `requer_livro_origem` | BOOLEAN | DEFAULT FALSE | Requires origin book |
| `requer_folha_origem` | BOOLEAN | DEFAULT FALSE | Requires origin page |
| `requer_data_origem` | BOOLEAN | DEFAULT FALSE | Requires origin date |
| `requer_forma` | BOOLEAN | DEFAULT FALSE | Requires form |
| `requer_descricao` | BOOLEAN | DEFAULT FALSE | Requires description |
| `requer_observacao` | BOOLEAN | DEFAULT TRUE | Requires notes |

**Values for `tipo`:**
- `averbacao`: Notation
- `registro`: Registration
- `inicio_matricula`: Start of matricula

---

#### 11. `dominial_lancamento` - Recordings/Transactions

Individual recordings within documents.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `documento_id` | INTEGER | FK -> documento, NOT NULL | Parent document |
| `tipo_id` | INTEGER | FK -> lancamentotipo, NOT NULL | Recording type |
| `numero_lancamento` | VARCHAR(50) | NULL | Registry-generated number |
| `data` | DATE | NOT NULL | Recording date |
| `transmitente_id` | INTEGER | FK -> pessoas, NULL | Transferor (legacy) |
| `adquirente_id` | INTEGER | FK -> pessoas, NULL | Transferee (legacy) |
| `valor_transacao` | DECIMAL(10,2) | NULL | Transaction value |
| `area` | DECIMAL(12,4) | NULL | Area |
| `origem` | VARCHAR(255) | NULL | Origin reference |
| `detalhes` | TEXT | NULL | Details |
| `observacoes` | TEXT | NULL | Notes |
| `data_cadastro` | DATE | DEFAULT CURRENT_DATE | Registration date |
| `forma` | VARCHAR(100) | NULL | Form/method |
| `descricao` | TEXT | NULL | Description |
| `titulo` | VARCHAR(255) | NULL | Title |
| `cartorio_origem_id` | INTEGER | FK -> cartorios, NULL | Origin registry |
| `cartorio_transacao_id` | INTEGER | FK -> cartorios, NULL | Transaction registry (legacy) |
| `cartorio_transmissao_id` | INTEGER | FK -> cartorios, NULL | Transmission registry |
| `livro_transacao` | VARCHAR(50) | NULL | Transaction book |
| `folha_transacao` | VARCHAR(50) | NULL | Transaction page |
| `data_transacao` | DATE | NULL | Transaction date |
| `livro_origem` | VARCHAR(50) | NULL | Origin book |
| `folha_origem` | VARCHAR(50) | NULL | Origin page |
| `data_origem` | DATE | NULL | Origin date |
| `eh_inicio_matricula` | BOOLEAN | DEFAULT FALSE | Is start of matricula |
| `documento_origem_id` | INTEGER | FK -> documento, NULL | Origin document link |

---

#### 12. `dominial_lancamentopessoa` - Recording Participants

Multiple people per recording (many-to-many with roles).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `lancamento_id` | INTEGER | FK -> lancamento, NOT NULL | Recording |
| `pessoa_id` | INTEGER | FK -> pessoas, NOT NULL | Person |
| `tipo` | VARCHAR(20) | NOT NULL | 'transmitente' or 'adquirente' |
| `nome_digitado` | VARCHAR(255) | NULL | Manually typed name |

**Constraints:**
- UNIQUE(lancamento_id, pessoa_id, tipo)

---

#### 13. `dominial_origemfimcadeia` - End of Chain Per Origin

Tracks end-of-chain information for each origin in a recording.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `lancamento_id` | INTEGER | FK -> lancamento, NOT NULL | Recording |
| `indice_origem` | INTEGER | NOT NULL | Origin index (0, 1, 2...) |
| `fim_cadeia` | BOOLEAN | DEFAULT FALSE | Is end of chain |
| `tipo_fim_cadeia` | VARCHAR(50) | NULL | End type |
| `especificacao_fim_cadeia` | TEXT | NULL | Specification |
| `classificacao_fim_cadeia` | VARCHAR(50) | NULL | Classification |

**Values for `tipo_fim_cadeia`:**
- `destacamento_publico`: Public patrimony detachment
- `outra`: Other
- `sem_origem`: Without origin

**Constraints:**
- UNIQUE(lancamento_id, indice_origem)

---

#### 14. `dominial_fimcadeia` - End of Chain Definitions

Master list of end-of-chain types.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `nome` | VARCHAR(100) | UNIQUE, NOT NULL | Name (e.g., "INCRA") |
| `tipo` | VARCHAR(50) | NOT NULL, DEFAULT 'destacamento_publico' | Type |
| `classificacao` | VARCHAR(50) | NOT NULL, DEFAULT 'origem_lidima' | Classification |
| `sigla` | VARCHAR(50) | NULL | Acronym (e.g., SPU) |
| `descricao` | TEXT | NULL | Description |
| `ativo` | BOOLEAN | DEFAULT TRUE | Active flag |
| `data_criacao` | TIMESTAMP | DEFAULT NOW() | Creation date |
| `data_atualizacao` | TIMESTAMP | AUTO UPDATE | Update date |

---

### Amendment/Change Models

#### 15. `dominial_alteracoestipo` - Amendment Types

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `tipo` | VARCHAR(50) | NOT NULL | 'registro', 'averbacao', 'nao_classificado' |

---

#### 16. `dominial_registrotipo` - Registration Types

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `tipo` | VARCHAR(100) | NOT NULL | Registration type name |

---

#### 17. `dominial_averbacaotipo` - Notation Types

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `tipo` | VARCHAR(100) | NOT NULL | Notation type name |

---

#### 18. `dominial_alteracoes` - Amendments

Property amendments/changes.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `imovel_id_id` | INTEGER | FK -> imovel, NOT NULL | Property |
| `tipo_alteracao_id_id` | INTEGER | FK -> alteracoestipo, NOT NULL | Amendment type |
| `livro` | VARCHAR(50) | NULL | Book |
| `folha` | VARCHAR(50) | NULL | Page |
| `cartorio_id` | INTEGER | FK -> cartorios, NOT NULL | Registry |
| `data_alteracao` | DATE | NULL | Amendment date |
| `registro_tipo_id` | INTEGER | FK -> registrotipo, NULL | Registration type |
| `averbacao_tipo_id` | INTEGER | FK -> averbacaotipo, NULL | Notation type |
| `titulo` | VARCHAR(255) | NULL | Title |
| `cartorio_origem_id` | INTEGER | FK -> cartorios, NOT NULL | Origin registry |
| `livro_origem` | VARCHAR(50) | NULL | Origin book |
| `folha_origem` | VARCHAR(50) | NULL | Origin page |
| `data_origem` | DATE | NULL | Origin date |
| `transmitente_id` | INTEGER | FK -> pessoas, NULL | Transferor |
| `adquirente_id` | INTEGER | FK -> pessoas, NULL | Transferee |
| `valor_transacao` | DECIMAL(10,2) | NULL | Transaction value |
| `area` | DECIMAL(12,4) | NULL | Area |
| `observacoes` | TEXT | NULL | Notes |
| `data_cadastro` | DATE | DEFAULT CURRENT_DATE | Registration date |

---

### System Models

#### 19. `dominial_importacaocartorios` - Registry Import Log

Tracks batch imports of registry offices.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `estado` | VARCHAR(2) | NOT NULL | State code |
| `data_inicio` | TIMESTAMP | DEFAULT NOW() | Start time |
| `data_fim` | TIMESTAMP | NULL | End time |
| `total_cartorios` | INTEGER | DEFAULT 0 | Total imported |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'pendente' | Status |
| `erro` | TEXT | NULL | Error message |

**Values for `status`:**
- `pendente`: Pending
- `em_andamento`: In progress
- `concluido`: Completed
- `erro`: Error

---

## Key Relationships

### Foreign Key Summary

```sql
-- TIs -> TerraIndigenaReferencia
dominial_tis.terra_referencia_id -> dominial_terraindigenareferencia.id

-- Imovel relationships
dominial_imovel.terra_indigena_id_id -> dominial_tis.id
dominial_imovel.proprietario_id -> dominial_pessoas.id
dominial_imovel.cartorio_id -> dominial_cartorios.id

-- TIs_Imovel junction
dominial_tis_imovel.tis_codigo_id -> dominial_tis.id
dominial_tis_imovel.imovel_id -> dominial_imovel.id

-- Documento relationships
dominial_documento.imovel_id -> dominial_imovel.id
dominial_documento.tipo_id -> dominial_documentotipo.id
dominial_documento.cartorio_id -> dominial_cartorios.id
dominial_documento.cri_atual_id -> dominial_cartorios.id
dominial_documento.cri_origem_id -> dominial_cartorios.id

-- DocumentoImportado
dominial_documentoimportado.documento_id -> dominial_documento.id
dominial_documentoimportado.imovel_origem_id -> dominial_imovel.id
dominial_documentoimportado.importado_por_id -> auth_user.id

-- Lancamento relationships
dominial_lancamento.documento_id -> dominial_documento.id
dominial_lancamento.tipo_id -> dominial_lancamentotipo.id
dominial_lancamento.transmitente_id -> dominial_pessoas.id
dominial_lancamento.adquirente_id -> dominial_pessoas.id
dominial_lancamento.cartorio_origem_id -> dominial_cartorios.id
dominial_lancamento.cartorio_transacao_id -> dominial_cartorios.id
dominial_lancamento.cartorio_transmissao_id -> dominial_cartorios.id
dominial_lancamento.documento_origem_id -> dominial_documento.id

-- LancamentoPessoa
dominial_lancamentopessoa.lancamento_id -> dominial_lancamento.id
dominial_lancamentopessoa.pessoa_id -> dominial_pessoas.id

-- OrigemFimCadeia
dominial_origemfimcadeia.lancamento_id -> dominial_lancamento.id

-- Alteracoes relationships
dominial_alteracoes.imovel_id_id -> dominial_imovel.id
dominial_alteracoes.tipo_alteracao_id_id -> dominial_alteracoestipo.id
dominial_alteracoes.cartorio_id -> dominial_cartorios.id
dominial_alteracoes.cartorio_origem_id -> dominial_cartorios.id
dominial_alteracoes.registro_tipo_id -> dominial_registrotipo.id
dominial_alteracoes.averbacao_tipo_id -> dominial_averbacaotipo.id
dominial_alteracoes.transmitente_id -> dominial_pessoas.id
dominial_alteracoes.adquirente_id -> dominial_pessoas.id
```

---

## Business Rules

### Matricula Uniqueness

The `matricula` field on properties is unique **per registry office (cartorio)**, not globally. This matches the Brazilian property registration system where different registries can have properties with the same matricula number.

### Document Chain (Cadeia Dominial)

The system tracks the chain of ownership through:
1. **Documents** (`Documento`) linked to properties
2. **Recordings** (`Lancamento`) within documents
3. **Origin documents** (`documento_origem`) linking recordings to previous documents

### End of Chain Classifications

When a property chain reaches its origin:
- `origem_lidima`: Legitimate public origin (e.g., INCRA, State)
- `sem_origem`: No traceable origin
- `inconclusa`: Investigation incomplete

---

## Indexes

Key performance indexes:

```sql
-- Property lookup by matricula and registry
CREATE INDEX dom_imovel_mat_cart_idx ON dominial_imovel(matricula, cartorio_id);

-- Document imports
CREATE INDEX ON dominial_documentoimportado(documento_id);
CREATE INDEX ON dominial_documentoimportado(imovel_origem_id);
CREATE INDEX ON dominial_documentoimportado(data_importacao);
CREATE INDEX ON dominial_documentoimportado(importado_por_id);

-- Terra Indigena reference ordering
CREATE INDEX ON dominial_terraindigenareferencia(nome);
```
