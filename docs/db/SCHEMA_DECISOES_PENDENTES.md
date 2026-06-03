# Decisões Pendentes do Schema v2

> **Quem deve ler isso:** Luandro (decisor final), Hiure (implementador), e qualquer pessoa que queira entender por que o schema v2 está do jeito que está. Este documento é em português para ser acessível a pessoas não-desenvolvedoras, mas mantém a precisão técnica.
>
> **Por que este documento existe:** A revisão cega do schema v2 (em `docs/SCHEMA_V2_BLINDSPOT_REVIEW.md`) encontrou 27 pontos cegos. Dez deles não podem ser resolvidos sem uma decisão humana. **A partir da sessão de grupo de 2026-06-02/03 com Luandro (decisor) e Hiure (implementador), 15 perguntas (Q1–Q15, mais a Q11b) foram decididas.** A Crítica Codex 2026-06-03 (gpt-5.5, high) encontrou 8 blockers; o round 2 pós-D1–D4 + T1–T4 encontrou mais 2 BLOCKERS e 1 nice-to-have — todos resolvidos antes do PR.

## Contexto rápido

O sistema **Cadeia Dominial** rastreia a história de propriedade de imóveis rurais no Brasil. Cada imóvel tem uma cadeia de documentos (matrícula, registros, averbações) e cada documento pode ter múltiplos lançamentos (transações) que citam documentos anteriores. O grafo resultante é a "cadeia dominial" — visualizada em React Flow.

**O schema legado** (Django + PostgreSQL, em `docs/legacy-django/03-database-models.md`) tem 13 tabelas principais. Estamos migrando isso para **Drizzle ORM + SQLite/D1** (Cloudflare). A revisão cega descobriu que o draft atual do ERD v2 não bate com o Django em vários pontos — e antes de corrigir, precisamos decidir **como** queremos que o sistema se comporte.

Cada pergunta abaixo tem 3 partes:
- 🤔 **A pergunta** — em linguagem simples
- 📍 **Como funciona hoje** — o que o Django faz (nosso ponto de partida)
- ⚖️ **As opções** — A, B, C, etc. com análise honesta
- 🗄️ **Como fica no banco** — exemplo de SQL/linhas resultantes
- 🌳 **Como fica no grafo** — descrição visual de cada opção no React Flow
- ✅ **Recomendação** — quando aplicável

---

## Q1 — O que acontece quando um imóvel é apagado?

### 🤔 A pergunta
Se um usuário apagar um imóvel (por exemplo, porque foi cadastrado errado), o que deve acontecer com todos os documentos, lançamentos e pessoas ligados a ele? Devem sumir junto (cascade), ou o sistema deve impedir o apagamento (protect)?

### 📍 Como funciona hoje no Django
O Django tem duas estratégias em jogo:

- **PROTECT** (proteção): o sistema **recusa** apagar o imóvel se ele tiver dependências críticas (como um cartório ou uma pessoa-proprietário). Força o usuário a resolver manualmente.
- **CASCADE** (cascata): quando o imóvel é apagado, **tudo relacionado some junto** — todos os documentos, todos os lançamentos, todas as pessoas envolvidas naquela transação.

Hoje, no Django:
- `Documento.imovel` → Imovel: **CASCADE** (apagar imóvel apaga documentos)
- `Lancamento.documento` → Documento: **CASCADE** (apagar documento apaga lançamentos)
- A cadeia se propaga: Imovel → Documento → Lancamento → LancamentoPessoa + OrigemFimCadeia

### ⚖️ As opções

#### Opção A — CASCADE total (igual ao Django hoje)
> Apagar o imóvel apaga tudo abaixo na cadeia.

**Prós:** Simples, consistente, mesmo comportamento do legado.
**Contras:** Um clique errado apaga anos de histórico. Irreversível.

**🗄️ Como fica no banco:**

```sql
-- Apagar o imóvel 123
DELETE FROM imovel WHERE id = 123;
-- Automaticamente:
-- DELETE FROM documento WHERE imovel_id = 123;  -- remove 50 documentos
-- DELETE FROM lancamento WHERE documento_id IN (...);  -- remove 200 lançamentos
-- DELETE FROM lancamento_pessoa WHERE lancamento_id IN (...);  -- remove 400 pessoas
-- DELETE FROM origem_fim_cadeia WHERE lancamento_id IN (...);  -- remove 50 origens
```

**🌳 Como fica no grafo:** O nó do imóvel e **toda a sua subárvore** desaparecem juntos. O grafo fica "limpo" — sem buracos.

#### Opção B — PROTECT (não permite apagar)
> O sistema recusa apagar o imóvel enquanto houver documentos.

**Prós:** Zero risco de perda acidental. Força revisão humana.
**Contras:** Para "limpar" um imóvel errado, é preciso apagar manualmente cada documento (que também tem PROTECT) e cada lançamento. Processo doloroso.

**🗄️ Como fica no banco:**

```sql
DELETE FROM imovel WHERE id = 123;
-- ERRO: foreign key violation. "Cannot delete — 50 documents reference this property."
-- O comando falha. Nenhuma linha é alterada.
```

**🌳 Como fica no grafo:** Imóvel e cadeia continuam visíveis até o usuário resolver manualmente. Nada some.

#### Opção C — CASCADE com "lixeira" (soft delete + CASCADE)
> Adicionar uma coluna `deleted_at` em cada tabela. "Apagar" = marcar `deleted_at = NOW()`. Cascade real é opcional e restrito a admins.

**Prós:** Reversível, auditável, seguro. Lixeira virtual.
**Contras:** Toda query precisa filtrar `WHERE deleted_at IS NULL`. Mais código. Mais índices.

**🗄️ Como fica no banco:**

```sql
UPDATE imovel SET deleted_at = '2026-06-02 12:00:00' WHERE id = 123;
-- Nada é apagado de verdade. A coluna deleted_at marca como "na lixeira".
-- Queries normais:
SELECT * FROM imovel WHERE deleted_at IS NULL;  -- 999 imóveis visíveis
SELECT * FROM imovel;  -- 1000 imóveis (incluindo o da lixeira)
```

**🌳 Como fica no grafo:** O imóvel e a cadeia **ficam visíveis** na visualização normal (porque a query filtra), mas com um indicador cinza/lixeira. Admin pode restaurar ou hard-deletar.

### ✅ Recomendação
**Opção C (soft-delete + CASCADE)** se os imóveis errados forem comuns; **Opção B (PROTECT)** se a auditoria for mais importante que a conveniência. **Evite Opção A** a menos que o legado exija paridade exata.

---

## Q2 — Como lidamos com "desativar" em vez de apagar?

### 🤔 A pergunta
Em sistemas jurídicos/cartoriais, é comum **não apagar** um documento ou pessoa (por causa de auditoria e histórico legal) mas **desativá-lo** para que não apareça em cadastros novos. Como modelamos isso no v2?

### 📍 Como funciona hoje no Django
O Django legado tem **quase nenhum soft-delete**:
- A única tabela com `ativo` é `FimCadeia` (definições pré-cadastradas como "INCRA", "Estado da Bahia").
- Para Pessoas, Documentos, Imóveis, Lançamentos: **não há campo de desativação**. Quem quiser "desativar" precisa hard-deletar.

Isso é um problema no novo sistema porque:
1. A Lei Geral de Proteção de Dados (LGPD) exige que pessoas possam pedir a remoção de seus dados.
2. Cadastros errados (uma pessoa cadastrada com CPF errado) precisam ser corrigidos sem perder o histórico.

### ⚖️ As opções

#### Opção A — Hard delete (igual ao Django legado)
> Sem soft-delete. "Desativar" = apagar de verdade.

**🗄️ Como fica no banco:**

```sql
DELETE FROM pessoa WHERE id = 555;
-- A pessoa some. Se era transmitente de 30 lançamentos, propaga cascade.
```

**🌳 Como fica no grafo:** Pessoa some do grafo. Lançamentos que dependiam dela podem ter `transmitente_id = NULL` (se SET NULL) ou serem apagados (se CASCADE).

#### Opção B — Soft-delete com flag `deleted_at`
> Adiciona coluna `deleted_at` em **todas** as tabelas relevantes. Hard delete só via admin.

**🗄️ Como fica no banco:**

```sql
-- "Apagar" pessoa
UPDATE pessoa SET deleted_at = NOW() WHERE id = 555;
-- A pessoa continua existindo no banco, mas escondida.

-- Listar pessoas (query padrão do app)
SELECT * FROM pessoa WHERE deleted_at IS NULL;
-- Não retorna a pessoa 555.

-- Auditoria (query de admin)
SELECT * FROM pessoa WHERE id = 555;
-- Retorna, com o deleted_at preenchido.
```

**🌳 Como fica no grafo:** A pessoa fica com opacidade 30% / ícone de "lixeira". Lançamentos vinculados continuam aparecendo (porque têm dados suficientes para se manter).

#### Opção C — Soft-delete + LGPD (anonimização)
> "Apagar" = substituir os campos pessoais por `NULL` ou hash, mas manter a estrutura (id, FKs, datas).

**🗄️ Como fica no banco:**

```sql
-- "Apagar" pessoa (LGPD)
UPDATE pessoa
SET nome = '[REMOVIDO POR LGPD]',
    cpf = NULL,
    rg = NULL,
    data_nascimento = NULL,
    email = NULL,
    telefone = NULL,
    deleted_at = NOW()
WHERE id = 555;
-- A pessoa continua existindo (FKs não quebram), mas os dados pessoais sumiram.
```

