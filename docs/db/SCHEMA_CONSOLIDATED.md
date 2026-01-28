# Schema Consolidado (v2) - Cadeia Dominial

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
- **Normalizar `numero`**: manter apenas números; não precisamos de letras no número (o tipo já indica a letra).
- Remover `observacoes`.
- **Adicionar `is_principal`** (0/1) para marcar o documento vigente do imovel.
- **Demais campos permanecem** (ex: `data`, `livro`, `folha`, `data_cadastro`, `sigla_patrimonio_publico`).

**`dominial_lancamento`**
- Remover campos legados: `transmitente_id`, `adquirente_id`, `cartorio_transacao_id`.
- Remover campos de origem legados: `origem`, `documento_origem_id`, `livro_origem`, `folha_origem`, `data_origem`.
- Usar `lancamento_pessoa` para pessoas e `cartorio_transmissao_id` (manual) para transmissão.
- Renomear `livro_transacao`, `folha_transacao`, `data_transacao` para `*_transmissao`.
- Renomear `cartorio_origem_id` → `cri_origem_id` (FK para `cri`).
- Remover `eh_inicio_matricula` (derivado de `lancamento_tipo.tipo`).
- Manter `numero_lancamento` (inteiro informado pelo usuario).
- Manter `forma` (texto livre informado pelo usuario).
- **Demais campos permanecem** (ex: `data`, `valor_transacao`, `area`, `detalhes`, `observacoes`, `descricao`, `titulo`).

**`cri`**
- Renomear tabela `dominial_cartorios` → `cri`.
- Remover `tipo` (todos os registros são CRI).

**`dominial_imovel`**
- Um `imovel` representa a matricula vigente. Quando a matricula muda, cria-se um novo `imovel`.
- Nao manter campos derivados (`matricula`, `tipo_documento_principal`); usar `documento.is_principal`.

### 2.3 Fim de cadeia

- **Manter `origem_fim_cadeia`**, agora vinculada a uma tabela `origem` (suporta múltiplas origens por lançamento).
- **Remover `fim_cadeia` (catálogo)** por não uso real.
- **Nao manter** campos de fim de cadeia em `documento` (o fim de cadeia qualifica a `origem`).

> **Decisão:** não inline em `lancamento`, pois perderíamos suporte a múltiplas origens. Se futuramente não houver multi-origem, avaliamos simplificar.

#### Consistência de fim de cadeia (recomendação)

- **Nao criar** coluna `fim_cadeia` no novo esquema (nao existe no legado atual).
- `tipo_fim_cadeia` e **opcional**; quando preenchido, indica fim de cadeia.
- `classificacao_fim_cadeia` e **obrigatoria apenas quando** `tipo_fim_cadeia` estiver preenchido.
- Se `tipo_fim_cadeia = 'outra'`, exigir `especificacao_fim_cadeia`.
- Adicionar CHECKs e corrigir dados nulos antes da migracao.

#### Origens estruturadas (nova tabela)

- Criar tabela `origem` para armazenar dados estruturados da origem do lancamento.
- `origem` substitui o uso de strings em `lancamento.origem` e fornece base para `origem_fim_cadeia`.
- `origem_fim_cadeia` passa a referenciar `origem` (1:1 por origem).
- **Um `lancamento` pode ter várias origens** (modelado por múltiplas linhas em `origem` com `indice`).
- **Fim de cadeia nao e um tipo de origem**. Ele e uma qualificacao da `origem` via `origem_fim_cadeia`.

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

- `pessoas`
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
- `numero` TEXT NOT NULL (normalizado so com digitos)
- `cri_id` FK obrigatório (aponta para `cri`)
- `imovel_id` FK obrigatório
- `is_principal` INTEGER NOT NULL DEFAULT 0 CHECK (is_principal IN (0,1))
- `lancamento_origem_id` FK opcional (lancamento que **criou** o documento em runtime)
- UNIQUE (`cri_id`, `tipo`, `numero`)
- UNIQUE parcial para garantir **um** documento principal por imovel:
  - `UNIQUE (imovel_id) WHERE is_principal = 1`
- Sem `origem`, sem `nivel_manual`

**`imovel` (resumo)**
- `cartorio_id` FK obrigatório (aponta para `cri`)
- `proprietario_id` FK obrigatório (aponta para `pessoas`)
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
- `cri_origem_id` (para inicio de matricula; FK para `cri`, **obrigatorio quando tipo = inicio_matricula**)
- `cartorio_transmissao_id` (manual, tabela separada de `cri`, **opcional**)
- `livro_transmissao`, `folha_transmissao`, `data_transmissao` (renomeados)
- `numero_lancamento` INTEGER NOT NULL CHECK (numero_lancamento > 0)
- UNIQUE (`documento_id`, `numero_lancamento`)
- Usado para compor a sigla exibida do lancamento (ex: `AV5 M123`).
- `forma` TEXT (opcional, entrada livre do usuario)

**`origem` (resumo)**
- `lancamento_id` + `indice` unico
- `indice` deve ser **>= 0** e **contiguo** por `lancamento` (0,1,2...)
- `cri_id` (FK para `cri`, opcional)
- `tipo` (`matricula`, `transcricao`)
- `numero` (somente digitos), `livro`, `folha`, `data`
- `observacoes` (opcional)

**`origem_fim_cadeia` (resumo)**
- `origem_id` unico
- `tipo_fim_cadeia`, `classificacao_fim_cadeia`, `especificacao_fim_cadeia`
- `classificacao_fim_cadeia` obrigatoria quando `tipo_fim_cadeia` estiver preenchido
- `especificacao_fim_cadeia` obrigatoria quando `tipo_fim_cadeia = 'outra'`

