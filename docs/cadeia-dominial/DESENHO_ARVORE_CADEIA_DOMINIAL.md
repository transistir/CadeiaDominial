# Desenho da Árvore da Cadeia Dominial (Guia para Devs)

Este documento descreve **como o sistema organiza e desenha a árvore da cadeia dominial** (visualização D3), desde o cadastro do imóvel até a criação de origens em “início de matrícula”, relacionando o fluxo com o código.

> Observação: o projeto possui versões “ativas” e versões “antigas/backup” de alguns arquivos JS. Neste repositório, a implementação Django + templates + services que governam o fluxo de produção está dentro de `old/` (ex.: `old/dominial/...`).

---

## ⚠️ AVISO: Terminologia "Pai/Filho" vs "Origem" - CONFLITO CONCEITUAL

Esta seção documenta um **problema de nomenclatura** no código atual que causa confusão e deve ser considerado na migração para React Flow.

### Onde "Pai/Filho" é usado no código atual

| Arquivo                                  | Variável/Método             | Uso                         |
| ---------------------------------------- | --------------------------- | --------------------------- |
| `hierarquia_arvore_service.py:227`       | `_buscar_documentos_pais()` | Método que busca origens    |
| `hierarquia_arvore_service.py:233`       | `doc_pai`                   | Variável local para origens |
| `D3_CHAIN_VISUALIZATION_FLOW.md:235-236` | `from:filho`, `to:pai`      | Comentário explicativo      |
| `cadeia_dominial_d3.js:484-500`          | `filhos`, `pai`, `filho`    | JS monta árvore             |

### O Problema: "Pai/Filho" conflita com "Origem"

#### 1. Conflito semântico

**No conceito de Cadeia Dominial (negócio):**

```
M100 "possui origens" M50, M30, T20
          ↑
        Origem = quem veio ANTES = naturalmente seria "PAI"
```

**No código (from/to):**

```python
conexao = {
    'from': 'M100',   # "filho" - quem TEM as origens
    'to': 'M50',      # "pai" - a origem em si
}
```

O documento que **declara** as origens é chamado de "filho", mas na lógica de cadeia dominial, **quem é a origem é o "pai"** (a fonte). Isso cria uma contradição mental.

#### 2. Problema de cardinalidade (MAIOR PROBLEMA)

A terminologia "pai/filho" pressupõe:

- 1 pai pode ter muitos filhos ✓
- 1 filho tem 1 pai ✗ (violado!)

**Mas na cadeia dominial real:**

```
M100 tem origens: M50, M30, T20  → 1 documento com 3 origens
M50 tem origens: M10, T5         → 1 documento com 2 origens
M30 tem origens: M15             → 1 documento com 1 origem
T20 tem origens: M8              → 1 documento com 1 origem
```

**Isso é um GRAFO, não uma árvore.** A terminologia "pai/filho" é inadequada para descrever relações múltiplas.

### O que fazer na migração para React Flow

React Flow também usa `parent/child`:

```javascript
// React Flow
edges: [
  { source: "M100", target: "M50" }, // source = M100 (filho!), target = M50 (pai!)
];
```

**Sugestões:**

1. **Documentar explicitamente** no código:

   ```python
   # AVISO: A nomenclatura "filho" se refere ao documento que DECLARA origens,
   # não a um conceito de hierarquia pai/filho tradicional.
   # O correto seria: "documento_derivado" e "origem"
   ```

2. **Renomear no código** (se for refatorar):
   - `documentos_pais` → `origens`
   - `doc_pai` → `origem`
   - `filho` → `documento_derivado` ou `documento_atual`
   - `pai` → `origem`

3. **No frontend React Flow**, usar nomes neutros:
   ```javascript
   edges: [{ source: "M100", target: "M50", label: "origem" }];
   ```

### Terminologia proposta para novo código

| Conceito                      | Termo sugerido            | Descrição                     |
| ----------------------------- | ------------------------- | ----------------------------- |
| Documento que declara origens | **Derivado** ou **Atual** | M100 deriva de M50            |
| Documento origem              | **Origem**                | M50 é origem de M100          |
| Relação                       | **Deriva de**             | "M100 deriva de M50"          |
| Múltiplas origens             | **Origens** (plural)      | M100 deriva de M50, M30 e T20 |