**🌳 Como fica no grafo:** O nó da pessoa mostra "[REMOVIDO]" em vez do nome. A cadeia **continua navegável** porque o id existe.

### ✅ Recomendação
**Opção C (soft-delete + anonimização LGPD)** é a melhor prática geral — é a única que atende simultaneamente a auditoria jurídica **e** a LGPD sem comprometer a navegação do grafo. A maioria dos sistemas brasileiros de cartório está indo por esse caminho. **Mas no contexto do v2 (Cadeia Dominial = sistema de pesquisadores de grilagem que copiam dados do cartório verbatim), a Opção B foi escolhida** (ver tabela de Decisões): `Pessoa` só tem `nome` (sem CPF/RG/email/telefone), então anonimização completa (C) não se aplica. Soft-delete (B) preserva divergências entre certidões como **evidência de grilagem**. Hard-delete (A) vira ainda mais perigoso com esse contexto.

---

## Q3 — Quantos "Fins de Cadeia" um lançamento pode ter?

### 🤔 A pergunta
Um lançamento (transação) pode ter várias origens (documentos anteriores que ele cita). A tabela `OrigemFimCadeia` marca **quais** dessas origens são o "fim" da cadeia dominial (i.e., até onde a história daquele imóvel é rastreável). A pergunta é: **uma** `OrigemFimCadeia` por cadeia, ou **muitas** (uma por origem)?

### 📍 Como funciona hoje no Django
O Django permite **muitas** OrigemFimCadeia por Lancamento — uma para cada origem que termina a cadeia:

```python
class OrigemFimCadeia(models.Model):
    lancamento = models.ForeignKey(Lancamento, on_delete=CASCADE)
    indice_origem = models.IntegerField()  # 0, 1, 2, ...
    fim_cadeia = models.BooleanField()
    tipo_fim_cadeia = models.CharField(...)  # destacamento_publico, outra, sem_origem
    classificacao_fim_cadeia = models.CharField(...)  # origem_lidima, sem_origem, inconclusa

    class Meta:
        unique_together = ['lancamento', 'indice_origem']
```

Ou seja: para um Lancamento com 3 origens, podem existir até 3 `OrigemFimCadeia` — uma por origem, marcando se aquela origem específica é o fim da cadeia.

### ⚖️ As opções

#### Opção A — Uma OrigemFimCadeia por Lancamento (1:1)
> Cada Lancamento tem **no máximo uma** OrigemFimCadeia.

**Prós:** Schema mais simples, fácil de consultar (`Lancamento.fim_cadeia` direto).
**Contras:** Perde a informação de **qual origem** especificamente termina a cadeia. Se um lançamento cita 3 origens e 2 delas terminam a cadeia, perdemos isso.

**🗄️ Como fica no banco:**

```sql
CREATE TABLE lancamento (
    id INTEGER PRIMARY KEY,
    documento_id INTEGER,
    -- ...
    fim_cadeia BOOLEAN,
    tipo_fim_cadeia TEXT
);
-- Se Lancamento 10 cita origens [5, 7, 9], e apenas a origem 7 termina a cadeia,
-- essa informação não é registrada.
```

**🌳 Como fica no grafo:** O nó do Lancamento tem um único atributo "fim de cadeia". Não dá pra saber visualmente qual das 3 origens é o fim.

#### Opção B — Muitas OrigemFimCadeia por Lancamento (1:N, como o Django)
> Cada Lancamento pode ter **várias** OrigemFimCadeia, uma por origem.

**Prós:** Preserva toda a informação do legado. Permite grafo rico.
**Contras:** Query mais complexa (precisa JOIN). Mais registros.

**🗄️ Como fica no banco:**

```sql
CREATE TABLE origem_fim_cadeia (
    id INTEGER PRIMARY KEY,
    lancamento_id INTEGER REFERENCES lancamento(id),
    indice_origem INTEGER,  -- 0, 1, 2
    fim_cadeia BOOLEAN,
    tipo_fim_cadeia TEXT,
    classificacao_fim_cadeia TEXT,
    UNIQUE(lancamento_id, indice_origem)
);
-- Lancamento 10 cita origens [5, 7, 9]:
INSERT INTO origem_fim_cadeia VALUES (1, 10, 0, false, NULL, NULL);
INSERT INTO origem_fim_cadeia VALUES (2, 10, 1, true, 'destacamento_publico', 'origem_lidima');
INSERT INTO origem_fim_cadeia VALUES (3, 10, 2, false, NULL, NULL);
-- A origem 7 (indice 1) é a que termina a cadeia.
```

**🌳 Como fica no grafo:** Cada Lancamento pode ter **múltiplas folhas** "fim de cadeia" — uma por origem. O usuário vê:
- 3 arestas saindo do Lancamento (para origens 5, 7, 9)
- 1 nó folha "fim" na ponta da aresta que vai pra origem 7
- Os outros 2 caminhos continuam se expandindo

**Exemplo visual:**

```
Lançamento R-2 (cita origens M-99999, M-88888, M-77777)
  ├──> M-99999 ─> [continua a cadeia]
  ├──> M-88888 ─> 🟥 FIM (destacamento público)  ← esta é a que termina
  └──> M-77777 ─> [continua a cadeia]
```

### ✅ Recomendação
**Opção B (1:N, como o Django)** — a informação semântica é valiosa, e a complexidade de query é gerenciável. Mudar para 1:1 seria perda de informação sem ganho real.

---

## Q4 — Os dados pessoais (CPF, RG, nome) devem ser criptografados em repouso?

### 🤔 A pergunta
O sistema armazena dados pessoais sensíveis (PII — _Personally Identifiable Information_): nome completo, CPF, RG, data de nascimento, email, telefone. Por causa da LGPD e de boas práticas de segurança, devemos criptografar esses campos no banco de dados?

### 📍 Como funciona hoje no Django
**Não há criptografia no legado.** Os campos são armazenados em texto puro:

- `Pessoas.cpf` — texto puro, índice único
- `Pessoas.rg` — texto puro
- `Pessoas.nome` — texto puro
- `Pessoas.data_nascimento` — texto puro
- `Pessoas.email` — texto puro
- `Pessoas.telefone` — texto puro

Se o banco for comprometido (acesso ao arquivo SQLite, dump de banco, log exposto), todos os CPFs estão legíveis.

### ⚖️ As opções

#### Opção A — Texto puro (igual ao Django legado)
> Sem criptografia. Confiar em segurança de infraestrutura (chaves de API, firewall, HTTPS).

**Prós:** Performance máxima, queries simples (`WHERE cpf = ?`).
**Contras:** Em caso de vazamento do banco, todos os CPFs são comprometidos. Não atende às melhores práticas de LGPD.

**🗄️ Como fica no banco:**

```sql
CREATE TABLE pessoa (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,  -- "João da Silva"
    cpf TEXT UNIQUE       -- "123.456.789-01"
);
-- Indexação: índice B-tree normal em cpf.
-- Busca: SELECT * FROM pessoa WHERE cpf = '123.456.789-01';  -- O(n log n)
```

**🌳 Como fica no grafo:** Sem impacto direto. O React Flow mostra o nome da pessoa no nó dela.

#### Opção B — Criptografia em nível de aplicação (AES-256-GCM)
> Antes de salvar, criptografa com chave mestra. Antes de ler, descriptografa.

**Prós:** Em caso de vazamento do banco, os PII são ilegíveis. Atende LGPD.
**Contras:** Queries `WHERE cpf = ?` não funcionam (precisa descriptografar todas as linhas, ou usar hash). Mais código, mais latência.

**🗄️ Como fica no banco:**

```sql
CREATE TABLE pessoa (
    id INTEGER PRIMARY KEY,
    nome_encrypted BLOB,  -- bytes cifrados com AES-256-GCM
    cpf_encrypted BLOB,   -- bytes cifrados
    cpf_hash TEXT UNIQUE   -- SHA-256 do CPF normalizado, para unicidade
);
-- Busca por CPF: SELECT * FROM pessoa WHERE cpf_hash = SHA256('123.456.789-01');
-- Leitura: SELECT id, nome_encrypted, cpf_encrypted; depois descriptografa em memória.
```

**🌳 Como fica no grafo:** Sem impacto direto. O React Flow continua mostrando o nome (que vem descriptografado do backend).

#### Opção C — Criptografia em repouso do banco inteiro (SQLite SEE / D1 always-encrypted)
> O arquivo do banco é criptografado no disco. O conteúdo é cifrado em nível de armazenamento, não de campo.

**Prós:** Mais simples de implementar (geralmente é uma flag na connection string). Atende LGPD para armazenamento.
**Contras:** Queries SQL continuam legíveis quando o banco está aberto (em memória). Se o processo for comprometido em runtime, os dados são visíveis.

**🗄️ Como fica no banco:** Idêntico à Opção A em SQL, mas o arquivo `.sqlite` no disco é cifrado.

**🌳 Como fica no grafo:** Sem impacto.

### ✅ Recomendação
**Opção B (criptografia em nível de aplicação)** se o sistema for armazenar dados reais de pessoas físicas e houver risco de exposição. **Opção A** é aceitável se o sistema for usado em ambiente controlado (servidor interno, sem exposição à internet). **Opção C** é complemento, não substituto, de A ou B.

---

## Q5 — Onde validamos CPF e CNPJ — no banco ou na aplicação?

### 🤔 A pergunta
CPF e CNPJ têm regras de validação (formato + dígitos verificadores). Onde essa validação deve morar — em uma constraint do banco de dados (que rejeita inserts inválidos) ou só no código da aplicação (que filtra antes de enviar)?

### 📍 Como funciona hoje no Django
**A validação é na aplicação, não no banco.** O Django tem:

