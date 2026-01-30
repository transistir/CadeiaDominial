# Respostas as Questoes Abertas do Schema

Este documento contem as decisoes tomadas para cada questao levantada em `SCHEMA_QUESTOES.md`.

---

## Q1) `documento.sigla_patrimonio_publico`: manter, derivar ou remover?

**Contexto:** o campo existe, mas nao ha definicao clara de significado, regra de preenchimento ou obrigatoriedade.

**Opcoes:**

1. **Manter como campo livre**
   - Pratico, mas aumenta risco de dados inconsistentes.
2. **Derivar automaticamente** (ex: com base em outras colunas)
   - Consistencia maior, mas precisa regra clara.
3. **Remover** (se nao for usado)
   - Simplifica, reduz risco.

**Decisao:** **Remover de `documento` (manter em `fim_cadeia`)**
**Justificativa:** o campo so faz sentido em `fim_cadeia` (origem de fim de cadeia por patrimonio publique). Nao pertence a tabela `documento`.
**Acoes:**

- Remover campo `sigla_patrimonio_publico` de `documento`
- Manter em `fim_cadeia` onde tem significado real

---

## Q2) `lancamento.cri_origem_id` vs `origem.cri_id`: duplicidade ou fonte unica?

**Contexto:** o CRI da origem pode ficar em `origem.cri_id`. Manter tambem em `lancamento` cria duplicidade.

**Opcoes:**

1. **Remover `lancamento.cri_origem_id`**
   - Fonte unica em `origem`.
   - Simples e consistente.
2. **Manter os dois com regra de sincronismo**
   - Exige trigger/app para garantir igualdade (fragil).
3. **Manter apenas em `lancamento`**
   - Perde granularidade quando houver varias origens.

**Decisao:** **Remover `lancamento.cri_origem_id`**
**Justificativa:** modelo antigo assumia uma origem por lancamento. O novo modelo usa tabela `origem` onde cada lancamento pode ter multiplas origens, cada uma com seu proprio `cartorio_id`. Campo era redundante e incompativel com o novo design.
**Acoes:**

- Remover campo `cri_origem_id` da tabela `lancamento`
- Usar `origem.cartorio_id` para identificar o cartorio de cada origem

---

## Q3) Multiplas origens por lancamento: explicitar regra e exemplos?

**Contexto:** o modelo permite N origens por lancamento, mas isso precisa ficar cristalino.

**Opcoes:**

1. **Documentar com exemplo simples** (ex: 2 origens, indices 0 e 1)
2. **Criar regra rigida** (ex: `origem.indice=0` e unico para inicio_matricula)

**Decisao:** **Documentar explicitamente e manter flexibilidade**
**Justificativa:** transmissao englobada (art. 225 e 234 da Lei 6.015/73) pode ter varias origens com cartorios diferentes. Cada origem pode ser:

- Um documento (matricula/transcricao): `origem.documento_id` aponta para `documento`
- Um fim de cadeia: `origem.fim_cadeia_id` aponta para `fim_cadeia`

**Acoes:**

- Documentar conceito de transmissao englobada com exemplo real
- Usar FK polimorfica em `origem`: `documento_id` OU `fim_cadeia_id`
- Cada origem tera campos proprios: `cartorio_id`, `livro`, `folha`, `data`

**Exemplo de Transmissao Englobada:**

```
Imovel X tem matricula M100 (documento atual)
  - Inicio de M100 tem 3 origens (transmissao englobada):
    - Origem 1: documento M50 (matricula, cadeia continua)
    - Origem 2: fim_cadeia (destacamento do patrimonio public - INCRA)
    - Origem 3: documento T30 (transcricao, cadeia continua)

Resultado no banco:
  lancamento (id=1) → documento_id=100 (M100) → tipo=inicio_matricula
  │
  ├── origem (id=1): documento_id=50 (M50), cartorio_id=1, livro=3, folha=45
  │
  ├── origem (id=2): fim_cadeia_id=1, tipo_fim=destacamento_publico,
  │     especificacao=INCRA, classificacao=origem_lidima
  │
  └── origem (id=3): documento_id=30 (T30), cartorio_id=3, livro=2, folha=30
```

---

## Q4) Significado de `origem.numero`

**Contexto:** ambiguidade se o campo e o numero da matricula/transcricao de origem ou outra coisa.

**Opcoes:**

1. **Numero do documento de origem** (matricula/transcricao)
2. **Outro conceito** (precisa campo proprio)

**Decisao:** **Numero do documento de origem (matricula/transcricao)**
**Justificativa:** quando a origem e um documento, `origem.numero` e o numero
do documento (ex: "M50", "T30"). Quando a origem e um fim de cadeia,
nao ha numero de documento (o numero fica em `fim_cadeia.especificacao`).
**Acoes:** nenhuma mudanca necessaria no schema