### Exemplo de JSON proposto (vs atual)

**Atual (confuso):**

```json
{
  "conexoes": [
    { "from": "M100", "to": "M50" },
    { "from": "M100", "to": "M30" }
  ]
}
```

**Proposto (claro):**

```json
{
  "derivacoes": [
    { "derivado": "M100", "origem": "M50" },
    { "derivado": "M100", "origem": "M30" }
  ]
}
```

---

## Conceitos e termos

- **TI (Terra Indígena)**: contexto de navegação; o usuário escolhe uma TI e então opera dentro dela.
- **Imóvel**: entidade principal. Ao cadastrar um imóvel, o sistema cria um **documento especial** que representa a “matrícula atual do imóvel” e vira o **card raiz** da árvore.
- **Documento**: nó (card) na árvore. Tipos principais:
  - `matricula` (normalmente número `M<numero>`)
  - `transcricao` (normalmente número `T<numero>`)
- **Lançamento**: evento registrado dentro de um documento. Alguns lançamentos contêm **origens** (campo texto) que “puxam” documentos pais para a árvore.
- **Origem (em início de matrícula)**: quando o lançamento é do tipo `inicio_matricula`, o usuário informa uma ou mais origens; cada origem referencia (ou cria) documentos anteriores na cadeia.

---

## Fluxo funcional (do usuário) → o que acontece no código

### Diagrama geral do fluxo

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. USUÁRIO ESCOLHE TI                                               │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  Usuário entra na TI e clica em "cadastrar novo imóvel"     │ │
│     └─────────────────────────────────────────────────────────────┘ │
│                              ↓                                       │
│  2. CADASTRA IMÓVEL (formulário)                                     │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  Preenche dados do imóvel e salva                           │ │
│     │                                                              │ │
│     │  → Sistema CRIA automaticamente:                            │ │
│     │    Documento de matrícula atual (ex: M100)                  │ │
│     │    Este documento será a RAIZ da cadeia dominial            │ │
│     └─────────────────────────────────────────────────────────────┘ │
│                              ↓                                       │
│  3. ABRE CADEIA DOMINIAL (árvore D3)                                 │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  fetch('/cadeia-dominial/<tis_id>/<imovel_id>/arvore/')     │ │
│     │                                                              │ │
│     │  Backend retorna:                                           │ │
│     │    { documentos: [...], conexoes: [...] }                   │ │
│     │                                                              │ │
│     │  Frontend desenha:                                          │ │
│     │    M100 (raiz)                                              │ │
│     └─────────────────────────────────────────────────────────────┘ │
│                              ↓                                       │
│  4. ADICIONA LANÇAMENTOS                                             │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │  Usuário abre M100 e adiciona lançamentos:                  │ │
│     │                                                              │ │
│     │  Tipo: "início de matrícula"                                │ │
│     │  Origens: "M50; T20; M30"                                   │ │
│     │                                                              │ │
│     │  → Sistema CRIA documentos para origens (se não existirem)  │ │
│     │  → Sistema CRIA conexões na árvore                          │ │
│     │                                                              │ │
│     │  Resultado:                                                 │ │
│     │    M100 ──→ M50                                             │ │
│     │    M100 ──→ T20                                             │ │
│     │    M100 ──→ M30                                             │ │
│     │                                                              │ │
│     │  Se M50 também tiver "início de matrícula" com origens...   │ │
│     │  → O processo se REPETE recursivamente                      │ │
│     └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 1) Usuário escolhe TI → cadastra novo imóvel

1. Usuário entra na TI e clica em **“cadastrar novo imóvel”**.
2. Preenche formulário do imóvel e salva.
3. **Efeito colateral importante**: o sistema cria automaticamente o “documento atual” (documento de matrícula do imóvel) — esse documento será a raiz da cadeia.

**Onde isso é implementado**

- **Form/submit do imóvel**: `old/dominial/views/imovel_views.py`
  - Ao salvar um imóvel novo, chama `LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)`.
- **Criação do documento raiz (matrícula atual)**: `old/dominial/services/lancamento_documento_service.py`
  - Garante prefixo `M` e cria um `Documento` com:
    - `numero = M<matricula_do_imovel>`
    - `origem = 'Matrícula atual do imóvel'`
    - `livro/folha` default (`'0'`) para serem herdados/atualizados conforme primeiros lançamentos.

