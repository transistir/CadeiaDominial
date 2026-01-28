> **LEGACY / REFERENCIA**: este documento foi consolidado. Fonte de verdade: `docs/db/SCHEMA_CONSOLIDATED.md` e ERD em `docs/db/SCHEMA_CONSOLIDATED_ERD.*`.
>
> Este arquivo e mantido apenas para contexto historico e pode conter regras desatualizadas.

# Documentação: Sistema de Cartórios no CadeiaDominial

**Versão do Documento:** 1.0
**Data:** Janeiro 2025
**Objetivo:** Documentar a situação atual dos campos de cartório para servir como referência na reescrita do sistema

---

## Sumário

1. [Contexto e Problema](#contexto-e-problema)
2. [Situação Atual: A Bagunça](#situação-atual-a-bagunça)
3. [Campos por Modelo](#campos-por-modelo)
4. [Fluxos de Criação e Uso](#fluxos-de-criação-e-uso)
5. [Problemas Identificados](#problemas-identificados)
6. [Proposta para Nova Versão](#proposta-para-nova-versão)
7. [Recomendações de Implementação](#recomendações-de-implementação)

---

## Contexto e Problema

Este documento surge da necessidade de explicar a confusão que se formou no código relacionado aos campos de cartório. Ao longo do desenvolvimento, diferentes necessidades surgiram e foram criadas soluções incrementais que resultaram em uma estrutura complexa e, muitas vezes, redundante.

### O Sistema de Registro de Imóveis Brasileiro

Para entender o contexto, é importante saber como funciona o sistema de registro de imóveis no Brasil:

1. **Cartório de Registro de Imóveis (CRI):** É o cartório responsável por registrar transações imobiliárias
2. **Matrícula:** Documento único do imóvel dentro de um cartório
3. **Livro/Folha:** Localização física do registro dentro do cartório
4. **Transcrição:** Quando um imóvel é transferido de um cartório para outro, o documento anterior é "transcrito" no novo cartório

### A Cadeia Dominial

O sistema Cadeia Dominial rastreia a história de propriedade de imóveis em Terras Indígenas, documentando:

- A matrícula atual do imóvel
- Todas as transações (lançamentos) realizadas
- A cadeia de documentos que provam a origem da propriedade

---

## Situação Atual: A Bagunça

### Visão Geral dos Campos

No código atual, existem **múltiplos campos de cartório** espalhados por diferentes modelos:

| Modelo       | Campos de Cartório                                                  | Total        |
| ------------ | ------------------------------------------------------------------- | ------------ |
| `Imovel`     | 1                                                                   | 1            |
| `Documento`  | 3 (`cartorio`, `cri_atual`, `cri_origem`)                           | 3            |
| `Lancamento` | 3 (`cartorio_origem`, `cartorio_transacao`, `cartorio_transmissao`) | 3            |
| `Alteracao`  | 2 (`cartorio`, `cartorio_origem`)                                   | 2            |
| **Total**    |                                                                     | **9 campos** |

### A Origem da Confusão

1. **Fase 1 - Início:** `Imovel.cartorio` e `Documento.cartorio` eram suficientes
2. **Fase 2 - Transmissões:** Surgiu a necessidade de rastrear onde a transmissão foi registrada → `Lancamento.cartorio_transacao`
3. **Fase 3 - Novos Campos:** Criados `Lancamento.cartorio_origem` e `Lancamento.cartorio_transmissao` (legado vs. novo)
4. **Fase 4 - CRI Rastreamento:** Criados `Documento.cri_atual` e `Documento.cri_origem` para rastrear mudanças de CRI

---

## Campos por Modelo

### 1. Imovel

```python
class Imovel(models.Model):
    # ... outros campos ...
    cartorio = models.ForeignKey('Cartorios', on_delete=PROTECT, null=True, blank=True)
```

| Aspecto                | Descrição                                      |
| ---------------------- | ---------------------------------------------- |
| **O que é**            | O CRI onde o imóvel está atualmente registrado |
| **Quando preenche**    | No cadastro inicial do imóvel                  |
| **Quem preenche**      | Usuário no formulário do imóvel                |
| **É obrigatório**      | Não (campo pode ser NULL)                      |
| **Usado na interface** | Sim, aparece nos detalhes do imóvel            |

**Problema identificado:** Este campo indica o cartório atual, mas não captura a história de mudanças de CRI.

---

### 2. Documento

```python
class Documento(models.Model):
    # ... outros campos ...
    cartorio = models.ForeignKey('Cartorios', on_delete=PROTECT)
    cri_atual = models.ForeignKey('Cartorios', related_name='documentos_cri_atual', null=True, blank=True)
    cri_origem = models.ForeignKey('Cartorios', related_name='documentos_cri_origem', null=True, blank=True)
```

| Campo        | Descrição                                | Quando Preenche           | Usado na Interface                  |
| ------------ | ---------------------------------------- | ------------------------- | ----------------------------------- |
| `cartorio`   | Cartório onde o documento foi registrado | Criação do documento      | **SIM** - É o que aparece na tabela |
| `cri_atual`  | CRI atual do documento                   | Automático via CRIService | NÃO                                 |
| `cri_origem` | CRI de origem (docs auto-criados)        | Automático via CRIService | NÃO                                 |

**Análise crítica:**

1. **`documento.cartorio`** é o único campo usado na interface
2. **`documento.cri_atual`** e **`documento.cri_origem`** nunca são exibidos
3. Na prática: `documento.cri_atual` ≈ `documento.cartorio` e `documento.cri_origem` ≈ `documento.cartorio`

---

### 3. Lancamento

```python
class Lancamento(models.Model):
    # ... outros campos ...
    cartorio_origem = models.ForeignKey('Cartorios', related_name='cartorio_origem_lancamento', null=True, blank=True)
    cartorio_transacao = models.ForeignKey('Cartorios', related_name='cartorio_transacao_lancamento', null=True, blank=True)
    cartorio_transmissao = models.ForeignKey('Cartorios', related_name='cartorio_transmissao_lancamento', null=True, blank=True)
```

| Campo                  | Descrição                                  | Contexto            | Obrigatório                      |
| ---------------------- | ------------------------------------------ | ------------------- | -------------------------------- |
| `cartorio_origem`      | Cartório de origem do imóvel               | Início de Matrícula | **SIM** para início de matrícula |
| `cartorio_transacao`   | [LEGADO] Onde foi registrada a transmissão | Registro            | Não usado                        |
| `cartorio_transmissao` | [NVO] Onde foi registrada a transmissão    | Registro            | Parcialmente usado               |

**Análise crítica:**

1. **`cartorio_origem`** é obrigatório para lançamentos do tipo "Início de Matrícula"
2. **`cartorio_transacao`** é legado e não deve ser mais usado
3. **`cartorio_transmissao`** é o campo "novo" mas a lógica de preenchimento é confusa

---

### 4. Alteracao ( modelo separado de alterações)

```python
class Alteracao(models.Model):
    # ... outros campos ...
    cartorio = models.ForeignKey('Cartorios', on_delete=CASCADE)
    cartorio_origem = models.ForeignKey('Cartorios', related_name='cartorio_responsavel', on_delete=CASCADE)
```

| Campo             | Descrição                           |
| ----------------- | ----------------------------------- |
| `cartorio`        | Cartório da alteração               |
| `cartorio_origem` | Cartório responsável pela alteração |

**Nota:** Este modelo parece ter uma duplicação similar - `cartorio` e `cartorio_origem` parecem ser o mesmo conceito.

---

## Fluxos de Criação e Uso

### Fluxo 1: Cadastro de Imóvel

```
Usuário preenche formulário do imóvel
         ↓
Imovel.cartorio = cartório selecionado (obrigatório no formulário)
         ↓
Imóvel salvo
```

### Fluxo 2: Criação de Documento Manual

```
Usuário cria documento via formulário
         ↓
Documento.cartorio = cartório selecionado pelo usuário
         ↓
Documento salvo
```

### Fluxo 3: Lançamento "Início de Matrícula"

```
Usuário preenche formulário de lançamento
         ↓
Lancamento.cartorio_origem = cartório de ORIGEM (OBRIGATÓRIO)
         ↓
Se documento não existe:
  - Documento.cartorio = Lancamento.cartorio_origem
  - Documento.cri_origem = Lancamento.cartorio_origem (via CRIService)
  - Documento.cri_atual = Imovel.cartorio (via CRIService)
         ↓
Lancamento salvo
```

### Fluxo 4: Lançamento "Registro"

```
Usuário preenche formulário de registro
         ↓
Lancamento.cartorio_transmissao = cartório da TRANSMISSÃO (opcional)
         ↓
Lancamento salvo
```

### Fluxo 5: Apresentação na Tabela da Cadeia Dominial

```
get_cadeia_dominial_tabela()
         ↓
Para cada documento:
  documento.cartorio.nome  ← ÚNICO CAMPO USADO!
         ↓
Renderiza tabela
```

---

## Problemas Identificados

### 1. Redundância de Dados

```python
# No documento:
documento.cartorio      = CRI X
documento.cri_atual     = CRI X  (redundante!)
documento.cri_origem    = CRI X  (redundante!)
```

### 2. Campos Legados Não Removidos

- `Lancamento.cartorio_transacao` ainda existe mas não é usado
  -Código ainda referencia em alguns lugares, causando confusão

### 3. Nomenclatura Inconsistente

| O que deveria ser               | Como está chamado                                                      |
| ------------------------------- | ---------------------------------------------------------------------- |
| Cartório do imóvel              | `Imovel.cartorio` ✓                                                    |
| Cartório do documento           | `Documento.cartorio` ✓                                                 |
| Cartório de origem (lançamento) | `Lancamento.cartorio_origem` ✓                                         |
| Cartório de transmissão         | `Lancamento.cartorio_transmissao` vs `Lancamento.cartorio_transacao` ✗ |
| Campos CRI                      | `cri_atual`, `cri_origem` - nomenclatura confusa                       |

### 4. CRIService É Desnecessário

O `CRIService` foi criado para gerenciar `cri_atual` e `cri_origem`, mas:

1. Nenhum desses campos é usado na interface
2. Eles duplicam `documento.cartorio`
3. Adicionam complexidade sem valor

### 5. Documentação Ausente

Não há documentação explicando:

- Quando usar cada campo
- A relação entre os campos
- Os fluxos de preenchimento

---

## Proposta para Nova Versão

### Princípios

1. **Simplicidade:** Cada conceito deve ter uma única representação
2. **Clareza:** Nomes devem ser autoexplicativos
3. **Necessidade:** Só criar campos que são realmente necessários

### Modelo Simplificado

```typescript
// IMÓVEL
interface Imovel {
  id: string;
  matricula: string;
  nome: string;
  proprietario: Pessoa;
  cartorio: Cartorio; // CRI atual do imóvel
}

// DOCUMENTO
interface Documento {
  id: string;
  tipo: "matricula" | "transcricao";
  numero: string;
  data: Date;
  cartorio: Cartorio; // Cartório onde foi registrado (herdado do lançamento de origem)
  livro: string;
  folha: string;
  imovel: Imovel;
}

// LANÇAMENTO
interface Lancamento {
  id: string;
  documento: Documento;
  tipo: "inicio_matricula" | "registro" | "averbacao";
  data: Date;

  // Para início de matrícula:
  cartorio_origem?: Cartorio; // Cartório de ORIGEM (obrigatório para início de matrícula)
  livro_origem?: string;
  folha_origem?: string;

  // Para registro:
  cartorio_transmissao?: Cartorio; // Cartório onde a transmissão foi registrada
  livro_transmissao?: string;
  folha_transmissao?: string;

  // Pessoas
  transmitentes: Pessoa[];
  adquirentes: Pessoa[];
}
```

### Apenas 3 Campos de Cartório

| Campo                             | Modelo     | Obrigatório | Descrição                                                                          |
| --------------------------------- | ---------- | ----------- | ---------------------------------------------------------------------------------- |
| `Imovel.cartorio`                 | Imovel     | **Sim**     | CRI onde o imóvel está registrado                                                  |
| `Documento.cartorio`              | Documento  | **Sim**     | Cartório onde o documento foi registrado (herdado de `Lancamento.cartorio_origem`) |
| `Lancamento.cartorio_transmissao` | Lancamento | Não         | Cartório específico da transmissão (apenas para Registros)                         |

### Campos Removidos

1. **`Documento.cri_atual`** → Remover (redundante com `Documento.cartorio`)
2. **`Documento.cri_origem`** → Remover (redundante com `Documento.cartorio`)
3. **`Lancamento.cartorio_origem`** → Renomear para manter, mas só usado em início de matrícula
4. **`Lancamento.cartorio_transacao`** → Remover (legado)
5. **`Lancamento.cartorio_transmissao`** → Manter (usado em registros)
6. **`Alteracao.cartorio_origem`** → Avaliar se é necessário

---

## Recomendações de Implementação

### Para a Nova Versão (TypeScript/Stack Nova)

#### 1. Banco de Dados

```sql
-- Tabela de cartórios (manter)
CREATE TABLE cartorios (
  id UUID PRIMARY KEY,
  nome VARCHAR(200) NOT NULL,
  cns VARCHAR(20) UNIQUE NOT NULL,
  tipo VARCHAR(10) DEFAULT 'CRI',
  estado CHAR(2),
  cidade VARCHAR(100),
  endereco VARCHAR(200)
);

-- Tabela de imóveis
CREATE TABLE imoveis (
  id UUID PRIMARY KEY,
  matricula VARCHAR(50) NOT NULL,
  nome VARCHAR(100),
  proprietario_id UUID REFERENCES pessoas(id),
  cartorio_id UUID REFERENCES cartorios(id) NOT NULL,  -- CRI do imóvel
  terra_indigena_id UUID REFERENCES tis(id)
);

-- Tabela de documentos
CREATE TABLE documentos (
  id UUID PRIMARY KEY,
  tipo VARCHAR(20) NOT NULL,  -- 'matricula' | 'transcricao'
  numero VARCHAR(50) NOT NULL,
  data DATE NOT NULL,
  cartorio_id UUID REFERENCES cartorios(id) NOT NULL,  -- Cartório do registro
  livro VARCHAR(50),
  folha VARCHAR(50),
  imovel_id UUID REFERENCES imoveis(id) NOT NULL,
  UNIQUE(numero, cartorio_id)
);

-- Tabela de lançamentos
CREATE TABLE lancamentos (
  id UUID PRIMARY KEY,
  documento_id UUID REFERENCES documentos(id) NOT NULL,
  tipo VARCHAR(20) NOT NULL,
  data DATE NOT NULL,

  -- Para início de matrícula:
  cartorio_origem_id UUID REFERENCES cartorios(id),  -- Cartório de origem
  livro_origem VARCHAR(50),
  folha_origem VARCHAR(50),

  -- Para registro:
  cartorio_transmissao_id UUID REFERENCES cartorios(id),  -- Cartório da transmissão
  livro_transmissao VARCHAR(50),
  folha_transmissao VARCHAR(50),

  -- Transmitentes e adquirentes via tabela de relacionamento
);
```

#### 2. Validações no Formulário de Lançamento

```typescript
// types/Lancamento.ts
type LancamentoTipo = "inicio_matricula" | "registro" | "averbacao";

interface LancamentoFormData {
  tipo: LancamentoTipo;
  data: Date;
  cartorio_origem_id?: UUID; // Obrigatório apenas para início de matrícula
  cartorio_transmissao_id?: UUID; // Opcional para registros
}

// Validação
function validateLancamento(data: LancamentoFormData): ValidationResult {
  if (data.tipo === "inicio_matricula" && !data.cartorio_origem_id) {
    return {
      valid: false,
      error: "Cartório de origem é obrigatório para início de matrícula",
    };
  }
  return { valid: true };
}
```

#### 3. Fluxo de Criação de Documento a partir de Origem

```typescript
async function criarDocumentoAPartirDeOrigem(
  dados: {
    tipo: "matricula" | "transcricao";
    numero: string;
    cartorio_origem_id: UUID;
    livro_origem?: string;
    folha_origem?: string;
  },
  imovel_id: UUID,
): Promise<Documento> {
  // O documento herda o cartório da origem
  const documento = await prisma.documento.create({
    data: {
      tipo: dados.tipo,
      numero: dados.numero,
      data: new Date(),
      cartorio_id: dados.cartorio_origem_id, // Herdado!
      livro: dados.livro_origem || "0",
      folha: dados.folha_origem || "0",
      imovel_id: imovel_id,
    },
  });

  return documento;
}
```

#### 4. Interface de Apresentação

```typescript
// A tabela da cadeia dominial usa apenas:
function renderizarDocumentoNaTabela(documento: Documento): JSX.Element {
  return (
    <tr>
      <td>{documento.tipo}: {documento.numero}</td>
      <td>{formatDate(documento.data)}</td>
      <td>{documento.cartorio.nome}</td>  {/* ÚNICO CAMPO USADO! */}
      <td>{documento.lancamentos.length} lançamentos</td>
    </tr>
  );
}
```

### Migrando do Código Antigo

Se precisar migrar dados do sistema antigo:

```python
# Script de migração (referência)
def migrate_cartorios():
    """
    Migrar do modelo antigo para o novo simplificado
    """
    # 1. Documento.cri_atual -> Documento.cartorio (se diferente)
    # 2. Documento.cri_origem -> Ignorar (redundante)
    # 3. Lancamento.cartorio_transacao -> Ignorar (legado)
    # 4. Lancamento.cartorio_transmissao -> Manter (se existir)
    # 5. Lancamento.cartorio_origem -> Manter (para início de matrícula)
    pass
```

---

## Glossário

| Termo                   | Definição                                                     |
| ----------------------- | ------------------------------------------------------------- |
| **Cartório**            | Oficio de registro (pode ser CRI ou outro tipo)               |
| **CRI**                 | Cartório de Registro de Imóveis                               |
| **Matrícula**           | Documento identificador do imóvel no cartório                 |
| **Transcrição**         | Registro de um documento de outro cartório no cartório atual  |
| **Lançamento**          | Registro de uma transação no documento                        |
| **Início de Matrícula** | Tipo de lançamento que indica a criação de uma nova matrícula |
| **Registro**            | Tipo de lançamento para transferência de propriedade          |
| **Averbação**           | Tipo de lançamento para alterações no registro                |

---

## Conclusão

O sistema atual tem 9 campos de cartório, mas apenas 3 são necessários e usados efetivamente:

1. **`Imovel.cartorio`** - CRI do imóvel (obrigatório no cadastro)
2. **`Documento.cartorio`** - Cartório do documento (herdado do lançamento de origem)
3. **`Lancamento.cartorio_transmissao`** - Cartório da transmissão (apenas para Registros)

Os campos `cri_atual`, `cri_origem` e `cartorio_transacao` são redundantes e devem ser removidos em uma nova implementação.

A nova versão deve focar em simplicidade, com validações claras no formulário de lançamentos para garantir que:

- `cartorio_origem` seja obrigatório apenas para início de matrícula
- A herança de cartório para documentos seja automática e previsível