---

## Q5) Vinculo entre documentos criados e suas origens

**Contexto:** `documento.lancamento_origem_id` liga o documento ao lancamento, mas nao identifica **qual origem** gerou o documento quando ha varias origens.

**Opcoes:**

1. **Adicionar `documento.origem_id`** (FK para `origem`)
2. **Regra deterministica** (ex: doc criado a partir de `origem.indice=0`)
3. **Nao vincular** (aceitar ambiguidade)

**Decisao:** **Nao necessario - relacao ja existe via `origem.documento_id`**
**Justificativa:** `documento` nao precisa de `origem_id`. A relacao e de `origem`
para `documento` (cada origem aponta para o documento de origem via FK `documento_id`).
**Acoes:** nenhuma - manter relacao natural origem → documento

---

## Q6) Cascades podem apagar documentos de outro imovel?

**Contexto:** com `lancamento` criando documentos, um delete pode apagar documentos de outro imovel caso o lancamento esteja ligado a outro contexto.

**Opcoes:**

1. **Permitir** (assumir que um lancamento so cria docs do mesmo imovel)
2. **Bloquear via regra** (ex: validar `documento.imovel_id == lancamento.documento.imovel_id`)
3. **Remover cascade** e deletar via app

**Decisao:** **Permitir cascade - apagar lancamento apaga toda a cadeia**
**Justificativa:** se usuario decide apagar um lancamento, o sistema deve
apagar: lancamento → origens → documentos de origem → lancamentos desses
documentos → e assim por diante (cascade completo).
**Acoes:**

- Manter ON DELETE CASCADE em todas as FKs da cadeia
- Origens apontam para documentos via FK
- Documentos apontam para lancamentos via FK

---

## Q7) `documento.is_principal`: como garantir "exatamente um"?

**Contexto:** o banco garante "no maximo um" via unique parcial, mas nao garante "pelo menos um".

**Opcoes:**

1. **Trigger/aplicacao** para garantir que sempre exista um principal
2. **Permitir zero** (aceitar estados incompletos)

**Decisao:** **Renomear para `is_documento_atual` e garantir exatamente um**
**Justificativa:** o campo identifica qual documento e o atual/vigente do imovel,
nao "o principal". Cada imovel pode ter varios documentos (matriculas,
transcricoes) e precisamos saber qual esta em vigor.
**Acoes:**

- Renomear `is_principal` para `is_documento_atual` (ou `is_vigente`)
- Garantir que cada imovel tenha exatamente um documento atual via app/trigger

---

## Q8) Normalizacao de `documento.numero` (apenas digitos) pode gerar colisao?

**Contexto:** numeros com letras podem colidir apos normalizacao.

**Opcoes:**

1. **Normalizar e resolver colisao manualmente**
2. **Manter campo bruto paralelo** (`numero_raw`)
3. **Nao normalizar**

**Decisao:** **Manter campo bruto paralelo (`numero_raw`)**
**Justificativa:** preserva rastreio e evita colisoes.
**Acoes:**

- Manter campo `numero_raw` com valor original
- Manter campo `numero` normalizado (apenas digitos)

---

## Q9) `numero_lancamento` obrigatorio: como migrar dados legados?

**Contexto:** a constraint exige valor > 0 e unico por documento.

**Opcoes:**

1. **Preencher com ordem por data/id**
2. **Permitir NULL temporariamente** e depois backfill
3. **Gerar automaticamente se vazio**

**Decisao:** **Permitir NULL temporariamente e depois backfill**
**Justificativa:** migra com menos risco. Preencher depois com ordem por data.
**Acoes:**

- Permitir NULL temporariamente durante migracao
- Backfill com sequencia ordenada por data apos validacao

---

## Q10) `lancamento_tipo.requer_*_origem`: significado e uso

**Contexto:** flags sao para UI/validacao, nao para DB. Ainda assim, precisam de definicao.

**Opcoes:**

1. **Definir que se aplicam a cada origem**
2. **Definir que se aplicam ao lancamento (como um todo)**
3. **Remover flags**

**Decisao:** **Definir que se aplicam ao lancamento (como um todo)**
**Justificativa:** as flags `requer_descricao`, `requer_titulo`, etc. indicam
quais campos do lancamento sao obrigatorios para preenchimento pelo usuario,
nao das origens. Cada origem pode ter seus proprios requisitos definidos
em `origem.tipo` ou em `fim_cadeia`.
**Acoes:** nenhuma - manter como esta

---

## Q11) `cartorio_transmissao`: entrada livre vs tabela controlada

**Contexto:** campo e "manual", mas FK exige registro.

**Opcoes:**

1. **Criar registro automaticamente se nao existir**
2. **Obrigar cadastro previo**