Por que isso é “especial”?

- É o documento que **representa o imóvel atual no contexto** e serve como **ponto de partida** para a construção da árvore.

---

### 2) Usuário abre a cadeia dominial (árvore D3)

1. Usuário acessa a tela da cadeia dominial (visualização D3).
2. O frontend faz `fetch` do JSON da árvore.
3. O backend monta a estrutura `{ documentos: [...], conexoes: [...] }`.
4. O JS converte isso numa hierarquia (root + children) e desenha a árvore.

**Rotas e view**

- Rotas: `old/dominial/urls.py`
  - Endpoint do JSON:
    - `path('cadeia-dominial/<int:tis_id>/<int:imovel_id>/arvore/', cadeia_dominial_arvore, name='cadeia_dominial_arvore')`
- View do JSON: `old/dominial/views/cadeia_dominial_views.py`
  - `cadeia_dominial_arvore(...)` retorna `JsonResponse(...)`
  - Chama o service: `HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel, criar_documentos_automaticos=True)`

**Service que monta `documentos` e `conexoes`**

- `old/dominial/services/hierarquia_arvore_service.py`
  - Responsável por:
    - identificar documento principal (raiz)
    - percorrer documentos e “subir” para origens (pais)
    - produzir lista plana de `documentos` e lista de `conexoes` (`from` → `to`)
    - recalcular `nivel` (profundidade lógica) via BFS

---

### 3) Usuário adiciona lançamentos → a árvore cresce

Quando o usuário cria lançamentos dentro de um documento, **a árvore cresce se o lançamento contém “origem”** (ou seja, referências para documentos pais).

Regra prática:

- **Sem origem**: documento não “puxa” pais novos para a árvore.
- **Com origem**: cada código `M123`/`T456` citado em `lancamento.origem` vira um documento pai (já existente ou criado automaticamente, dependendo do caso) e aparece conectado ao documento atual.

**Como as origens são interpretadas no backend**

Existem dois pontos principais:

1. **Parsing/validação de origens** (quando o sistema cria documentos automaticamente a partir de origens):

- `old/dominial/utils/hierarquia_utils.py`
  - `processar_origens_para_documentos(origem_texto, imovel, lancamento)`
  - Implementa validações (incluindo regra especial para `inicio_matricula`).

2. **Criação automática de documentos para origens** (quando aplicável):

- `old/dominial/services/lancamento_origem_service.py`
  - `LancamentoOrigemService.processar_origens_automaticas(...)`
  - Trata:
    - múltiplas origens separadas por `;`
    - cartório específico por origem (via cache/mapeamento)
    - “fim de cadeia” como caso especial (não cria “documentos normais”)

E por fim, na construção da árvore:

- `old/dominial/services/hierarquia_arvore_service.py`
  - `_buscar_documentos_pais(documento, imovel, criar_documentos_automaticos)`
  - Extrai origens com regex e resolve para `Documento` (ou cria automático se habilitado).

---

## Modelo de dados da árvore (JSON)

O endpoint da árvore retorna um JSON com, principalmente:

- **`imovel`**: metadados do imóvel (id, matrícula, nome, proprietário)
- **`documentos`**: lista plana de nós (cada um vira um card)
- **`conexoes`**: lista de arestas `from` → `to`
  - **⚠️ ATENÇÃO - Semântica confusa:**
    - `from` = documento que **declara** as origens (chamado de "filho" no código, mas seria melhor chamar de "derivado")
    - `to` = a **origem** em si (chamada de "pai" no código)

