# Schema Consolidado (v2) - Cadeia Dominial

> **⚠️ SUPERSEDED (2026-06-03, round 3 do T-001).** Este documento é histórico/proposta de consolidação e **NÃO** está alinhado com as decisões finais Q1-Q15 + Q11b + D1-D4 + T1-T4 (PR #24). Continua referenciando campos removidos (`documento.imovel_id`, `documento.is_documento_atual`, `cartorio_transmissao_id`) que foram movidos ou eliminados pelas decisões da PR #24.
>
> **Fontes canônicas atuais:**
> - Decisões + apêndice SQLite/D1: [`docs/db/SCHEMA_DECISOES_PENDENTES.md`](./SCHEMA_DECISOES_PENDENTES.md)
> - Diagrama visual: [`docs/db/erd-v2.mmd`](./erd-v2.mmd) (note: Mermaid é documentação visual, não schema; UNIQUE_NOTE/CHECK constraints não são enforcem pelo .mmd)
> - Migration executável: **T-101 (Drizzle, ainda não escrita)**
>
> Próximo passo: ou (a) reescrever este arquivo para refletir as decisões da PR #24, ou (b) removê-lo. A migration T-101 will replace both this file and the legacy `DATABASE_SCHEMA.md`/`SCHEMA_IMPROVEMENT_PROPOSAL.md` com um único Drizzle schema versionado.

**Objetivo:** consolidar todas as propostas de melhoria em um único documento coerente, pronto para migração de dados do banco atual para um novo esquema limpo, com foco em SQLite.

**Fontes consolidadas:**
- `docs/DATABASE_SCHEMA.md`
- `docs/SCHEMA_IMPROVEMENT_PROPOSAL.md`
- `docs/db/legacy/*.md`

---

## 1) Princípios de desenho

1. **Eliminar legado não usado** para reduzir risco e custo de manutenção.
2. **Preservar semântica crítica** da cadeia dominial (documentos, lançamentos, origens de cadeia).
3. **Compatibilidade com SQLite** (tipos simples, sem enums nativos).
4. **Migrar dados com rastreabilidade**, evitando perda silenciosa.

---

## 2) Decisões finais (consolidadas)

### 2.1 Tabelas removidas

| Tabela | Decisão | Justificativa | Observações de migração |
| --- | --- | --- | --- |
| `dominial_documentotipo` | REMOVER | Apenas 2 valores fixos (`matricula`, `transcricao`) | Substituir por `documento.tipo` + CHECK |
| `dominial_alteracoes` | REMOVER | Legado, já migrado para `lancamento` + `documento` | Verificar se existem linhas pendentes |
| `dominial_alteracoestipo` | REMOVER | Só usada por `alteracoes` | Remover junto |
| `dominial_registrotipo` | REMOVER | Legado, tabela vazia | Remover junto |
| `dominial_averbacaotipo` | REMOVER | Legado, só usada em `alteracoes` | Remover junto |
| `dominial_tis_imovel` | REMOVER | Substituido por `tis_imovel` (N:N TI <-> imovel) | Atualizar mapeamento na migracao |
| `dominial_importacaocartorios` | REMOVER | Log administrativo | Substituir por logs de aplicação |
| `dominial_documentoimportado` | REMOVER | Funcionalidade não usada | Opcional: flag simples no `documento` |
| `dominial_fimcadeia` | REMOVER | Catálogo redundante, sem uso | Ver seção 2.3 |

> **Nota importante:** isso resolve conflitos entre os docs. A proposta original mantinha o catalogo `fim_cadeia`, mas a analise detalhada mostra que ele nao e usado; portanto **removemos**.

### 2.2 Campos removidos / alterados

**`dominial_documento`**
- Remover `origem` (mensagem automática errada, sem uso).
- Remover `nivel_manual` (campo de visualização; deve ser calculado no frontend).
- **Inline** o tipo: `tipo` TEXT com CHECK (`matricula`, `transcricao`) no lugar de `tipo_id`.
- **Normalizar `numero`**: manter apenas digitos; guardar valor original em `numero_raw`.
- Remover `observacoes`.
- **Adicionar `numero_raw`** (texto original antes da normalizacao).
- **Renomear `is_principal`** para `is_documento_atual` (0/1) para marcar o documento vigente do imovel.
- Remover `sigla_patrimonio_publico` (fica em `origem_fim_cadeia`).
- **Demais campos permanecem** (ex: `data`, `livro`, `folha`, `data_cadastro`).

**`dominial_lancamento`**
- Remover campos legados: `transmitente_id`, `adquirente_id`, `cartorio_transacao_id`.
- Remover campos de origem legados: `origem`, `documento_origem_id`, `livro_origem`, `folha_origem`, `data_origem`.
- Usar `lancamento_pessoa` para pessoas e `cartorio_transmissao_id` (manual) para transmissão.
- Renomear `livro_transacao`, `folha_transacao`, `data_transacao` para `*_transmissao`.
- Remover `cartorio_origem_id` (CRI de origem passa a ficar em `origem.cri_id`).
- Remover `eh_inicio_matricula` (derivado de `lancamento_tipo.tipo`).
- Manter `numero_lancamento` (inteiro informado pelo usuario).
- Manter `forma` (texto livre informado pelo usuario).
- **Demais campos permanecem** (ex: `data`, `valor_transacao`, `area`, `detalhes`, `observacoes`, `descricao`, `titulo`).

**`cri`**
- Renomear tabela `dominial_cartorios` → `cri`.
- Remover `tipo` (todos os registros são CRI).

**`dominial_imovel`**
- Um `imovel` representa a matricula vigente. Quando a matricula muda, cria-se um novo `imovel`.
- Nao manter campos derivados (`matricula`, `tipo_documento_principal`); usar `documento.is_documento_atual`.

### 2.3 Fim de cadeia

- **Manter `origem_fim_cadeia`**, agora vinculada a uma tabela `origem` (suporta múltiplas origens por lançamento).
- **Remover `fim_cadeia` (catálogo)** por não uso real.
- **Nao manter** campos de fim de cadeia em `documento` (o fim de cadeia qualifica a `origem`).
- `sigla_patrimonio_publico` passa a existir em `origem_fim_cadeia`.

> **Decisão:** não inline em `lancamento`, pois perderíamos suporte a múltiplas origens. Se futuramente não houver multi-origem, avaliamos simplificar.

#### Consistência de fim de cadeia (recomendação)

- **Nao criar** coluna `fim_cadeia` no novo esquema (nao existe no legado atual).
- `tipo_fim_cadeia` e **opcional**; quando preenchido, indica fim de cadeia.
- `classificacao_fim_cadeia` e **obrigatoria apenas quando** `tipo_fim_cadeia` estiver preenchido.
- Se `tipo_fim_cadeia = 'outra'`, exigir `especificacao_fim_cadeia`.
- Se `tipo_fim_cadeia = 'destacamento_publico'`, exigir `sigla_patrimonio_publico`.
- Adicionar CHECKs e corrigir dados nulos antes da migracao.

#### Origens estruturadas (nova tabela)

- Criar tabela `origem` para armazenar dados estruturados da origem do lancamento.
- `origem` substitui o uso de strings em `lancamento.origem` e fornece base para `origem_fim_cadeia`.
- `origem_fim_cadeia` passa a referenciar `origem` (1:1 por origem).
- **Um `lancamento` pode ter várias origens** (modelado por múltiplas linhas em `origem` com `indice`).
- **Fim de cadeia e um tipo de origem** (`origem.tipo = 'fim_cadeia'`), com dados adicionais em `origem_fim_cadeia`.
- Quando a origem for um documento, preencher `origem.documento_id` (opcional) e manter os dados de identificacao (`numero`, `livro`, `folha`, `data`).

### 2.4 Campos de CRI em documentos

- **`documento.cri_id`** referencia a tabela `cri` (todos cartorios do tipo CRI).
- Remover `documento.cartorio_id`, `documento.cri_atual_id` e `documento.cri_origem_id`.

### 2.5 CRI (tabela)

- Renomear `cartorios` → `cri`.
- Remover a coluna `tipo` (todos os registros são CRI).
- Se no futuro houver outros tipos, reintroduzir `tipo` com CHECK.
- `lancamento.cartorio_transmissao_id` continua apontando para uma tabela separada (`cartorio_transmissao`), preenchida manualmente.
- `cartorio_transmissao` **nao** e CRI e **nao** deve ser usado como FK para `cri`.

---

## 3) Esquema consolidado (v2)

### 3.1 Tabelas mantidas (com ajustes)

- `pessoa`
- `cri`
- `cartorio_transmissao` (cadastro manual)
- `terra_indigena_referencia`
- `tis`
- `tis_imovel` (relacao N:N entre TI e imovel)
- `imovel`
- `documento`
- `lancamento_tipo`
- `lancamento`
- `lancamento_pessoa`
- `origem`
- `origem_fim_cadeia`

### 3.2 Campos principais (resumo)

> **Nota:** este resumo cobre os campos **principais**. O inventario completo de colunas (incluindo campos mantidos sem alteracoes) esta no ERD.

**`documento` (resumo)**
- `tipo` TEXT NOT NULL CHECK (`matricula`, `transcricao`)
- `numero` TEXT NOT NULL (normalizado so com digitos; aplicar CHECK de apenas digitos)
- `numero_raw` TEXT (valor original)
- `cri_id` FK obrigatório (aponta para `cri`)
- `imovel_id` FK obrigatório
- `is_documento_atual` INTEGER NOT NULL DEFAULT 0 CHECK (is_documento_atual IN (0,1))
- UNIQUE (`cri_id`, `tipo`, `numero`)
- UNIQUE parcial para garantir **um** documento atual por imovel:
  - `UNIQUE (imovel_id) WHERE is_documento_atual = 1`
- Sem `origem`, sem `nivel_manual`, sem `sigla_patrimonio_publico`

**`imovel` (resumo)**
- `cri_id` FK obrigatório (aponta para `cri`)
- `proprietario_id` FK obrigatório (aponta para `pessoa`)
- `arquivado` INTEGER NOT NULL DEFAULT 0 (0/1)
- Um `imovel` representa a matricula vigente. Quando a matricula muda, cria-se um novo `imovel`.
- **Relacao com TI**: um `imovel` pode ter varias TIs e uma TI pode ter varios imoveis (N:N via `tis_imovel`).

**`cri` (resumo)**
- Sem coluna `tipo` (assumimos CRI como padrão)

**`cartorio_transmissao` (resumo)**
- Tabela separada para transmissão (preenchimento manual).
- Entrada livre pelo usuario: se nao existir, criar novo registro em `cartorio_transmissao`.

**`lancamento_tipo` (resumo)**
- `tipo` TEXT NOT NULL CHECK (`inicio_matricula`, `registro`, `averbacao`)
- `nome` TEXT NOT NULL (label legivel para UI)
- Flags de UI/validacao (permissivas, sem obrigatoriedade no banco):
  - `requer_detalhes`
  - `requer_transmissao`
  - `requer_cartorio_origem`
  - `requer_data_origem`
  - `requer_descricao`
  - `requer_folha_origem`
  - `requer_forma`
  - `requer_livro_origem`
  - `requer_observacao`
  - `requer_titulo`

**`lancamento` (resumo)**
- `tipo_id` FK obrigatório (`lancamento_tipo`)
- Sem `transmitente_id`/`adquirente_id`
- `cartorio_transmissao_id` (manual, tabela separada de `cri`, **opcional**)
- `livro_transmissao`, `folha_transmissao`, `data_transmissao` (renomeados)
- `numero_lancamento` INTEGER CHECK (numero_lancamento > 0) (pode ser NULL durante migracao; aplicar NOT NULL apos backfill)
- UNIQUE (`documento_id`, `numero_lancamento`)
- Usado para compor a sigla exibida do lancamento (ex: `AV5 M123`).
- `forma` TEXT (opcional, entrada livre do usuario)

**`origem` (resumo)**
- `lancamento_id` + `indice` unico
- `indice` deve ser **>= 0** e **contiguo** por `lancamento` (0,1,2...)
- `cri_id` (FK para `cri`, opcional)
- `documento_id` (FK para `documento`, opcional)
- `tipo` (`matricula`, `transcricao`, `fim_cadeia`)
- `numero` (somente digitos), `livro`, `folha`, `data`
- `observacoes` (opcional)
- Se `tipo = 'fim_cadeia'`, exige linha em `origem_fim_cadeia` e `documento_id` deve ser NULL

**`origem_fim_cadeia` (resumo)**
- `origem_id` unico
- `tipo_fim_cadeia`, `classificacao_fim_cadeia`, `especificacao_fim_cadeia`
- `sigla_patrimonio_publico` (opcional; obrigatorio quando tipo_fim_cadeia = destacamento_publico)
- `classificacao_fim_cadeia` obrigatoria quando `tipo_fim_cadeia` estiver preenchido
- `especificacao_fim_cadeia` obrigatoria quando `tipo_fim_cadeia = 'outra'`

**`tis_imovel` (resumo)**
- `id` PK
- `tis_id` FK obrigatório (`tis`)
- `imovel_id` FK obrigatório (`imovel`)
- UNIQUE (`tis_id`, `imovel_id`)

---

### 3.3 Regras condicionais (aplicacao/trigger)

- Se `lancamento_tipo.tipo = 'inicio_matricula'`, entao `origem.cri_id` deve ser **obrigatorio** para as origens do lancamento.
- Se `documento.is_documento_atual = 1`, entao `documento.cri_id` deve **coincidir** com `imovel.cri_id`.
- As flags `requer_*` em `lancamento_tipo` sao apenas configuracoes de UI/validacao do **lancamento** e **nao** devem ser tratadas como constraints do banco.
- Se `origem.tipo = 'fim_cadeia'`, entao deve existir uma linha em `origem_fim_cadeia` e `origem.documento_id` deve ser NULL.
- Se `origem.tipo IN ('matricula', 'transcricao')`, entao `origem_fim_cadeia` **nao** deve existir.
- `origem.indice` deve ser contiguo por `lancamento` (enforce via aplicacao/trigger).
- Evitar deletar o **ultimo** documento atual de um `imovel` (enforce via aplicacao/trigger).

---

## 4) Ajustes de compatibilidade SQLite

- `DATE` e `TIMESTAMP` → `TEXT` (ISO8601).
- `BOOLEAN` → `INTEGER` (0/1).
- `DECIMAL` → `REAL` (ou `INTEGER` com centavos se necessário).
- Enums → `CHECK`.

---

## 5) Migracao de dados (ordem sugerida)

1. **Backups e contagens:** snapshot completo + contagem de linhas.
2. **Migrar pessoa/CRI/terras/tis/imovel**.
3. **Documento:**
   - Criar `tipo` inline.
   - Remover `origem`/`nivel_manual`.
   - Normalizar `numero` e preencher `numero_raw`.
   - Garantir apenas `matricula`/`transcricao` (remover valor legado `transmissao`).
   - Preencher `documento.is_documento_atual = 1` para o documento vigente de cada imovel (exatamente 1).
   - Migrar `sigla_patrimonio_publico` para `origem_fim_cadeia` quando aplicavel.
   - Remover `documento.lancamento_origem_id` (campo eliminado).
4. **Lancamento:**
   - Migrar `lancamento_pessoa` se necessário.
   - Remover campos legados.
   - Remover `cartorio_origem_id` (CRI passa para `origem.cri_id`).
   - Definir `numero_lancamento` por documento antes de aplicar a constraint NOT NULL (ex: ordem por `data`, `id`).
5. **Origem e fim de cadeia:**
   - Criar `origem` (com `tipo`, `cri_id`, `documento_id` quando aplicavel) e migrar dados estruturados (ou parsing do `lancamento.origem`).
   - Atualizar `origem_fim_cadeia` para referenciar `origem` e receber `sigla_patrimonio_publico` quando houver.
   - Nao criar documentos automaticamente na migracao; isso e comportamento de runtime para `inicio_matricula`.
6. **Remover tabelas legadas** após checagens.

### Mapa de renomeacoes e remocoes

**Tabelas**
- `dominial_cartorios` → `cri`
- `dominial_pessoas` → `pessoa`
- `cartorio_transmissao` (nova tabela, manual)

**Imoveis**
- `imovel.cartorio_id` → `imovel.cri_id`

**Documentos**
- `documento.cartorio_id` → `documento.cri_id` (FK passa a apontar para `cri`)
- `documento.is_principal` → `documento.is_documento_atual`
- `documento.cri_atual_id` → removido
- `documento.cri_origem_id` → removido
- `documento.lancamento_origem_id` → removido
- `documento.sigla_patrimonio_publico` → `origem_fim_cadeia.sigla_patrimonio_publico`

**Lancamentos**
- `lancamento.cartorio_origem_id` → removido (CRI passa para `origem.cri_id`)
- `lancamento.cartorio_transmissao_id` → manter (tabela separada, preenchimento manual)
- `lancamento.cartorio_transacao_id` → removido (legado)

**Origens**
- Criar `origem` e migrar de `lancamento.origem` (se ainda existir) + `origemfimcadeia.indice_origem`
- `origem_fim_cadeia.lancamento_id + indice_origem` → `origem_fim_cadeia.origem_id`
- `origem.tipo` inclui `fim_cadeia` e `origem.documento_id` liga a origem ao documento quando aplicavel

---

## 6) Checagens obrigatórias antes de executar a migração

**Legado em `lancamento`:**
```sql
SELECT
  COUNT(*) FILTER (WHERE transmitente_id IS NOT NULL) AS legacy_transmitente,
  COUNT(*) FILTER (WHERE adquirente_id IS NOT NULL) AS legacy_adquirente,
  COUNT(*) FILTER (WHERE cartorio_transacao_id IS NOT NULL) AS legacy_cartorio_transacao
FROM dominial_lancamento;
```

**Multi-origem em fim de cadeia:**
```sql
SELECT COUNT(*) AS multi_origem
FROM dominial_origemfimcadeia
WHERE indice_origem > 0;
```

## 7) Conflitos resolvidos (registro de decisão)

| Tema | Proposta antiga | Decisão consolidada | Motivo |
| --- | --- | --- | --- |
| `fim_cadeia` (catalogo) | Manter catálogo | REMOVER | Sem uso real; duplicidade com `origem_fim_cadeia` |
| `origemfimcadeia` | Inline em `lancamento` | MANTER tabela | Suporta múltiplas origens |
| `documentoimportado` | Manter | REMOVER | Funcionalidade nunca usada |
| `alteracoes` | Manter/clarificar | REMOVER | Legado já migrado |
| `cri_atual/cri_origem` | Manter | REMOVER | Informação duplicada em outra fonte |
| `cartorios` → `cri` | Manter | RENOMEAR | Padronizar nomenclatura para CRI |
| `cri.tipo` | Manter | REMOVER | Todos os registros são CRI |
| `cartorio_transmissao_id` | Renomear | MANTER nome + tabela separada | Campo manual, não é CRI |

---

## 8) Pendências mínimas (se houver)

1. **Normalização de `documento.numero`:** extrair apenas dígitos, preservar `numero_raw` e validar unicidade por CRI.
2. **`numero_lancamento`:** backfill por documento antes de ativar NOT NULL.

---

## 9) Notas para migracao futura (forward-compat)

- `origem` é a fonte estruturada oficial; `lancamento.origem` (string) deve ser removido após migração.
- `cartorio_transmissao_id` permanece **separado** de `cri` e é **preenchido manualmente**.
- `documento.cri_id` e `imovel.cri_id` apontam para `cri` e devem **coincidir** quando `documento.is_documento_atual = 1`.
- `origem_fim_cadeia` referencia `origem` (não `lancamento`); crie `origem` antes de migrar `origem_fim_cadeia`.
- CHECKs de fim de cadeia só devem ser ativados após corrigir nulos existentes.

---

## 10) Regras de exclusao (ON DELETE)

- **`imovel` → `documento`**: `ON DELETE CASCADE`.
- **`imovel` → `tis_imovel`**: `ON DELETE CASCADE`.
- **`documento` → `lancamento`**: `ON DELETE CASCADE`.
- **`lancamento` → `origem`**: `ON DELETE CASCADE`.
- **`origem` → `origem_fim_cadeia`**: `ON DELETE CASCADE`.
- **`lancamento` → `lancamento_pessoa`**: `ON DELETE CASCADE`.
- **Documentos gerados automaticamente**: nao ha criacao automatica de documentos na migracao.
- **Regra em runtime**: lancamentos do tipo `inicio_matricula` criam **um ou mais** `documento` automaticamente (dependendo da quantidade de origens, usando `tipo`, `numero` e `cri_id`).
- **Exclusao**: ao excluir um `lancamento` do tipo `inicio_matricula`, apagar os `documento` criados automaticamente por ele (derivar via `origem.documento_id`).
- **Arquivamento**: `imovel.arquivado = 1` desativa o imovel sem apagar a cadeia.

---

## 11) Resultado esperado

- **Esquema menor e coerente** (redução significativa de tabelas e campos legados).
- **Sem perda de semântica essencial** para a cadeia dominial.
- **Compatível com SQLite** e migração limpa de dados.