**Decisao:** **Criar registro automaticamente se nao existir**
**Justificativa:** melhor UX. Usuario digita livremente.
**Acoes:**

- Implementar logica de upsert: buscar por nome, criar se nao existir

---

## Q12) Fonte de verdade: doc completo ou resumo?

**Contexto:** `SCHEMA_CONSOLIDATED.md` hoje e resumo; ERD contem inventario completo.

**Opcoes:**

1. **Manter doc como resumo** e ERD como inventario completo
2. **Expandir doc** com todas as colunas do ERD

**Decisao:** **Manter doc como resumo e ERD como inventario completo**
**Justificativa:** ERD ja tem inventario completo. Duplicar informacao aumenta risco de descompasso.
**Acoes:** nenhuma; manter separacao atual

---

## Q13) Inconsistência de nomenclatura: `imovel.cartorio_id` vs `documento.cri_id`

**Contexto:** ambos apontam para a tabela `cri`, mas usam nomes diferentes (`cartorio_id` em imovel, `cri_id` em documento e origem).

**Opções:**

1. **Renomear `imovel.cartorio_id` para `imovel.cri_id`** - consistência total
2. **Manter como está** e documentar a exceção
3. **Renomear ambos para `cartorio_id`** - volta à convenção antiga

**Decisão:** **Renomear `imovel.cartorio_id` para `imovel.cri_id`**
**Justificativa:** consistência e clareza com demais FKs para `cri`.
**Ações:**

- Renomear coluna `cartorio_id` → `cri_id` na tabela `imovel`

---

## Q14) `lancamento_pessoa.tipo`: valores válidos não definidos

**Contexto:** o campo `tipo` existe na tabela `lancamento_pessoa`, mas não há CHECK ou documentação dos valores válidos.

**Opções:**

1. **Definir CHECK** com valores explícitos (`transmitente`, `adquirente`)
2. **Manter como texto livre**
3. **Criar tabela de lookup** `lancamento_pessoa_tipo`

**Decisão:** **CHECK com valores explícitos**
**Justificativa:** simplicidade e integridade dos dados.
**Ações:**

- Adicionar CHECK constraint: `tipo IN ('transmitente', 'adquirente')`

---

## Q15) `lancamento_pessoa`: precedência entre `pessoa_id` e `nome_digitado`

**Contexto:** ambos campos existem, mas não há regra clara de quando usar cada um.

**Opções:**

1. **`pessoa_id` obrigatório**, `nome_digitado` como cache
2. **`pessoa_id` opcional**, `nome_digitado` como fallback
3. **Regra XOR**: exatamente um preenchido

**Decisão:** **`pessoa_id` opcional, `nome_digitado` como fallback**
**Justificativa:** flexibilidade com rastreabilidade. Permite registrar pessoas não cadastradas.
**Ações:** nenhuma - manter estrutura atual

---

## Q16) `origem.indice`: constraint CHECK >= 0 ausente

**Contexto:** a documentação diz que `indice` deve ser >= 0, mas não há CHECK explícito.

**Opções:**

1. **Adicionar CHECK (`indice >= 0`)** no banco + app garante contiguidade
2. **Não adicionar CHECK**, deixar tudo para a aplicação

**Decisão:** **Adicionar CHECK (`indice >= 0`)**
**Justificativa:** banco garante mínimo, app garante contiguidade.
**Ações:**

- Adicionar CHECK constraint: `indice >= 0`

---

## Q17) ERD não visualiza constraints importantes

**Contexto:** o ERD mostra estrutura e FKs, mas não exibe UNIQUE, CHECK, NOT NULL, ON DELETE.

**Opções:**

1. **Criar seção de constraints no ERD** (notes no Mermaid)
2. **Criar documento separado** `SCHEMA_CONSTRAINTS.md`
3. **Manter apenas no doc**

**Decisão:** **Criar documento separado `SCHEMA_CONSTRAINTS.md`**
**Justificativa:** clareza sem poluir o ERD.
**Ações:**

- Criar `docs/db/SCHEMA_CONSTRAINTS.md` com todas as constraints

---

## Q18) `origem.tipo`: CHECK constraint ausente no doc

**Contexto:** valores são `matricula`, `transcricao`, `fim_cadeia` (origem pode ser documento ou fim de cadeia).

**Opções:**

1. **CHECK com 3 valores**: `matricula`, `transcricao`, `fim_cadeia`
2. **Manter texto livre**

**Decisão:** **CHECK com 3 valores explícitos**
**Justificativa:** consistência e validação no banco.
**Ações:**

- Adicionar CHECK constraint: `tipo IN ('matricula', 'transcricao', 'fim_cadeia')`

---

## Q19) `origem.cri_id`: quando obrigatório?