```python
class Pessoas(models.Model):
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True)
    # Sem validador de CPF no nível do model. Validação é responsabilidade do form/serializer.
```

Em SQL, o campo `cpf` é apenas `VARCHAR(14) UNIQUE` — aceita qualquer string de até 14 caracteres.

### ⚖️ As opções

#### Opção A — Validação só na aplicação (igual ao Django)
> Backend valida CPF/CNPJ antes de fazer o INSERT. Banco aceita qualquer string.

**Prós:** Simples, fácil de mudar regras de validação sem migração de banco.
**Contras:** Se alguém inserir via SQL direto (script de migração, admin, import em massa) e não passar pela app, dados ruins entram.

**🗄️ Como fica no banco:**

```sql
CREATE TABLE pessoa (
    id INTEGER PRIMARY KEY,
    cpf TEXT UNIQUE
    -- Sem CHECK constraint. Aceita 'foo', '123', etc.
);

-- Esses dois inserts passam:
INSERT INTO pessoa (cpf) VALUES ('123.456.789-01');  -- válido
INSERT INTO pessoa (cpf) VALUES ('qualquer');         -- INVÁLIDO, mas passa!
```

**🌳 Como fica no grafo:** Sem impacto.

#### Opção B — Validação dupla (app + CHECK constraint no banco)
> Backend valida antes de enviar. Banco também rejeita inválidos via CHECK constraint.

**Prós:** Defesa em profundidade. Dados ruins nunca entram, mesmo via script SQL.
**Contras:** CHECK constraints em SQLite têm sintaxe limitada. Validação real (dígitos verificadores) precisa de expressão regular ou função — nem sempre suportada.

**🗄️ Como fica no banco (SQLite):**

```sql
CREATE TABLE pessoa (
    id INTEGER PRIMARY KEY,
    cpf TEXT UNIQUE CHECK (
        cpf IS NULL OR
        cpf GLOB '[0-9][0-9][0-9].[0-9][0-9][0-9].[0-9][0-9][0-9]-[0-9][0-9]'
    )
);
-- '123.456.789-01' passa. 'qualquer' falha com CHECK constraint violation.
```

**🌳 Como fica no grafo:** Sem impacto.

#### Opção C — Banco armazena normalizado (só dígitos), app valida e formata
> App valida com dígitos verificadores. Banco armazena só os 11 dígitos. Formatação (com pontos e traços) é responsabilidade da UI.

**Prós:** Validação fica trivial (regex `^[0-9]{11}$`). Busca por CPF é direta. Padronização garantida.
**Contras:** Migrar dados antigos que têm formatação diversa exige limpeza. UI tem que formatar para exibir.

**🗄️ Como fica no banco:**

```sql
CREATE TABLE pessoa (
    id INTEGER PRIMARY KEY,
    cpf TEXT UNIQUE CHECK (cpf IS NULL OR cpf GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]')
);
-- '12345678901' passa. '123.456.789-01' falha.
```

**🌳 Como fica no grafo:** Sem impacto direto. UI formata para "123.456.789-01" na exibição.

### ✅ Recomendação
**Opção C (normalizado no banco, validado na app)** — é a melhor prática da indústria. CHECK constraint garante integridade mesmo se a app falhar. UI formata para exibição. Migrar dados antigos exige um script de normalização (que o `legacy-fit` script — T-300 — pode fazer).

---

## Q6 — No React Flow, mostramos TODOS os fins de cadeia ou só o "atual"?

### 🤔 A pergunta
Lembrando da Q3: cada Lancamento pode ter **várias** OrigemFimCadeia (uma por origem). No React Flow, cada fim de cadeia vira um **nó folha** sintético (`fim-<documento.id>-<indice>`). A pergunta é: visualizamos **todos** os fins de cadeia (provenance completa) ou **só o mais recente / o "atual"** (vista simplificada)?

### 📍 Como funciona hoje
A documentação atual do React Flow (`docs/react-flow.md`) define:

> **Fim de cadeia** → Synthetic leaf node
>   - `id`: `fim-<documento.id>-<indice>`
>   - `data`: include `tipo_fim_cadeia`, `classificacao_fim_cadeia`
>   - edge from `doc-<documento.id>` to `fim-...`

Ou seja: o React Flow **já está planejado** para mostrar **um nó por (documento, indice)**. Mas o documento não esclarece se isso é "todos os fins" ou "só o atual".

### ⚖️ As opções

#### Opção A — Mostrar TODOS os fins de cadeia (provenance completa)
> Cada OrigemFimCadeia vira um nó folha. O usuário vê **toda** a história.

**Prós:** Auditável, completo, atende historiadores e pesquisadores. Não esconde nada.
**Contras:** Grafos densos, podem ter 10+ nós folha em uma cadeia complexa. Ruído visual para usuários leigos.

**🗄️ Como fica no banco:** Idêntico à Q3-OpçãoB — uma OrigemFimCadeia por origem.

**🌳 Como fica no grafo:**

```
M-12345 (Imóvel Atual)
  ├──> Lançamento R-1 ──> M-99999 ──> 🟥 FIM (origem: INCRA)
  ├──> Lançamento Av-1 (sem origem)
  └──> Lançamento R-2 ──> M-12345 (origem = si mesmo, loop)
                        ├──> M-88888 ──> 🟥 FIM (destacamento público)
                        └──> M-77777 ──> 🟥 FIM (sem origem)
```

Cadeia com 3 nós folha "FIM" — um para cada fim de cadeia registrado. Cada um com sua cor (verde/vermelho/amarelo) por classificação.

#### Opção B — Mostrar só o "atual" (vista simplificada)
> Apenas o Lancamento mais recente (com `fim_cadeia = true`) vira nó folha. Outros são escondidos.

**Prós:** Visual limpo. Ideal para usuários leigos / mobile / impressão.
**Contras:** Perde informação. Difícil voltar atrás se o "atual" mudar (um novo lançamento pode redefinir o que é "atual").

**🗄️ Como fica no banco:** Precisa de uma coluna ou query que diga "este é o fim atual". Pode ser um flag `is_current` em `OrigemFimCadeia` ou um campo em `Lancamento`.

**🌳 Como fica no grafo:**

```
M-12345 (Imóvel Atual)
  ├──> Lançamento R-1 ──> M-99999 ──> 🟥 FIM (único nó folha visível)
  ├──> Lançamento Av-1
  └──> Lançamento R-2 ──> M-12345
```

Só 1 nó folha visível (o "atual"). Os outros 2 fins de cadeia do exemplo anterior ficam **escondidos** mas ainda no banco.

#### Opção C — Híbrido: padrão simplificado, toggle para provenance
> Por padrão, mostra só o atual. Botão "Mostrar histórico completo" revela os outros.

**Prós:** Melhor dos dois mundos. Leigos veem simplicidade; pesquisadores veem profundidade.
**Contras:** Mais código de UI. Dois modos de visualização para testar e manter.

**🗄️ Como fica no banco:** Idêntico à Q3-OpçãoB (provenance completa preservada).

**🌳 Como fica no grafo:** Mesmo grafo de A, mas com toggle `🔍 [Completo] / [Simples]`. Em modo Simples, só o nó folha "atual" aparece. Em modo Completo, todos aparecem.

### ✅ Recomendação
**Opção C (híbrido com toggle)** — é o que melhor atende a múltiplos públicos. O dado fica preservado (Q3-B), mas a UI adapta. Custo de implementação é baixo (basicamente um filtro no build do grafo). Se o orçamento de UI for apertado, **Opção A** é aceitável (e simplifica a versão "impressa").

---

## Q7 — Cross-chain delete behavior (UX menu) — bloqueia T-105

### 🤔 A pergunta
Um Documento pode ser `is_documento_atual=true` para N Imóveis E `origem.documento_id` para M outros Lancamentos. Quando o usuário clica "remover" num Lancamento ou Documento compartilhado entre múltiplas chains, qual o menu da UI?

### ⚖️ As opções

- **🅰️ Menu: [Editar] [Soft-delete]** — sem "Mover", sem hard-delete na UI
- **🅱️ Menu: [Editar] [Mover] [Soft-delete]** — sem hard-delete na UI principal; "Mover" como botão distinto
- **🅲️ Menu: [Editar] [Soft-delete (com blast radius)]** — confirmação rica no dialog (Q12=🅳️)

### ✅ Decisão
- **Q7a = 🅱️** (Hiure, 2026-06-02) — Menu: [Editar] [Mover] [Soft-delete]. "Mover" precisa ser um botão distinto pra dar confiança ao usuário de que o trabalho não vai ser perdido. Hard-delete é admin-only, fora do menu padrão.

---

## Q8 — Restore semantics (após Q7b=🅱️)

