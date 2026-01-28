> **LEGACY / REFERENCIA**: este documento foi consolidado. Fonte de verdade: `docs/db/SCHEMA_CONSOLIDATED.md` e ERD em `docs/db/SCHEMA_CONSOLIDATED_ERD.*`.
>
> Este arquivo e mantido apenas para contexto historico e pode conter regras desatualizadas.

# Análise: Múltiplas Origens vs Múltiplos Cartórios no Lancamento

**Versão:** 1.0
**Data:** 2026-01-27
**Objetivo:** Documentar como o sistema atual lida (ou não lida) com múltiplas origens e múltiplos cartórios em lançamentos do tipo "Início de Matrícula"

---

## Sumário

1. [Contexto](#contexto)
2. [Estrutura Atual do Banco de Dados](#estrutura-atual-do-banco-de-dados)
3. [Como Múltiplas Origens São Armazenadas](#como-múltiplas-origens-são-armazenadas)
4. [O Problema: Múltiplos Cartórios Não São Suportados](#o-problema-múltiplos-cartórios-não-são-suportados)
5. [Análise Detalhada por Modelo](#análise-detalhada-por-modelo)
6. [Cenários de Problema](#cenários-de-problema)
7. [Fluxo de Criação no Backend](#fluxo-de-criação-no-backend)
8. [Recomendações para Migração](#recomendações-para-migração)
9. [Proposta de Schema Novo](#proposta-de-schema-novo)

---

## Contexto

### O Cenário Real

Um lançamento do tipo **"Início de Matrícula"** pode ter **múltiplas origens** (múltiplos documentos anteriores que deram origem ao imóvel atual). Cada origem pode ter:

- **Matrícula ou Transcrição diferente** (ex: "M50", "T20", "M30")
- **Cartório diferente** (ex: 1º CRI Salvador, 2º CRI Salvador)
- **Livro/Folha diferentes** (ex: Livro 3, Folha 45 vs Livro 5, Folha 12)

### O Problema

O sistema atual **não suporta** múltiplos cartórios, livros e folhas para um único lançamento. Isso causa **perda de dados** quando o usuário informa origens de cartórios diferentes.

---

## Estrutura Atual do Banco de Dados

### Tabela `Lancamento`

| Campo                | Tipo           | Descrição                    | Observação                            |
| -------------------- | -------------- | ---------------------------- | ------------------------------------- |
| `id`                 | PK             | Identificador                |                                       |
| `documento_id`       | FK             | Documento do lançamento      |                                       |
| `tipo`               | FK             | Tipo de lançamento           | inicio_matricula, registro, averbacao |
| `origem`             | Text           | Origens concatenadas         | `"M50; T20; M30"`                     |
| `cartorio_origem_id` | FK → Cartorios | **ÚNICO** cartório de origem | ⚠️ Apenas 1                           |
| `livro_origem`       | Text           | **ÚNICO** livro de origem    | ⚠️ Apenas 1                           |
| `folha_origem`       | Text           | **ÚNICA** folha de origem    | ⚠️ Apenas 1                           |
| `data_origem`        | Date           | Data do documento de origem  |                                       |

### Tabela `OrigemFimCadeia`

| Campo                      | Tipo            | Descrição                       | Observação                              |
| -------------------------- | --------------- | ------------------------------- | --------------------------------------- |
| `id`                       | PK              | Identificador                   |                                         |
| `lancamento_id`            | FK → Lancamento | Lançamento associado            |                                         |
| `indice_origem`            | Integer         | Índice da origem (0, 1, 2...)   |                                         |
| `fim_cadeia`               | Boolean         | Se é fim de cadeia              |                                         |
| `tipo_fim_cadeia`          | Char(50)        | Tipo do fim de cadeia           | destacamento_publico, outra, sem_origem |
| `especificacao_fim_cadeia` | Text            | Especificação para tipo "outra" |                                         |
| `classificacao_fim_cadeia` | Char(50)        | Classificação                   | origem_lidima, sem_origem, inconclusa   |

**Constraint:** `UNIQUE(lancamento_id, indice_origem)`

---

## Como Múltiplas Origens São Armazenadas

### Armazenamento Atual (String Concatenada)

```
Lancamento.origem = "M50; T20; M30"
                    │     │   │
                    │     │   └── Origem 2: T20
                    │     └────── Origem 1: T20
                    └───────────── Origem 0: M50
```

### Relacionamento com `OrigemFimCadeia`

```
Lancamento (id=1)
│
├── OrigemFimCadeia (indice_origem=0) → "M50"
│   ├── fim_cadeia: false
│   └── ...
│
├── OrigemFimCadeia (indice_origem=1) → "T20"
│   ├── fim_cadeia: false
│   └── ...
│
└── OrigemFimCadeia (indice_origem=2) → "M30"
    ├── fim_cadeia: true
    ├── tipo_fim_cadeia: "destacamento_publico"
    └── classificacao_fim_cadeia: "origem_lidima"
```

---

## O Problema: Múltiplos Cartórios Não São Suportados

### O que funciona:

| Funcionalidade                              | Status                   |
| ------------------------------------------- | ------------------------ |
| Múltiplas origens (matrículas/transcrições) | ✅ Salvas como string    |
| Classificação de fim de cadeia por origem   | ✅ Via `OrigemFimCadeia` |
| Índice de cada origem                       | ✅ `indice_origem`       |

### O que NÃO funciona:

| Funcionalidade            | Status | Problema                       |
| ------------------------- | ------ | ------------------------------ |
| Múltiplos cartórios       | ❌     | Apenas 1 FK em `Lancamento`    |
| Múltiplos livros          | ❌     | Apenas 1 campo em `Lancamento` |
| Múltiplas folhas          | ❌     | Apenas 1 campo em `Lancamento` |
| Múltiplas datas de origem | ❌     | Apenas 1 campo em `Lancamento` |

### Visualização do Problema

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LANCAMENTO (id=1)                                │
├─────────────────────────────────────────────────────────────────────┤
│ origem: "M50; T20; M30"                                             │
│ cartorio_origem_id: 5     ← SALVA APENAS O PRIMEIRO!                │
│ livro_origem: "3"          ← SALVA APENAS O PRIMEIRO!               │
│ folha_origem: "45"         ← SALVA APENAS O PRIMEIRO!               │
│ data_origem: "1990-01-15"  ← SALVA APENAS O PRIMEIRO!               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  ORIGEMFIMCADEIA                                    │
├─────────────────────────────────────────────────────────────────────┤
│ indice_origem: 0  → M50  (cartório deveria ser: 1º CRI Salvador)   │
│                  ⚠️ NÃO TEM CAMPO cartorio_id!                      │
├─────────────────────────────────────────────────────────────────────┤
│ indice_origem: 1  → T20  (cartório deveria ser: 2º CRI Salvador)   │
│                  ⚠️ NÃO TEM CAMPO cartorio_id!                      │
├─────────────────────────────────────────────────────────────────────┤
│ indice_origem: 2  → M30  (cartório deveria ser: 3º CRI Itabuna)    │
│                  ⚠️ NÃO TEM CAMPO cartorio_id!                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Análise Detalhada por Modelo

### 1. Lancamento

**Arquivo:** `old/dominial/models/lancamento_models.py:43`

```python
class Lancamento(models.Model):
    # ... outros campos ...
    origem = models.TextField(blank=True)  # "M50; T20; M30"
    cartorio_origem = models.ForeignKey(
        'Cartorios',
        related_name='cartorio_origem_lancamento',
        null=True,
        blank=True
    )  # ← ÚNICO cartório!
    livro_origem = models.CharField(max_length=20, blank=True)
    folha_origem = models.CharField(max_length=20, blank=True)
    data_origem = models.DateField(null=True, blank=True)
```

**Problema:** `cartorio_origem`, `livro_origem`, `folha_origem`, `data_origem` são campos únicos.

---

### 2. OrigemFimCadeia

**Arquivo:** `old/dominial/models/lancamento_models.py:151`

```python
class OrigemFimCadeia(models.Model):
    lancamento = models.ForeignKey(Lancamento, on_delete=models.CASCADE)
    indice_origem = models.IntegerField()
    fim_cadeia = models.BooleanField(default=False)
    tipo_fim_cadeia = models.CharField(max_length=50, choices=[...])
    especificacao_fim_cadeia = models.TextField(blank=True)
    classificacao_fim_cadeia = models.CharField(max_length=50, choices=[...])
```

**Problema:** NÃO tem campos para cartório, livro, folha, data. Apenas armazena **classificação de fim de cadeia**.

---

## Cenários de Problema

### Cenário 1: Múltiplos Cartórios Diferentes

**Entrada do usuário:**

```
Origem 1: M50 - Cartório: 1º CRI Salvador - Livro: 3 - Folha: 45
Origem 2: T20 - Cartório: 2º CRI Salvador - Livro: 5 - Folha: 12
Origem 3: M30 - Cartório: 3º CRI Itabuna - Livro: 2 - Folha: 30
```

**O que é salvo:**

```
Lancamento.origem = "M50; T20; M30"  ✅
Lancamento.cartorio_origem_id = (1º CRI Salvador)  ⚠️ Apenas o primeiro!
Lancamento.livro_origem = "3"  ⚠️ Apenas o primeiro!
Lancamento.folha_origem = "45"  ⚠️ Apenas o primeiro!
```

**Dados perdidos:**

- T20 e M30 perdem informações de cartório, livro e folha

---

### Cenário 2: Origens com Livros/Folhas Diferentes

**Entrada do usuário:**

```
Origem 1: M50 - Livro: 3 - Folha: 45
Origem 2: T20 - Livro: 10 - Folha: 200
```

**O que é salvo:**

```
Lancamento.origem = "M50; T20"  ✅
Lancamento.livro_origem = "3"  ⚠️ Apenas o primeiro!
Lancamento.folha_origem = "45"  ⚠️ Apenas o primeiro!
```

**Dados perdidos:**

- T20 perde informações de livro e folha

---

### Cenário 3: Cadeia com Fins de Cadeia Diferentes

**Entrada do usuário:**

```
Origem 1: M50 - Fim de Cadeia: INCRA (origem_lidima)
Origem 2: Sem Origem (sem_origem)
```

**O que é salvo:**

```
Lancamento.origem = "M50; Sem Origem"  ✅

OrigemFimCadeia (indice=0):
  fim_cadeia: true
  tipo_fim_cadeia: "destacamento_publico"
  especificacao_fim_cadeia: "INCRA"
  classificacao_fim_cadeia: "origem_lidima"  ✅

OrigemFimCadeia (indice=1):
  fim_cadeia: true
  tipo_fim_cadeia: "sem_origem"
  classificacao_fim_cadeia: "sem_origem"  ✅
```

**O que funciona:**

- Classificação de fim de cadeia por origem ✅

**O que não funciona:**

- Se cada fim de cadeia tiver cartório diferente ❌

---

## Fluxo de Criação no Backend

**Arquivo:** `old/dominial/services/lancamento_campos_service.py`

```python
@staticmethod
def _processar_campos_inicio_matricula(request, lancamento):
    # 1. Coletar origens do POST
    origens_completas = request.POST.getlist('origem_completa[]')
    cartorios_origem = request.POST.getlist('cartorio_origem[]')
    livros_origem = request.POST.getlist('livro_origem[]')
    folhas_origem = request.POST.getlist('folha_origem[]')

    # 2. Concatenar origens (APENAS A STRING!)
    lancamento.origem = '; '.join(origens_completas)

    # 3. Salvar APENAS o primeiro cartório, livro e folha
    if cartorios_origem:
        lancamento.cartorio_origem_id = cartorios_origem[0]
    if livros_origem:
        lancamento.livro_origem = livros_origem[0]
    if folhas_origem:
        lancamento.folha_origem = folhas_origem[0]

    lancamento.save()

    # 4. Criar OrigemFimCadeia para cada origem
    for i, origem in enumerate(origens_completas):
        fim_cadeia = request.POST.get(f'fim_cadeia_{i}') == 'on'
        tipo_fim = request.POST.get(f'tipo_fim_cadeia_{i}')
        classificacao = request.POST.get(f'classificacao_fim_cadeia_{i}')

        OrigemFimCadeia.objects.create(
            lancamento=lancamento,
            indice_origem=i,
            fim_cadeia=fim_cadeia,
            tipo_fim_cadeia=tipo_fim,
            classificacao_fim_cadeia=classificacao,
            # ⚠️ NÃO salva cartório, livro, folha por origem!
        )
```

---

## Recomendações para Migração

### Princípios

1. **Cada origem deve ter seus próprios dados completos**
2. **Cartório, livro, folha, data devem ser por origem**
3. **Compatibilidade com dados existentes**

### Estratégia de Migração

```python
def migrar_multiplas_origens():
    """
    Migra dados de múltiplas origens do formato atual para o novo schema.
    """
    for lancamento in Lancamento.objects.all():
        # Extrair origens da string concatenada
        origens = lancamento.origem.split('; ') if lancamento.origem else []

        if len(origens) <= 1:
            # Caso simples: apenas uma origem, migrate normal
            LancamentoOrigem.objects.create(
                lancamento=lancamento,
                indice_origem=0,
                documento_numero=origens[0] if origens else None,
                cartorio_id=lancamento.cartorio_origem_id,
                livro=lancamento.livro_origem,
                folha=lancamento.folha_origem,
                data=lancamento.data_origem,
            )
        else:
            # Múltiplas origens: dados limitados, usar o que existe
            for i, origem in enumerate(origens):
                if i == 0:
                    # Primeira origem: usar dados do lançamento
                    LancamentoOrigem.objects.create(
                        lancamento=lancamento,
                        indice_origem=i,
                        documento_numero=origem,
                        cartorio_id=lancamento.cartorio_origem_id,
                        livro=lancamento.livro_origem,
                        folha=lancamento.folha_origem,
                        data=lancamento.data_origem,
                    )
                else:
                    # Outras origens: dados incompletos
                    LancamentoOrigem.objects.create(
                        lancamento=lancamento,
                        indice_origem=i,
                        documento_numero=origem,
                        # cartorio_id=NULL (dado perdido!)
                        # livro=NULL (dado perdido!)
                        # folha=NULL (dado perdido!)
                        # data=NULL (dado perdido!)
                    )
```

---

## Proposta de Schema Novo

### Tabela `lancamento_origem` (Nova)

```sql
CREATE TABLE lancamento_origem (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lancamento_id INTEGER NOT NULL REFERENCES lancamento(id),
    indice_origem INTEGER NOT NULL,

    -- Dados da origem
    documento_tipo TEXT CHECK(documento_tipo IN ('matricula', 'transcricao', 'outra')),
    documento_numero VARCHAR(50),

    -- Dados do registro (cartório, livro, folha)
    cartorio_id INTEGER REFERENCES cartorios(id),
    livro VARCHAR(20),
    folha VARCHAR(20),
    data DATE,

    -- Dados de fim de cadeia (renomeados de OrigemFimCadeia)
    fim_cadeia BOOLEAN DEFAULT FALSE,
    tipo_fim_cadeia TEXT CHECK(tipo_fim_cadeia IN ('destacamento_publico', 'outra', 'sem_origem')),
    especificacao_fim_cadeia TEXT,
    classificacao_fim_cadeia TEXT CHECK(classificacao_fim_cadeia IN ('origem_lidima', 'sem_origem', 'inconclusa')),

    -- Constraints
    UNIQUE(lancamento_id, indice_origem)
);

-- Index para performance
CREATE INDEX idx_lancamento_origem_lancamento ON lancamento_origem(lancamento_id);
CREATE INDEX idx_lancamento_origem_documento ON lancamento_origem(documento_numero);
```

### Tabela `lancamento` (Simplificada)

```sql
-- Remover campos duplicados/redundantes
ALTER TABLE lancamento DROP COLUMN cartorio_origem;
ALTER TABLE lancamento DROP COLUMN livro_origem;
ALTER TABLE lancamento DROP COLUMN folha_origem;
ALTER TABLE lancamento DROP COLUMN data_origem;
ALTER TABLE lancamento DROP COLUMN origem;

-- Manter compatibilidade temporária (view ou campo calculado)
-- Esses campos podem ser populados via trigger ou application logic
-- para manter compatibilidade com código existente
```

### Modelo TypeScript (Novo)

```typescript
interface LancamentoOrigem {
  id: string;
  lancamentoId: string;
  indiceOrigem: number;

  // Documento de origem
  documentoTipo: "matricula" | "transcricao" | "outra";
  documentoNumero: string | null;

  // Registro da origem
  cartorioId: string | null;
  cartorio?: Cartorio; // FK reversa
  livro: string | null;
  folha: string | null;
  data: Date | null;

  // Fim de cadeia
  fimCadeia: boolean;
  tipoFimCadeia: "destacamento_publico" | "outra" | "sem_origem" | null;
  especificacaoFimCadeia: string | null;
  classificacaoFimCadeia: "origem_lidima" | "sem_origem" | "inconclusa" | null;
}

interface Lancamento {
  id: string;
  documentoId: string;
  tipo: LancamentoTipo;
  data: Date;

  // Relacionamentos
  documento: Documento;
  origens: LancamentoOrigem[]; // hasMany
  pessoas: LancamentoPessoa[]; // hasMany
}
```

---

## Exemplo de Dados no Schema Novo

### Entrada do Usuário

```
Origem 1: M50 - Cartório: 1º CRI Salvador - Livro: 3 - Folha: 45
Origem 2: T20 - Cartório: 2º CRI Salvador - Livro: 5 - Folha: 12
Origem 3: M30 - Cartório: 3º CRI Itabuna - Livro: 2 - Folha: 30
```

### Salvamento no Schema Novo

```json
{
  "lancamento": {
    "id": "1",
    "documento_id": "100",
    "tipo": "inicio_matricula",
    "data": "2026-01-27"
  },
  "origens": [
    {
      "indice_origem": 0,
      "documento_tipo": "matricula",
      "documento_numero": "M50",
      "cartorio_id": 1,
      "livro": "3",
      "folha": "45",
      "data": null,
      "fim_cadeia": false
    },
    {
      "indice_origem": 1,
      "documento_tipo": "transcricao",
      "documento_numero": "T20",
      "cartorio_id": 2,
      "livro": "5",
      "folha": "12",
      "data": null,
      "fim_cadeia": false
    },
    {
      "indice_origem": 2,
      "documento_tipo": "matricula",
      "documento_numero": "M30",
      "cartorio_id": 3,
      "livro": "2",
      "folha": "30",
      "data": null,
      "fim_cadeia": true,
      "tipo_fim_cadeia": "destacamento_publico",
      "classificacao_fim_cadeia": "origem_lidima"
    }
  ]
}
```

---

## Impactos na Migração

### Dados Perdidos (Historicamente)

| Cenário                             | Dados Perdidos                              | Impacto                                    |
| ----------------------------------- | ------------------------------------------- | ------------------------------------------ |
| Lançamentos com múltiplos cartórios | Cartório, livro, folha, data das origens 2+ | Alto - dado real não capturado             |
| Cadeias com origens diferentes      | Integridade da cadeia                       | Alto - impossibilita rastreamento completo |

### Correlações Necesárias

1. **Atualizar frontend** para enviar array de origens com dados completos
2. **Atualizar backend** para processar e salvar cada origem individualmente
3. **Criar migration** para migrar dados existentes (com pérdida)
4. **Criar view** para compatibilidade com código que usa `lancamento.origem`

---

## Arquivos Relacionados

| Arquivo                                              | Propósito                                      |
| ---------------------------------------------------- | ---------------------------------------------- |
| `old/dominial/models/lancamento_models.py`           | Modelos Lancamento e OrigemFimCadeia           |
| `old/dominial/services/lancamento_campos_service.py` | Processamento de campos de início de matrícula |
| `docs/db/ORIGEMFIMCADEIA_ANALISE.md`                 | Análise da tabela OrigemFimCadeia              |
| `docs/db/CARTORIOS_DOCUMENTACAO.md`                  | Documentação sobre campos de cartório          |
| `docs/cadeia-dominial/TIPOS_LANCAMENTO.md`           | Tipos de lançamento e campos                   |

---

## Conclusão

O sistema atual **não suporta** múltiplos cartórios, livros e folhas por lançamento. Isso é uma **limitação significativa** que causa perda de dados em cenários reais onde:

1. Um imóvel deriva de **múltiplos documentos de cartórios diferentes**
2. Cada documento tem seu próprio **livro e folha**
3. A cadeia dominial precisa rastrear **todas as origens com precisão**

A migração deve incluir:

- Nova tabela `lancamento_origem` com dados completos por origem
- Migration para preservar dados existentes (com perdas documentadas)
- Atualização do frontend para interface de múltiplas origens
- Compatibilidade retroativa via view ou aplicação

---

**Data da Análise:** 2026-01-27
**Analista:** Claude Code
**Status:** Documentado para参考 em migração