**Contexto:** o ERD mostra `cri_id` como opcional. Para `inicio_matricula`, faz sentido exigir CRI.

**Opções:**

1. **Obrigatório apenas para `inicio_matricula`** (regra condicional)
2. **Sempre opcional**
3. **Sempre obrigatório**

**Decisão:** **Obrigatório apenas para `inicio_matricula`**
**Justificativa:** coerente com semântica de início de matrícula.
**Ações:**

- Documentar regra: `origem.cri_id` obrigatório quando `lancamento.tipo = 'inicio_matricula'`
- Validar na aplicação

---

## Q20) Convenção de nomes: `pessoas` (plural) vs outras tabelas (singular)

**Contexto:** a tabela `pessoas` está no plural, enquanto outras estão no singular.

**Opções:**

1. **Renomear para `pessoa`** (singular)
2. **Manter `pessoas`**

**Decisão:** **Renomear para `pessoa`**
**Justificativa:** consistência de convenção de nomenclatura.
**Ações:**

- Renomear tabela `pessoas` → `pessoa`

---

## Q21) ERD usa `bool` mas SQLite usa `INTEGER`

**Contexto:** o ERD mostra `bool`, mas SQLite usa INTEGER (0/1).

**Opções:**

1. **Mudar ERD para `int`** com nota
2. **Manter `bool` no ERD** e documentar

**Decisão:** **Manter `bool` no ERD e documentar**
**Justificativa:** ERD legível, doc com detalhes técnicos.
**Ações:**

- Adicionar nota no ERD: "bool representa INTEGER (0/1) no SQLite"

---

## Q22) Ciclo de FK: `documento ↔ lancamento`

**Contexto:** `documento.lancamento_origem_id → lancamento` e `lancamento.documento_id → documento` criam ciclo.

**Opções:**

1. **Remover CASCADE de `documento.lancamento_origem_id`** (SET NULL)
2. **Manter CASCADE em ambos**
3. **Bloquear exclusão de lancamento**

**Decisão:** **Remover campo `documento.lancamento_origem_id`**
**Justificativa:** não há necessidade de navegação reversa documento → lançamento que o criou.
**Ações:**

- Remover coluna `lancamento_origem_id` da tabela `documento`
- Q24 não se aplica (campo removido)

---

## Q23) `tis.terra_referencia_id` vs `terra_indigena_referencia`

**Contexto:** campo é `terra_referencia_id`, tabela é `terra_indigena_referencia`.

**Opções:**

1. **Renomear para `terra_indigena_referencia_id`**
2. **Manter `terra_referencia_id`**

**Decisão:** **Manter `terra_referencia_id`**
**Justificativa:** praticidade, desde que documentado.
**Ações:** nenhuma - manter como está

---

## Q24) Migração: como popular `documento.lancamento_origem_id` para dados legados?

**Decisão:** **Não aplicável**
**Justificativa:** o campo foi removido na Q22, então não há dados para migrar.
**Ações:** nenhuma

---

## Q25) `lancamento_tipo`: falta campo `nome` legível?

**Contexto:** a tabela `lancamento_tipo` tem apenas `tipo` (valor técnico) e flags.

**Opções:**

1. **Adicionar campo `nome`** TEXT NOT NULL
2. **Derivar nome no frontend**

**Decisão:** **Adicionar campo `nome`**
**Justificativa:** permite personalização sem mudança de código.
**Ações:**

- Adicionar coluna `nome` TEXT NOT NULL na tabela `lancamento_tipo`

---

## Resumo das Ações de Consolidação (Q13-Q25)

| Questão | Decisão            | Ação no Schema                                       |
| ------- | ------------------ | ---------------------------------------------------- |
| Q13     | Renomear           | `imovel.cartorio_id` → `imovel.cri_id`               |
| Q14     | CHECK              | `tipo IN ('transmitente', 'adquirente')`             |
| Q15     | Manter             | Nenhuma - opcional/fallback já funciona              |
| Q16     | CHECK              | `origem.indice >= 0`                                 |
| Q17     | Documento separado | Criar `SCHEMA_CONSTRAINTS.md`                        |
| Q18     | CHECK              | `tipo IN ('matricula', 'transcricao', 'fim_cadeia')` |
| Q19     | Regra condicional  | `cri_id` obrigatório para `inicio_matricula`         |
| Q20     | Renomear           | `pessoas` → `pessoa`                                 |
| Q21     | Documentar         | Nota no ERD: bool = INTEGER(0/1)                     |
| Q22     | Remover            | Remover `documento.lancamento_origem_id`             |
| Q23     | Manter             | Nenhuma                                              |
| Q24     | Não aplicável      | Campo removido na Q22                                |
| Q25     | Adicionar          | `lancamento_tipo.nome` TEXT NOT NULL                 |