### 🤔 A pergunta
GIVEN Q7b=🅱️ (soft-delete conservador: só I + junctions, L's preservados), qual o comportamento do restore?

### ⚖️ As opções

- **🅰️ Restore simétrico** (recomendação) — undo exato do Q7b=B
- **🅱️ Restore cascata reverso** — restore I + cascade em L's (não se aplica com Q7b=B)
- **🅲️ Restore minimal** — só I.deleted_at = NULL. Junctions ficam "pendentes"
- **🅳️ Restore com revisão de pares** — usuário confirma cada junction/L individualmente

### ✅ Decisão
- **🅰️** (Hiure, 2026-06-03) — simétrico ao Q7b=B, intuitivo ("restaurar = desfazer").

---

## Q9 — Trilha de análise do pesquisador (researcher attribution)

### 🤔 A pergunta
Pesquisadores de grilagem ingerem dados públicos de cartórios (read-only) e adicionam anotações analíticas próprias. Quando um pesquisador cria/edita/remove uma anotação, o sistema deve rastrear **quem, quando, e qual era o conteúdo antes**?

### ⚖️ As opções

- **🅰️ Sem trilha** — última versão ganha
- **🅱️ Histórico de versões por anotação** — cada edit salva uma versão
- **🅲️ Histórico + provenance de criação** — registra também quem criou originalmente
- **🅳️ Tudo de C + exportação logada** — cada export (PDF, CSV, JSON) registra chain-of-custody

### ✅ Decisão
- **🅲️** (Hiure, 2026-06-03) — provenance de criação é crítica em equipe (autor original vs editor).

---

## Q10 — Raw vs normalized em campos string com variação real de cartório

### 🤔 A pergunta
`documento.numero` tem formato rígido (`<M|T>` + número) — não tem `_raw` ali (cartório não erra nesse campo). Mas outros campos têm variação real entre certidões:

- `documento.outorgante_nome`, `documento.outorgado_nome` — "João da Silva" vs "JOÃO DA SILVA" vs "João da Silva Santos"
- `documento.endereco` — "Rua S. João, 100" vs "Rua São João, n. 100"
- `lancamento.descricao` — texto livre
- `documento.cartorio_nome` — "1º Cartório de Registro de Imóveis" vs "1o. Cart. Reg. Imóveis"

O padrão `campo_raw` (verbatim) + `campo` (normalized pra busca) deve ser aplicado?

### ⚖️ As opções

- **🅰️ Não** — versão única basta
- **🅱️ Sim, em todos os campos variáveis** — `_raw` + normalized em cada
- **🅲️ Sim em B, mais flag `has_significant_variation`** — marca campo pra revisão quando raw ≠ normalized significativamente
- **🅳️ Tudo de C, mais detecção de discrepância entre certidões** — quando o MESMO imóvel tem certidões com strings diferentes, marca como discrepância (potencial grilagem)

### ✅ Decisão
- **🅰️ com exceção de `cartorio_nome`** (Hiure, 2026-06-03).
- Pros outros campos (nomes, endereços, descrições), busca fuzzy full-text sem `_raw`/`_normalized` é suficiente.
- **Mas `cartorio_nome` é o único onde a busca exata + normalização tem valor sistêmico** (cruzar certidões que citam o mesmo cartório).

### Implicação estrutural (Hiure, 2026-06-03)
`cartorio` vira **entidade própria** (tabela `cartorio`), não string field em `documento`:

- `cartorio` table com campos espelhando a API do **Sistema Nacional de Cartórios** (schema TBD)
- **Source 1 (preferencial):** API lookup → preenche/normaliza `cartorio` automaticamente
- **Source 2 (fallback):** cadastro manual pelo pesquisador, com os mesmos campos da API
- `documento.cartorio_id` é FK pra `cartorio.id`
- Sem campo "outros" / texto livre — pesquisador preenche a mesma estrutura da API

> **⚠️ Q11b (NOVA — Hiure, 2026-06-03):** refinamento da decisão. Ver seção dedicada abaixo.

---

## Q11b (NOVA, schema:) — Refinamento da Q10 sobre `cartorio` / `cri` / `cartorio_transmissao`

> **Contexto:** Q10 decidiu que `cartorio` é entidade própria. Q11b refina **COMO** essa entidade se relaciona com Documento, Lancamento e Origem — surgiu de dúvidas de implementação (Jun 2026).

### 🅰️ `lancamento.cri_origem_id` separado?
**Pergunta:** Lancamento precisa de uma coluna própria `cri_origem_id` (FK pra `cri`), separada do `origem.cri_id`?

**Resposta (Hiure, 2026-06-03): NÃO.** O CRI da origem já é capturado por `origem.cri_id` (a Origem do Lancamento já tem seu próprio `cri_id` FK). Lancamento herda isso transitivamente. Adicionar `cri_origem_id` no Lancamento seria duplicação.

### 🅱️ Comarca do imóvel muda ao longo do tempo?
**Pergunta:** Um Imóvel pode mudar de comarca (CRI) ao longo de sua história? Precisamos de `imovel_cri_historico` (N:N + período)?

**Resposta (Hiure, 2026-06-03): NÃO no v1.** Quando pesquisadores pegam o documento, isso já foi consolidado e não deve mudar. `imovel.cri_id` é fixo (FK direto, sem histórico). Se v2+ precisar, criar `imovel_cri_historico` na hora.

> **Importante (Hiure):** "sempre manter a unicidade de documentos com `cartorio + numero_documento` (M ou T + número)" — constraint de unicidade deve ser pelo par `(cartorio_id, tipo, numero)`, não só pelo número.

### 🅲️ Cada Documento tem 1 CRI só? Ou N:N (junction)?
**Pergunta:** `documento.cri_id` FK direto, ou junction `documento_cri` (N:N)?

**Resposta (Hiure, 2026-06-03): FK DIRETO. Cada Documento tem 1 CRI só.** Não precisa de junction N:N.

> *"(docs/db/SCHEMA_CONSOLIDATED.md:137) `UNIQUE (cri_id, tipo, numero)` — isso garante que a matrícula 12345 no 1º CRI de Salvador é um documento, e a matrícula 12345 no 2º CRI de Salvador é OUTRO documento distinto. Dois cartórios podem ter a mesma numeração para documentos diferentes e é por isso que a unicidade deve ser pelo par numero + cri_id."* (Hiure, 2026-06-03)

> *Exemplo:* matrícula 12345 no 1º CRI de Salvador = documento 1. Transcrição 12345 no 1º CRI de Salvador = documento 2. Matrícula 12345 no 2º CRI = documento 3. Matrícula 12345 no 1º CRI de Curitiba = documento 4.

### Schema final (Q10 + Q11b)

```
cri {
  int id PK
  text nome "1º Cartório de Registro de Imóveis de Salvador"
  text cidade
  text uf
  text CNS_codigo "Cadastro Nacional de Serventia (TBD)"
  // ... outros campos espelhando API do Sistema Nacional de Cartórios
  text created_at
  text updated_at
}

documento {
  int id PK
  text tipo "CHECK (matricula | transcricao)"
  text numero "normalizado, só dígitos"
  text numero_raw "valor original"
  int cri_id FK                  // FK direto, SEM junction
  // (Q13) imovel_id REMOVIDO em v2: chain membership foi para imovel_documento junction
  // (Q13) is_documento_atual REMOVIDO em v2: virou per-par na junction
  text created_at
  text deleted_at
  UNIQUE (cri_id, tipo, numero)  // par cartorio+tipo+numero
  // (Q10) sem outorgante_nome_raw / outorgado_nome_raw (busca fuzzy FTS5 basta)
}

imovel {
  int id PK
  int cri_id FK                  // fixo, sem histórico no v1
  int proprietario_id FK
  int arquivado "0/1"
  text created_at
  text deleted_at
  // (Q11b=🅲️) v1: imovel_id direto no documento (sem junction imovel_documento)
  //             Q13=N:N com junction vem depois (ver Q13 abaixo)
}

lancamento {
  int id PK
  int documento_id FK
  int tipo_id FK
  text cartorio_transmissao_nome "FREE-FORM, sem FK"  // tabelionato de notas
  text livro_transmissao
  text folha_transmissao
  text data_transmissao
  int numero_lancamento
  text forma
  // SEM cri_origem_id (Q11b=🅰️) — CRI da origem vem via origem.cri_id
  text created_at
  text deleted_at
  UNIQUE (documento_id, numero_lancamento)
}

origem {
  int id PK
  int lancamento_id FK
  int indice "0, 1, 2..."
  int cri_id FK                  // CRI de origem (Q11b=🅰️: este campo já é o "cri_origem_id")
  int documento_id FK "opcional"
  text tipo "matricula | transcricao | fim_cadeia"
  text numero
  text livro
  text folha
  text data
  text observacoes
  UNIQUE (lancamento_id, indice)
}
```

---

## Q12 — UX confirmation dialog (obrigatório em T-105)

### 🤔 A pergunta
Toda operação de delete (soft ou hard) deve passar por um dialog? Que informações o dialog mostra?

### ⚖️ As opções

- **🅰️ Dialog simples "tem certeza?"**
- **🅱️ Dialog com blast radius** — lista N+M chains, M' Lancamentos afetados
- **🅲️ Dialog com blast radius + botão "Editar ao invés"**
- **🅳️ Igual C, mais preview ANTES** — modal read-only read-back do que vai sumir, depois dialog de confirmação

### ✅ Decisão
- **🅳️** (Hiure, 2026-06-03) — "É importante perguntar ao usuário se ele quer mesmo apagar ou se ele quer só editar alguma informação" (Hiure, 2026-06-02).

### Comportamento final do delete (T-105)
1. Usuário clica "Apagar" → **modal de preview read-only** lista blast radius; permite CANCELAR ou AVANÇAR
2. AVANÇAR → **dialog de confirmação**:
   - Botão padrão (não destrutivo, foco do Enter): **"Editar ao invés de apagar"** → abre form de edição
   - Botão destrutivo (vermelho, type-to-confirm com nome do registro): **"Apagar mesmo assim"**
   - Checkbox opcional: "não mostrar preview de novo nesta sessão" (com audit log)
3. Confirmação → soft-delete (Q7a/B) + audit log (Q9=C) + provenance (Q10)

---

## Q13 — Modelagem de "chain membership" (CRITICAL — v1 tinha bug estrutural)

### 🤔 A pergunta
v1 (e v2 herdado) tinha `imovel ||--o{ documento : possui`, codificando "este Imóvel é o dono do Documento". Isso é **errado** — a cadeia histórica é **igualmente pertencente** a todos os Imóveis que a citam (matrícula compartilhada entre grileiros disputando, por exemplo).

### ⚖️ As opções

- **🅰️ Manter 1:N** — `documento.imovel_id` direto, "primário" + "shared" como exceção
- **🅱️ Junction `imovel_documento` (N:N completo)** — Documento perde `imovel_id` direto; chain membership via junction. `is_documento_atual` vira per-par.

### ✅ Decisão
- **🅱️** (Hiure, 2026-06-02) — *"Não é para ser prioritário de nenhuma cadeia dominial esse histórico. Ele pertence igualmente a diferentes imóveis."*

### Schema (Q13=🅱️)
```
imovel ||--o{ imovel_documento : ""
documento ||--o{ imovel_documento : ""
imovel_documento {
  int id PK
  int imovel_id FK
  int documento_id FK
  int is_documento_atual "0/1, per (Imovel, Documento) pair"
  int delete_operation_id "FK audit_log (Q8=A)"
  text created_at
  text deleted_at "soft-delete per chain membership"
}
documento {
  // (Q13) imovel_id REMOVIDO (vai pra junction)
  // (Q13) is_documento_atual REMOVIDO (vai pra junction, per-par)
}
```

### Implicações
- **T-100:** adicionar `imovel_documento` ao ERD; remover `imovel_id` e `is_documento_atual` de `documento`
- **T-101:** criar a tabela junction; ajustar FKs
- **T-300 (legacy-fit):** o legacy Django tinha `documento.imovel_id` (1:N); precisa popular a junction `imovel_documento` na migração

---

## Q14 — Operação MOVE/REASSIGN cross-chain (surgiu do insight do Hiure)

### 🤔 A pergunta
*"Ela não pode perder esses lançamentos. Eles precisam ser atrelados a outra cadeia dominial. Só enviar ele para outra cadeia dominial de outro imóvel."* (Hiure, 2026-06-02)

O sistema precisa de uma operação MOVE que:
- ✅ Preserva o Lancamento byte-for-byte (igualdade no MOVE = preservação de evidência)
- ✅ Torna o Lancamento visível na chain do Documento de destino (D'), sem mutar o L
- ✅ É auditável — registra o evento de move no log + na tabela append-only `lancamento_move_event`
- ✅ Trigger de soft-delete no D de origem? Se L é o ÚNICO Lancamento em D, mover L deixa D "órfão". D vira soft-deleted automaticamente? Ou fica "pendente"?

### ✅ Decisão
- **🅱️ MOVE preserva Lancamento; D de origem fica "pendente"** (Hiure, 2026-06-02) — sem Lancamentos ativos, mas NÃO soft-deletado. Usuário decide depois se quer fechar a chain, reatribuir D, ou deixar pendente.

### Implementação (event-sourced, alinhada com Codex critique 2026-06-03)

**Ação é append-only — o Lancamento NÃO é mutado.**

```
Tabela lancamento_move_event (append-only, sem updated_at/deleted_at):
  id
  lancamento_id     -- FK lancamento
  from_documento_id -- D origem
  to_documento_id   -- D destino
  reason            -- text, obrigatório (Q12=🅳️)
  moved_by          -- FK user
  moved_at          -- ISO8601 TEXT
  audit_log_id      -- FK audit_log; action='MOVE'

Tabela audit_log:
  operation_id  -- UUID; agrupa todos os moves de uma operação
  action = 'MOVE'
  payload_json  -- snapshot do estado pré-move
```

**Lógica:**
1. Usuário seleciona um ou mais Lancamentos e clica "Mover para outra cadeia"
2. UI mostra preview: "L [id] será movido de D [origem] para D' [destino]. L's já existem em D'? Mostra possíveis colisões." (Q12=🅳️)
3. Usuário confirma
4. Sistema: cria 1 row em `lancamento_move_event` por Lancamento movido
5. Sistema: cria 1 row em `audit_log` com `action='MOVE'`, `operation_id=UUID`, `payload_json` snapshot
6. **Lancamento NÃO é mutado.** PK e FKs originais (incluindo `documento_id`) ficam intactas.
7. UI consulta `lancamento_move_event` (via view abaixo) para mostrar L na chain de D'.
8. D de origem fica "pendente" se não tem mais L's ativos apontando pra ele

### View SQL: `v_lancamento_current_location` (T2)

Regra UI-only ("L aparece na chain de D' se existe move event mais recente com `to_documento_id = D'`, OU se L foi criado direto em D'") é frágil — vai gerar "lançamentos fantasma" em 2 anos (Codex critique 2026-06-03 #5). Solução: **view computada** que a UI consulta:

```sql
CREATE VIEW v_lancamento_current_location AS
SELECT
  l.id AS lancamento_id,
  COALESCE(
    (SELECT me.to_documento_id
     FROM lancamento_move_event me
     WHERE me.lancamento_id = l.id
     ORDER BY me.moved_at DESC, me.id DESC
     LIMIT 1),
    l.documento_id
  ) AS current_documento_id
FROM lancamento l
WHERE l.deleted_at IS NULL;
```

**Como a UI consome:**
- "Mostrar L na chain de D" → `JOIN lancamento l ON l.id = ? JOIN v_lancamento_current_location v ON v.lancamento_id = l.id WHERE v.current_documento_id = D`
- "Quais L's estão em D'?" → query acima
- "Histórico de moves do L" → `SELECT * FROM lancamento_move_event WHERE lancamento_id = L ORDER BY moved_at, id`

**D1/SQLite support:** `CREATE VIEW` totalmente suportado. Custo: index em `lancamento_move_event(lancamento_id, moved_at DESC, id DESC)` para performance (Drizzle adiciona via `CREATE INDEX` na migration T-101).

**Por que não coluna `current_documento_id` em `lancamento`?**
- Quebraria Q14=B (append-only) — coluna seria mutada em cada MOVE.
- Q8=🅰️ (restore simétrico) não conseguiria desfazer via SQL: precisaria salvar estado anterior.
- View é determinística, sempre bate com `lancamento_move_event`. Custo de cálculo é aceitável para queries de UI.

**Por que append-only (não mutação em `lancamento`)?**
- **Evidência:** hash/byte do Lancamento é estável através do tempo. MOVE é evento, não mutação.
- **Auditoria:** histórico completo de moves (um L pode ter sido movido múltiplas vezes).
- **Restore simétrico (Q8=🅰️):** undo de MOVE = insert de move event reverso.
- **Time-travel queries:** "onde o L estava em 2025-01-01?" = filtrar `lancamento_move_event` por `moved_at <= X`.

---

## Q15 — Delete de Documento compartilhado entre N Imóveis (surgiu do Codex 2026-06-03)

### 🤔 A pergunta
Q13 fez `Documento` ser compartilhável entre N Imóveis via junction `imovel_documento`. Q7a=🅱️ diz "soft-delete no menu" mas não distingue:
- **D está em 1 chain só** (I-exclusive) → soft-delete afeta 1 chain
- **D está em 3 chains** (shared entre I1, I2, I3) → soft-delete afeta 3 chains

O usuário talvez **não perceba** que está afetando outras 2 chains. A UI precisa deixar isso explícito.

### ⚖️ As opções

- **🅰️ "Desvincular desta cadeia" (default)** — soft-delete só da junction ativa
- **🅱️ "Apagar globalmente" (admin-only)** — soft-delete do D + TODAS as junctions
- **🅲️ Two-step: tenta desvincular primeiro** — UI mostra preview: "D está em 3 chains. Opções: (a) Desvincular desta chain, (b) Apagar globalmente (afeta 3 chains)"
- **🅳️ Igual C, mais "modo D órfão"** — se D fica sem junctions ativas, vira "órfão" automaticamente; UI oferece hard-delete admin-only

### ✅ Decisão
- **🅳️** (Hiure, 2026-06-03) — default = desvincular desta cadeia; admin-only = apagar globalmente; órfão = derivado de `NOT EXISTS active imovel_documento`.

### Implementação (Q15=🅳️)

**Três ações, três escopos:**

1. **"Desvincular desta cadeia" (default, qualquer usuário)**
   - Soft-delete **apenas** da row em `imovel_documento` (junction ativa)
   - `documento` continua existindo, intacto, em outras chains
   - `lancamento` continua existindo (Q7b=B preserva L)
   - **Constraint derivada:** `imovel_documento.is_documento_atual` per-par; soft-delete zera `is_documento_atual` se era 1
   - Partial UNIQUE adicional: `UNIQUE (imovel_id) WHERE is_documento_atual=1 AND deleted_at IS NULL` (T1) — garante no máximo 1 doc atual por Imóvel

2. **"Apagar globalmente" (admin-only)**
   - Soft-delete do `documento` + soft-delete de TODAS as `imovel_documento` onde ele aparece
   - `lancamento` preservado órfão (Q7b=B)
   - Admin vê o blast radius completo antes de confirmar (Q12=🅳️)
   - Audit log: `action=SOFT_DELETE, entity_type=documento, entity_id=X, payload_json={junctions_affected: [ids...]}`

3. **"D órfão" (estado derivado)**
   - **Não é coluna.** É uma view computada:
   ```sql
   CREATE VIEW v_documento_orfao AS
   SELECT d.id, d.tipo, d.numero, d.cri_id
   FROM documento d
   WHERE d.deleted_at IS NULL
     AND NOT EXISTS (
       SELECT 1 FROM imovel_documento id_
       WHERE id_.documento_id = d.id
         AND id_.deleted_at IS NULL
     );
   ```
   - UI lista `v_documento_orfao` e oferece: "Reatribuir a imóvel existente" (cria nova junction) | "Hard-delete (admin-only)" | "Deixar pendente"

**Por que estado derivado (não coluna):**
- Regra UI-only (Codex critique 2026-06-03 #5) é frágil — uma `is_orfao` flag desatualiza se o usuário reatribui
- View é determinística, sempre correta, custo = scan do índice `imovel_documento.documento_id`
- D1 (Cloudflare D1 suporta CREATE VIEW; SQLite full support)

### Diagrama de decisão (Q15=🅳️)

```
Usuário clica "Apagar" em Documento D
   │
   ├─ D está em 1 chain? ── SIM ──> "Tem certeza? D afeta 1 chain (I=X)"
   │                                 [Cancelar] [Apagar]
   │
   └─ D está em N chains? ── NÃO ──> "D está em N chains. Opções:"
                                     [Desvincular desta chain] (default, soft-delete junction)
                                     [Apagar globalmente] (admin-only, soft-delete D + N junctions)
                                     [Cancelar]
```

---

## Decisões

> ✅ **Seção preenchida em 2026-06-02/03** durante sessão de grupo com Luandro (decisor) e Hiure (implementador). Q15 ainda em aberto. As decisões destravam T-001 e liberam o início de T-100 (re-desenhar o ERD aplicando Q1–Q14) e T-101 (schema Drizzle).
>
> **Contexto crítico que ancorou várias decisões** (revelado por Hiure durante a sessão): o v2 é usado por um **grupo de pesquisadores investigando grilagem de terras**, não por cartório. Eles copiam dados do cartório pro sistema **exatamente como estão** (inclusive erros), porque **divergências entre certidões são indícios de grilagem**. Sistema = cópia fiel + camada de análise, NÃO uma base "limpa".

| # | Pergunta | Escolha | Justificativa |
|---|---|---|---|
| Q1 | Cascade em Imovel | **Opção C** (soft-delete + CASCADE admin-only) | Erros de digitação de imóvel são comuns no cartório; histórico precisa continuar auditável (quem lançou, quando, em qual documento). Soft-delete + CASCADE real só via admin resolve isso. |
| Q2 | Soft-delete vs hard-delete | **Opção B** (coluna `deleted_at` em todas as tabelas relevantes) | LGPD moot: v2 `Pessoa` só tem `nome`. Anonimização (C) não se aplica. Soft-delete (B) preserva divergências entre certidões como **evidência de grilagem** — corrigir "erro" não pode significar perder a string original. Hard-delete (A) vira ainda mais perigoso com esse contexto. |
| Q3 | Cardinalidade OrigemFimCadeia | **Opção B** (1:N — uma OrigemFimCadeia por origem, como Django) | **Essa é a informação mais importante e precisa ganhar destaque no grafo. A maioria das grilagens vai ser desvendada por ela** (Hiure, 2026-06-02). Cada origem com classificação independente permite ver o mapa granular de legitimidade de uma vez. Não é comum ter >1 origem por Lancamento, mas pode acontecer e precisa estar modelado. |
| Q4 | PII encryption at rest | **Opção A** (texto puro) | v2 `Pessoa` só tem `nome` (sem CPF/RG/email/telefone), e nome em cartório é público por definição. Usuários são grupo fechado de pesquisadores que precisam buscar/comparar nomes livremente. Criptografia quebraria a busca sem ganho de segurança real. Complexidade de KMS/chave mestra em D1/Cloudflare Workers é custo desproporcional. |
| Q5 | Validação CPF/CNPJ | **REMOVER** `cpf`/`rg`/`data_nascimento`/`email`/`telefone` de `Pessoa` no v2. Q5b vira N/A. | Coerente com Q2/Q4: v2 não é sistema de PII, é cópia fiel do cartório + análise. Pesquisadores não precisam do CPF dentro do sistema — quem precisa cruza com bases externas (Receita, processos judiciais). Sub-task explícita do T-300: "definir quais colunas descartar do legado no v2". |
| Q6 | React Flow: atual vs completo | **Opção A** (mostrar todos os fins de cadeia sempre) | Fins de cadeia são a evidência mais crítica pra detecção de grilagem (ancorada em Q3); precisam estar visíveis sempre. A complexidade visual de "cadeia gigante" (centenas de documentos) é resolvida por uma **camada de controles de visualização** (toggle de ramos, colapso de subárvore, filtros por classificação) que vale pra cadeia **inteira** — não só pra fins de cadeia. Essa camada vira **task T-104** (Phase 1.5 do roadmap). |
| Q7a | Menu delete | **🅱️** [Editar] [Mover] [Soft-delete] | "Mover" precisa ser botão distinto pra dar confiança ao usuário. Hard-delete é admin-only, fora do menu padrão. |
| Q7b | Cascade delete Imóvel | **🅱️** Cascade conservador: I + junctions, L's preservados | Lancamentos são evidência — devem sobreviver órfãos. Cascade em junctions `imovel_documento` apenas. |
| Q8 | Restore semantics | **🅰️** Simétrico ao Q7b=B | Intuitivo ("restaurar = desfazer"). Soft-delete foi conservador, nada de "lixo" pra restaurar. |
| Q9 | Trilha de análise | **🅲️** Histórico + provenance de criação | Crítico em equipe (autor original vs editor). |
| Q10 | Raw vs normalized | **🅰️** com exceção de `cartorio_nome` | Demais campos variáveis usam busca fuzzy FTS5. `cartorio_nome` vira entidade própria (tabela `cartorio`). |
| Q11b | Refinamento Q10 sobre `cri` | **Ver Q11b acima** | `cri` table (não genérico `cartorio`); `documento.cri_id` FK direto (sem junction); `UNIQUE (cri_id, tipo, numero)`; `cartorio_transmissao` é campo livre, não tabela; `imovel.cri_id` fixo (sem histórico v1). |
| Q12 | UX confirmation dialog | **🅳️** preview ANTES + dialog | "É importante perguntar se quer mesmo apagar ou se quer só editar" (Hiure, 2026-06-02). |
| Q13 | Chain membership | **🅱️** Junction `imovel_documento` (N:N) | "Pertence igualmente a diferentes imóveis" (Hiure, 2026-06-02). `is_documento_atual` per-par. |
| Q14 | MOVE cross-chain | **🅱️** MOVE preserva Lancamento, D origem "pendente" | Append-only `lancamento_move_event`; Lancamento não é mutado. |
| Q15 | Delete D compartilhado | **🅳️** Default = desvincular desta chain; admin-only = apagar global; órfão = view computada | "Órfão" como estado derivado (view `v_documento_orfao`) em vez de coluna — sempre correto, regra UI-only seria frágil. D1 suporta CREATE VIEW. |

### Decisões adicionais derivadas

> Estas não estavam nas 6 perguntas originais, mas emergiram naturalmente da discussão.

- **Nova task T-104 — Controles de visualização da cadeia** (toggle de ramos, colapso de subárvore, filtros por classificação, layouts de export PDF/XLSX/PNG). **Bloqueada em T-100 e T-101.** Justificativa: cadeias com centenas de documentos inviabilizam a visualização sem esses controles; precisa ser uma feature de UI/UX própria, não uma escolha binária escondida dentro da Q6. Detalhes no TASKS.md.
- **Sub-task do T-300 (legacy-fit)** — "Definir e descartar colunas PII do legado". Lista atual: `Pessoas.cpf`, `Pessoas.rg`, `Pessoas.data_nascimento`, `Pessoas.email`, `Pessoas.telefone`. Migrar do Postgres legado (que tem esses campos) pro Drizzle/D1 (que não terá) sem perda funcional.
- **T-105 (Soft-delete workflow)** — implementação do delete UX (Q7a/B, Q12=🅳️), restore (Q8=🅰️), MOVE (Q14=🅱️), delete de Documento shared (Q15 — bloqueada até decisão). **Bloqueada em T-100/T-101 E na decisão de Q15.**

**Notas finais para implementadores (T-100/T-101):**
- A tabela acima (linhas de Decisões) é a fonte de verdade. Use-a como referência canônica.
- Para o contexto crítico (pesquisadores de grilagem, cópia fiel) e a justificativa de cada escolha, ver `docs/db/erd-v2-legend.md` seção 6 e este doc (seções Q1–Q15).

---

## Apêndice: Convenções SQLite/D1 (Codex critique 2026-06-03 — T3 expandido)

Para o schema Drizzle/T-101, as seguintes convenções de tipos são obrigatórias:

| Conceito | Tipo errado | Tipo correto (SQLite/D1) |
|---|---|---|
| Boolean | `bool`, `boolean` | `INTEGER` (0/1) com `CHECK (col IN (0,1))` |
| Date | `date` | `TEXT` ISO8601 (`'2026-06-03'`) |
| Datetime | `datetime`, `timestamp` | `TEXT` ISO8601 (`'2026-06-03T14:30:00Z'`) |
| Money | `decimal`, `numeric`, `real` | `INTEGER` em **centavos** (evita rounding errors) |
| Area | `decimal`, `real` | `INTEGER` em **centiares** (1 are = 100 m²) ou `TEXT` decimal com escala fixa |
| Enum (ex: `tipo_cartorio`) | `enum` nativo Postgres | `TEXT` com `CHECK (col IN ('CRI','NOTAS','CIVIL','TRANSMISSAO','OUTRO'))` |
| UUID (operation_id) | n/a | `TEXT` (Drizzle gera UUID v4) |
| Encrypted blob | n/a | `BLOB` (AES-256-GCM) — **N/A no v2** (Q4=A + Q5=REMOVER PII de Pessoa; v2 não armazena PII) |
| Hash (cpf_hash) | n/a | `TEXT` (SHA-256 hex) — **N/A no v2** (sem PII para hashear) |

### `NOW()` / timestamps

SQLite/D1 **NÃO** tem `NOW()`. **A aplicação gera o timestamp no app layer** (Node `new Date().toISOString()`) e grava como `TEXT` ISO8601 UTC. Justificativa: testes determinísticos, reprodutibilidade de migrações, sem dependência de clock do servidor.

```ts
// Padrão na app
import { randomUUID } from 'crypto';
const now = new Date().toISOString(); // '2026-06-03T14:30:00.000Z'
const opId = randomUUID();            // 'f47ac10b-58cc-4372-a567-0e02b2c3d479'

db.insert(auditLog).values({
  operationId: opId,
  action: 'CREATE',
  createdAt: now,
  // ...
});
```

### FK actions explícitas (Drizzle → ON DELETE)

Toda FK precisa ter `onDelete` explícito. Defaults Drizzle = `NO ACTION` (= RESTRICT em SQLite), o que é raramente o que queremos:

| Relação | onDelete | Justificativa |
|---|---|---|
| `documento.cri_id` → `cri.id` | `RESTRICT` | Não pode apagar CRI com docs; admin tem hard-delete separado |
| `imovel.cri_id` → `cri.id` | `RESTRICT` | Mesmo |
| `origem.cri_id` → `cri.id` | `RESTRICT` | Mesmo |
| `lancamento.documento_id` → `documento.id` | `SET NULL` | Q7b=B: L preservado órfão se D sumir |
| `lancamento.tipo_id` → `lancamento_tipo.id` | `RESTRICT` | Não pode apagar tipo em uso; criar novo + migrate L se necessário |
| `lancamento_pessoa.lancamento_id` → `lancamento.id` | `CASCADE` | Junction de membership, segue o L |
| `lancamento_pessoa.pessoa_id` → `pessoa.id` | `SET NULL` | Q2=B: nome_verbatim preservado; LGPD pode apagar P |
| `imovel_documento.imovel_id` → `imovel.id` | `CASCADE` | Q7b=B: junction segue I |
| `imovel_documento.documento_id` → `documento.id` | `RESTRICT` | Q15=🅳️: apagar D é admin-only e intencional |
| `anotacao_versao.imovel_documento_id` → `imovel_documento.id` | `CASCADE` | Junction específica |
| `anotacao_versao.autor_original_id` → `user.id` | `RESTRICT` | F1: autor original é histórico, não pode virar NULL |
| `anotacao_versao.created_by_id` → `user.id` | `SET NULL` | Editor pode ser removido, anotação permanece |
| `anotacao_versao.operation_id` → `audit_log.id` | `SET NULL` | Audit log pode ser purgado (LGPD), anotação preservada |
| `lancamento_move_event.lancamento_id` → `lancamento.id` | `RESTRICT` | Q14=B: append-only; L é imutável |
| `lancamento_move_event.from_documento_id` → `documento.id` | `SET NULL` | D pode sumir, evento preservado |
| `lancamento_move_event.to_documento_id` → `documento.id` | `SET NULL` | Mesmo |
| `lancamento_move_event.moved_by_id` → `user.id` | `SET NULL` | Pesquisador removido, evento preservado |
| `lancamento_move_event.audit_log_id` → `audit_log.id` | `SET NULL` | Audit log pode ser purgado, evento preservado |
| `origem.documento_id` → `documento.id` | `SET NULL` | Origem órfã se D sumir; tipo=fim_cadeia tem NULL anyway |
| `user.deleted_at` | (no FK) | n/a |
| `audit_log.actor_id` → `user.id` | `SET NULL` | LGPD: pesquisador pode pedir remoção, log preservado |
| `audit_log.deleted_at` | (no FK) | n/a |
| `tis_imovel.*` | `CASCADE` | Junction simples |
| `tis.terra_referencia_id` → `terra_indigena_referencia.id` | `RESTRICT` | Referência oficial não pode sumir com TIs em uso |

**Invariante Q14 (write-time, no app antes de INSERT):**
```ts
// Antes de criar um lancamento_move_event, validar:
const current = await db.query.v_lancamento_current_location.findFirst({
  where: eq(v_lancamento_current_location.lancamento_id, payload.lancamento_id),
});
if (current && current.documento_id !== payload.from_documento_id) {
  throw new Error(
    `Q14 violation: L ${payload.lancamento_id} is currently in D ${current.documento_id}, ` +
    `but move event says from D ${payload.from_documento_id}`
  );
}
```
**Alternativa (mais barata):** `CHECK (from_documento_id IS NOT NULL)` na migration + validação de `current_location` no app para impedir double-MOVE.

**No Drizzle:**
```ts
criRelations: {
  documento: many('documento', { relationName: 'documento_cri' })
},
// table definitions:
// documento.cri_id: integer('cri_id').references(() => cri.id, { onDelete: 'restrict' })
```

### FTS5 — sync via triggers

SQLite/D1 suporta FTS5 oficial. Para cada tabela com campos full-text, criar:
1. Tabela virtual `*_fts` (FTS5 content table)
2. Triggers `INSERT/UPDATE/DELETE` para manter `*_fts` em sync com a tabela base

```sql
-- Pessoa FTS
CREATE VIRTUAL TABLE pessoa_fts USING fts5(
  nome,
  content='pessoa',
  content_rowid='id'
);

CREATE TRIGGER pessoa_ai AFTER INSERT ON pessoa BEGIN
  INSERT INTO pessoa_fts(rowid, nome) VALUES (new.id, new.nome);
END;
CREATE TRIGGER pessoa_ad AFTER DELETE ON pessoa BEGIN
  INSERT INTO pessoa_fts(pessoa_fts, rowid, nome) VALUES('delete', old.id, old.nome);
END;
CREATE TRIGGER pessoa_au AFTER UPDATE ON pessoa BEGIN
  INSERT INTO pessoa_fts(pessoa_fts, rowid, nome) VALUES('delete', old.id, old.nome);
  INSERT INTO pessoa_fts(rowid, nome) VALUES (new.id, new.nome);
END;

-- Busca
SELECT p.* FROM pessoa p
JOIN pessoa_fts fts ON fts.rowid = p.id
WHERE pessoa_fts MATCH 'joao silva*'
  AND p.deleted_at IS NULL
ORDER BY rank;
```

**Drizzle:** a tabela virtual FTS5 e os triggers vão via `sql.raw` na migration (Drizzle não tem DSL nativo pra FTS5). Helper: `scripts/db/fts5-helper.ts` (a criar em T-101) que gera SQL parametrizado pelo schema.

**Aplicar a:**
- `pessoa.nome` (Q4=A, sem criptografia)
- `documento.outorgante_nome`, `outorgado_nome`, `endereco`
- `cri.nome`
- `lancamento.descricao`, `observacoes`
- `anotacao_versao.texto`

**Soft-delete + FTS5:** triggers usam `AFTER` (não `BEFORE`), então soft-delete (UPDATE `deleted_at`) **NÃO** remove do FTS5. A query de busca precisa filtrar `WHERE p.deleted_at IS NULL` (já mostrado acima). Trade-off: linhas soft-deletadas continuam no índice FTS, mas a query filtra. **Tamanho do índice cresce** com soft-deletes → rotina de vacuum (T-101).

### Partial UNIQUE indexes

`CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL` em junctions. Aplicar em T-101 via Drizzle `sql.raw`:

```sql
-- Q13: 1 row por (I, D) ativo
CREATE UNIQUE INDEX uq_imovel_documento_pair
  ON imovel_documento(imovel_id, documento_id)
  WHERE deleted_at IS NULL;

-- Q15=🅳️: no máximo 1 D atual por Imóvel
CREATE UNIQUE INDEX uq_imovel_documento_atual
  ON imovel_documento(imovel_id)
  WHERE is_documento_atual = 1 AND deleted_at IS NULL;

-- T1+D1: UNIQUE no cri por CNS ativo
CREATE UNIQUE INDEX uq_cri_cns
  ON cri(cns_codigo)
  WHERE cns_codigo IS NOT NULL AND deleted_at IS NULL;

-- Q3: 1 OrigemFimCadeia por origem
CREATE UNIQUE INDEX uq_origem_fim_cadeia_origem
  ON origem_fim_cadeia(origem_id)
  WHERE origem_id IS NOT NULL;
```

Drizzle não tem DSL pra `WHERE` em `uniqueIndex` ainda (issue #2456); workaround: `sql.raw` no migration ou Drizzle `index().where()`. Verificar na implementação T-101 qual a melhor forma.

### Datas parciais (cartório tem data incompleta)

Cartórios frequentemente registram data incompleta ("15/06/1950" sem hora, ou "junho/1950" sem dia). Schema v2 aceita esses formatos como `TEXT`:

| Formato cartório | Como gravar | Validação |
|---|---|---|
| `'1950-06-15'` | ISO8601 date completo | `regex /^\d{4}-\d{2}-\d{2}$/` |
| `'1950-06'` | ISO8601 year-month (parcial) | `regex /^\d{4}-\d{2}$/` (UI mostra "junho/1950") |
| `'1950'` | Só ano (parcial) | `regex /^\d{4}$/` (UI mostra "1950") |
| `'1950-06-15T14:30:00Z'` | ISO8601 datetime UTC | `regex /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/` |

**Validação:** no app layer (Zod ou similar). DB aceita qualquer `TEXT` (não vale a pena CHECK constraint regex em SQLite — performance ruim, e regex no SQLite tem sintaxe limitada).

**Sort:** SQLite ordena `TEXT` lexicograficamente, que **coincide** com ordenação cronológica para ISO8601. `"1950-06"` < `"1950-06-15"` < `"1950-07-01"`. Sem conversão pra DATE/JULIAN.

**Comparações entre formatos:** `"1950-06-15" > "1950-06"` é correto. `"1950-06" = "1950-06"` é correto. Mas `"1950-06-15" = "1950-06-15T00:00:00Z"` é **FALSO** (string diferente). UI normaliza pra comparação (ex: trim do T-... quando ambos são pure-date).

### CHECK constraints

Aplicar via migration Drizzle em todos os enums:

- `cri.tipo_cartorio` → `CHECK (tipo_cartorio IN ('CRI','NOTAS','CIVIL','TRANSMISSAO','OUTRO'))`
- `lancamento_tipo.tipo` → `CHECK (tipo IN ('inicio_matricula','registro','averbacao'))`
- `documento.tipo` → `CHECK (tipo IN ('matricula','transcricao'))`
- `origem.tipo` → `CHECK (tipo IN ('matricula','transcricao','fim_cadeia'))`
- `lancamento_pessoa.papel` → `CHECK (papel IN ('transmitente','adquirente','outorgante','outorgado','anuente','testemunha'))`
- `audit_log.action` → `CHECK (action IN ('CREATE','EDIT','SOFT_DELETE','RESTORE','MOVE','ANNOTATE','EXPORT'))`
- `imovel.arquivado` → `CHECK (arquivado IN (0,1))`
- `imovel_documento.is_documento_atual` → `CHECK (is_documento_atual IN (0,1))`
- `anotacao_versao.is_current` → `CHECK (is_current IN (0,1))`
- `user.deleted_at IS NULL OR deleted_at GLOB '[0-9]*'` (data válida)

> **Nota sobre Mermaid ERD (T4):** o .mmd (`erd-v2.mmd`) é **documentação visual**, NÃO schema canônico. Tipos `text` no Mermaid correspondem a `TEXT` no D1, mas a versão executável é a Drizzle migration (T-101). `UNIQUE_NOTE` é só annotation visual — partial UNIQUE indexes (`WHERE deleted_at IS NULL`), CHECK constraints, FTS5 sync triggers, e views (`v_lancamento_current_location`, `v_documento_orfao`) NÃO aparecem no .mmd; aplicar via migration Drizzle + SQL DDL. **Mermaid interpreta `--` e `|` em comentários como relações**, então CHECK constraints detalhados vão no .md, não no .mmd.

---

## Próximos passos

1. ✅ Decisões Q1–Q15 preenchidas (incluindo Q15=🅳️ decidida por @Hiure 2026-06-03).
2. ✅ Crítica Codex 2026-06-03 round 2 processada: **4 decisões D1–D4** + **4 fixes técnicos T1–T4** aplicadas no ERD e na apêndice SQLite/D1.
3. As decisões são commitadas neste arquivo (em um PR de docs).
4. O PR é mergeado na `v2`.
5. T-001 do `docs/TASKS.md` é marcado como concluído.
6. T-100, T-101, T-104 podem ser iniciadas (não bloqueadas).
7. T-105 pode ser iniciada (Q15=🅳️ destravou).

---

## Crítica Codex 2026-06-03 (gpt-5.5, high) — RESOLVIDA 2026-06-03

> Ver `docs/db/CODEX_CRITIQUE_2026-06-03.md` para o relatório completo. **Verdict: NEEDS REWORK, medium severity.** Direção conceitual correta, blockers eram nível-implementação.
>
> **Status 2026-06-03 (round 2, todas resolvidas):**

### Decisões aplicadas (Codex #1-#3, #6)

| # | Achado | Decisão | Status |
|---|---|---|---|
| **D1** | `cri` precisa de UNIQUE ativo (cns_codigo) | `UNIQUE (cns_codigo) WHERE cns_codigo IS NOT NULL AND deleted_at IS NULL` (partial UNIQUE) | ✅ Aplicado |
| **D2** | `origem` precisa de `numero_raw` | Adicionado `text numero_raw` à `origem` (verbatim) | ✅ Aplicado |
| **D3** | Separar `user` (pesquisador) de `pessoa` (cartório) | `user` table criada; `lancamento_move_event.moved_by_id`, `audit_log.actor_id`, `anotacao_versao.created_by_id` migram de `pessoa_id` → `user_id`. `pessoa` continua domínio cartório. **`anotacao_versao.autor_original_id` corrigido para `user_id` no round 2 (F1, Codex bloqueante): Q9 fala de "pesquisador criando anotação", não cartório.** | ✅ Aplicado (corrigido F1) |
| **D4** | Q15 recomendação: D | Q15=🅳️ decidido por @Hiure; default = desvincular, admin-only = apagar global, órfão = view `v_documento_orfao` | ✅ Aplicado |

### Fixes técnicos aplicados (Codex #4, #5, #7, #8)

| # | Achado | Fix | Status |
|---|---|---|---|
| **T1** | Faltam partial UNIQUE constraints em `imovel_documento` | `UNIQUE (imovel_id, documento_id) WHERE deleted_at IS NULL` + `UNIQUE (imovel_id) WHERE is_documento_atual=1 AND deleted_at IS NULL` (Q15=🅳️: garante no máximo 1 doc atual por Imóvel) | ✅ Documentado no .mmd, Drizzle vai aplicar |
| **T2** | Q14 append-only MOVE precisa de SQL view determinística | `v_lancamento_current_location` (coroutine via `lancamento_move_event ORDER BY moved_at, id DESC LIMIT 1`); documentado em Q14 | ✅ Documentado em Q14 + view SQL inline |
| **T3** | Apêndice SQLite/D1 incompleto | Expandido com: FTS5 sync (triggers INSERT/UPDATE/DELETE), FK actions explícitas (RESTRICT/SET NULL/CASCADE), sem `NOW()` PG (UTC ISO8601 no app), datas parciais do cartório (`text` com validação leve de formato) | ✅ Apêndice expandido |
| **T4** | Mermaid `UNIQUE_NOTE` é só visual, não enforce | Nota explícita no topo do .mmd: "Mermaid NÃO é schema. UNIQUE_NOTE é só documentação visual. Drizzle migration é canônica" | ✅ Nota no topo do .mmd |

### Tabelas adicionais (Codex #5 - estado derivado)

| View | Propósito | Substitui |
|---|---|---|
| `v_lancamento_current_location` | "Onde o L está AGORA?" (Q14) | Regra UI-only frágil que geraria lançamentos fantasma |
| `v_documento_orfao` | "Quais D's não estão em nenhuma chain ativa?" (Q15=🅳️) | Flag `is_orfao` desatualizaria em reatribuição |

Ambas views são D1-compatíveis (CREATE VIEW suportado em SQLite). Implementação em Drizzle migration T-101.

---

## Crítica Codex 2026-06-03 Round 2 (gpt-5.5, xhigh) — RESOLVIDA 2026-06-03

> Ver `docs/db/CODEX_CRITIQUE_2026-06-03_ROUND2.md` para o relatório completo. **Verdict: NEEDS-MINOR-FIXES.** 2 BLOCKERS (F1, F2), 1 NICE-TO-HAVE (F3), 4 inconsistências textuais.

### Achados round 2 resolvidos

| # | Achado | Fix | Status |
|---|---|---|---|
| **F1** | `anotacao_versao.autor_original_id` apontava para `pessoa` (cartório), contradizendo Q9 (researcher attribution) | Mudado para `user_id` (pesquisador); visual edge `pessoa ||--o{ imovel_documento : "anotou"` corrigida para `user \|\|--o{ anotacao_versao : "autor_original"` (a edge original estava geometricamente errada — FK mora em `anotacao_versao`, não em `imovel_documento`) | ✅ Aplicado |
| **F2** | `anotacao_versao` é soft-deletable (legend) mas faltava `deleted_at` | Adicionado `text deleted_at`; documentada a diferença: `deleted_at` = apaga anotação INTEIRA (todas versões); `is_current=0` = marca versão como não-atual mas mantém no histórico | ✅ Aplicado |
| **F3** | T3 FK actions incompleta + faltava `lancamento_tipo \|\|--o{ lancamento` visual | 6 FKs adicionadas (`lancamento.tipo_id`, `anotacao_versao.autor_original_id`/`created_by_id`/`operation_id`, `lancamento_move_event.moved_by_id`/`audit_log_id`, `origem.documento_id`, `tis.terra_referencia_id`); edge `lancamento_tipo \|\|--o{ lancamento : "classifica"` adicionada | ✅ Aplicado |
| **F4** | Q2 seção ainda recomendava C; tabela de Decisões diz B | Seção de Q2 atualizada para refletir a decisão final (B) com justificativa do contexto v2 (pesquisadores de grilagem) | ✅ Aplicado |
| **F5** | Q1 intro dizia "6 perguntas (Q1 a Q6)" | Atualizado para "15 perguntas (Q1–Q15, mais Q11b)" | ✅ Aplicado |
| **F6** | Q11b "schema final" snippet ainda mostrava `documento.imovel_id` e `documento.is_documento_atual` (removidos em Q13) | Snippet atualizado com comentários `// (Q13) REMOVIDO em v2` | ✅ Aplicado |
| **F7** | Q14 invariante write-time faltando | Documentada invariante (validar `from_documento_id` = `v_lancamento_current_location` antes de INSERT) com snippet TS | ✅ Documentado |

**Perguntas ou discordâncias?** Abra um issue ou comente direto neste PR.