**`tis_imovel` (resumo)**
- `id` PK
- `tis_id` FK obrigatório (`tis`)
- `imovel_id` FK obrigatório (`imovel`)
- UNIQUE (`tis_id`, `imovel_id`)

---

### 3.3 Regras condicionais (aplicacao/trigger)

- Se `lancamento_tipo.tipo = 'inicio_matricula'`, entao `lancamento.cri_origem_id` deve ser **obrigatorio**.
- Se `documento.is_principal = 1`, entao `documento.cri_id` deve **coincidir** com `imovel.cartorio_id`.
- As flags `requer_*` em `lancamento_tipo` sao apenas configuracoes de UI/validacao e **nao** devem ser tratadas como constraints do banco.
- As flags `requer_*_origem` referem-se aos campos da tabela `origem` (e nao a campos em `lancamento`).
- `origem.indice` deve ser contiguo por `lancamento` (enforce via aplicacao/trigger).
- Evitar deletar o **ultimo** documento principal de um `imovel` (enforce via aplicacao/trigger).

---

## 4) Ajustes de compatibilidade SQLite

- `DATE` e `TIMESTAMP` → `TEXT` (ISO8601).
- `BOOLEAN` → `INTEGER` (0/1).
- `DECIMAL` → `REAL` (ou `INTEGER` com centavos se necessário).
- Enums → `CHECK`.

---

## 5) Migracao de dados (ordem sugerida)

1. **Backups e contagens:** snapshot completo + contagem de linhas.
2. **Migrar pessoas/CRI/terras/tis/imovel**.
3. **Documento:**
   - Criar `tipo` inline.
   - Remover `origem`/`nivel_manual`.
   - Normalizar `numero`.
   - Garantir apenas `matricula`/`transcricao` (remover valor legado `transmissao`).
   - Preencher `documento.is_principal = 1` para o documento vigente de cada imovel (exatamente 1).
   - Preencher `documento.lancamento_origem_id` para documentos criados por `inicio_matricula` (quando for possivel inferir).
4. **Lancamento:**
   - Migrar `lancamento_pessoa` se necessário.
   - Remover campos legados.
   - Renomear `cartorio_origem_id` → `cri_origem_id` e apontar FK para `cri`.
   - Definir `numero_lancamento` por documento antes de aplicar a constraint (ex: ordem por `data`, `id`).
5. **Origem fim de cadeia:**
   - Criar `origem` e migrar dados estruturados (ou parsing do `lancamento.origem`).
   - Atualizar `origem_fim_cadeia` para referenciar `origem`.
   - Nao criar documentos automaticamente na migracao; isso e comportamento de runtime para `inicio_matricula`.
6. **Remover tabelas legadas** após checagens.

### Mapa de renomeacoes (cartorio → cri)

**Tabela**
- `dominial_cartorios` → `cri`
- `cartorio_transmissao` (nova tabela, manual)

**Documentos**
- `documento.cartorio_id` → `documento.cri_id` (FK passa a apontar para `cri`)
- `documento.cri_atual_id` → removido
- `documento.cri_origem_id` → removido

**Lancamentos**
- `lancamento.cartorio_origem_id` → `lancamento.cri_origem_id`
- `lancamento.cartorio_transmissao_id` → manter (tabela separada, preenchimento manual)
- `lancamento.cartorio_transacao_id` → removido (legado)

**Origens**
- Criar `origem` e migrar de `lancamento.origem` (se ainda existir) + `origemfimcadeia.indice_origem`
- `origem_fim_cadeia.lancamento_id + indice_origem` → `origem_fim_cadeia.origem_id`

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

1. **Normalização de `documento.numero`:** extrair apenas dígitos e validar unicidade por cartório.

---

## 9) Notas para migracao futura (forward-compat)

- `origem` é a fonte estruturada oficial; `lancamento.origem` (string) deve ser removido após migração.
- `cartorio_transmissao_id` permanece **separado** de `cri` e é **preenchido manualmente**.
- `documento.cri_id` e `imovel.cartorio_id` apontam para `cri` e devem **coincidir** quando `documento.is_principal = 1`.
- `origem_fim_cadeia` referencia `origem` (não `lancamento`); crie `origem` antes de migrar `origem_fim_cadeia`.
- CHECKs de fim de cadeia só devem ser ativados após corrigir nulos existentes.

---

## 10) Regras de exclusao (ON DELETE)

- **`imovel` → `documento`**: `ON DELETE CASCADE`.
- **`imovel` → `tis_imovel`**: `ON DELETE CASCADE`.
- **`documento` → `lancamento`**: `ON DELETE CASCADE`.
- **`lancamento` → `documento` (via `documento.lancamento_origem_id`)**: `ON DELETE CASCADE`.
- **`lancamento` → `origem`**: `ON DELETE CASCADE`.
- **`origem` → `origem_fim_cadeia`**: `ON DELETE CASCADE`.
- **`lancamento` → `lancamento_pessoa`**: `ON DELETE CASCADE`.
- **Documentos gerados automaticamente**: nao ha criacao automatica de documentos na migracao.
- **Regra em runtime**: lancamentos do tipo `inicio_matricula` criam **um ou mais** `documento` automaticamente (dependendo da quantidade de origens, usando `tipo`, `numero` e `cartorio`).
- **Exclusao**: ao excluir um `lancamento` do tipo `inicio_matricula`, apagar os `documento` criados automaticamente por ele.
- **Arquivamento**: `imovel.arquivado = 1` desativa o imovel sem apagar a cadeia.

---

## 11) Resultado esperado

- **Esquema menor e coerente** (redução significativa de tabelas e campos legados).
- **Sem perda de semântica essencial** para a cadeia dominial.
- **Compatível com SQLite** e migração limpa de dados.