> **Nota importante:** Veja a seção ["⚠️ AVISO: Terminologia Pai/Filho"](<#️⃣-avisoterminologia-paifilho-vs-origem---conflito-conceitual) para entender por que essa nomenclatura é confusa e как (como) ela conflita com o conceito de "origem" da cadeia dominial.

Essa convenção está explícita no backend:

- Em `old/dominial/services/hierarquia_arvore_service.py`, ao criar conexão:
  - `from = documento_atual.numero` (derivado)
  - `to = doc_pai.numero` (origem)

---

## Como o frontend transforma JSON em árvore D3

### Arquivo principal do D3

- Código antigo (visto com frequência em manutenção): `old/static/dominial/js/cadeia_dominial_d3.js`
- Arquivo de build/static do Django costuma existir em `staticfiles/dominial/js/` (gerado/copied).

### Passos do JS

1. **Fetch** do JSON:
   - `fetch(`/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/?t=${timestamp}`)`
   - O parâmetro `t` é um “cache buster”.

2. **`converterParaArvoreD3(data)`**

- Mapeia documentos por `numero`
- Escolhe a raiz:
  - tende a usar `nivel === 0` ou `origem` vazia/nula
- Constrói a árvore principal a partir de `data.conexoes`
  - Importante: existe lógica de “não duplicar cards” (`visitados`)
  - Conexões que “sobram” viram `conexoesExtras` (linhas tracejadas) para preservar múltiplas relações sem duplicar nós.

3. **`renderArvoreD3(arvore, ...)`**

- Converte para `d3.hierarchy(...)`
- `d3.tree()` com layout horizontal (nível controla o eixo X/Y)
- Desenha:
  - links principais (`path.link`, verde)
  - links extras (`path.link-extra`, tracejado cinza)
  - cards (`rect`) com cor por tipo:
    - matrícula: azul
    - transcrição: roxo
    - fim de cadeia: verde/vermelho conforme classificação

---

## Regra de ordenação de múltiplas origens (início de matrícula)

### Regra esperada (negócio)

Quando um documento possui um lançamento do tipo **"início de matrícula"** e o usuário informa **múltiplas origens**, a árvore deve desenhar os documentos na seguinte ordem:

1. **Matrículas** (do maior número para o menor)
2. **Transcrições** (do maior número para o menor)

E isso se repete recursivamente (para cada documento que, por sua vez, tenha "início de matrícula" com múltiplas origens).

> **Nota:** A ordenação se aplica a **todos** os documentos da árvore, não apenas ao documento raiz. Cada nível deve respeitar a mesma regra: matrículas primeiro (maior → menor), depois transcrições (maior → menor).

### Exemplo visual

**Usuário lança em M100:**

```
Origens: "M50, T30, M25, T10, M80"
```

**Ordenação correta esperada:**

```
M100
├── M80   ← matrícula (maior número primeiro)
├── M50   ← matrícula
├── M25   ← matrícula
├── T30   ← transcrição (maior número primeiro)
└── T10   ← transcrição
```

**Ordenação atual (incorreta - só por número):**

```
M100
├── M80
├── M50
├── T30   ← transcrição no meio das matrículas!
├── M25
└── T10
```

### Como está hoje (implementação atual)

No JS do D3, a ordenação aplicada aos `children` é:

- **somente por número (desc)**, ignorando tipo (matrícula vs transcrição).
- Implementação: `ordenarFilhosPorNumeroDesc(nodo)` em `old/static/dominial/js/cadeia_dominial_d3.js`
  - extrai dígitos com regex e faz `numB - numA`.

Ou seja: se você precisa garantir **“matrículas primeiro e transcrições depois”**, isso **não está codificado explicitamente** nesse ordenamento atual.

### Onde já existe uma ordenação por tipo (referência útil)

Há uma implementação de ordenação por tipo em um service usado para “cadeia completa” (PDF/tabela), que pode servir como referência:

- `old/dominial/services/cadeia_completa_service.py`
  - `_ordenar_documentos_hierarquicamente(...)`:
    - prioridade matrícula → transcrição → outros
    - depois ordena por número desc

### Sugestão de evolução (ponto de extensão)

Existem dois lugares naturais para implementar a regra:

- **No frontend (mais simples e imediato)**: trocar/estender `ordenarFilhosPorNumeroDesc` para ordenar por:
  - prioridade do tipo (`matricula` antes de `transcricao`)
  - depois número desc
- **No backend (mais consistente)**: garantir que `documentos_pais` já venha ordenado do service (e/ou enviar um atributo que indique ordem desejada), para o frontend só respeitar.

---

## “Documento especial do imóvel” (raiz) — detalhes importantes

O “card raiz” da árvore, para um imóvel recém-cadastrado, é criado automaticamente no cadastro do imóvel:

- `old/dominial/views/imovel_views.py` (apenas para `imovel_id` inexistente)
- `old/dominial/services/lancamento_documento_service.py`
