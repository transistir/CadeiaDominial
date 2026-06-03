# Decisões Pendentes do Schema v2

> **Quem deve ler isso:** Luandro (decisor final), Hiure (implementador), e qualquer pessoa que queira entender por que o schema v2 está do jeito que está. Este documento é em português para ser acessível a pessoas não-desenvolvedoras, mas mantém a precisão técnica.
>
> **Por que este documento existe:** A revisão cega do schema v2 (em `docs/SCHEMA_V2_BLINDSPOT_REVIEW.md`) encontrou 27 pontos cegos. Dez deles não podem ser resolvidos sem uma decisão humana. São as 6 perguntas abaixo (Q1 a Q6). **Nenhuma linha de código do schema novo pode ser escrita enquanto essas 6 perguntas não forem respondidas.**

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
**Opção C (soft-delete + anonimização LGPD)** — é a única que atende simultaneamente a auditoria jurídica **e** a LGPD sem comprometer a navegação do grafo. A maioria dos sistemas brasileiros de cartório está indo por esse caminho.

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

## Decisões

> ✅ **Seção preenchida em 2026-06-02** durante sessão de grupo com Luandro (decisor) e Hiure (implementador). As decisões destravam T-001 e liberam o início de T-100 (re-desenhar o ERD aplicando Q1–Q6) e T-101 (schema Drizzle).
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

### Decisões adicionais derivadas das Q1–Q6

> Estas não estavam nas 6 perguntas originais, mas emergiram naturalmente da discussão.

- **Nova task T-104 — Controles de visualização da cadeia** (toggle de ramos, colapso de subárvore, filtros por classificação, layouts de export PDF/XLSX/PNG). **Bloqueada em T-100 e T-101.** Justificativa: cadeias com centenas de documentos inviabilizam a visualização sem esses controles; precisa ser uma feature de UI/UX própria, não uma escolha binária escondida dentro da Q6. Detalhes no TASKS.md.
- **Sub-task do T-300 (legacy-fit)** — "Definir e descartar colunas PII do legado". Lista atual: `Pessoas.cpf`, `Pessoas.rg`, `Pessoas.data_nascimento`, `Pessoas.email`, `Pessoas.telefone`. Migrar do Postgres legado (que tem esses campos) pro Drizzle/D1 (que não terá) sem perda funcional.

**Notas finais para implementadores (T-100/T-101):**

- A tabela acima (linhas 502–509) é a fonte de verdade das decisões. O "formato sugerido" original (linhas 518–527 antes deste patch) listava respostas alternativas que **contradiziam** as decisões tomadas e foi removido. Use a tabela de Decisões como referência canônica.
- Para o contexto crítico (pesquisadores de grilagem, cópia fiel) e a justificativa de cada escolha, ver `docs/db/erd-v2-legend.md` seção 6 e este doc linhas 502-509.

---

## Open questions (Q7–Q12) — bloqueiam T-105, não bloqueiam T-100/T-101

> Estas perguntas surgiram da revisão do Codex + da observação do Hiure sobre **cross-chain delete behavior**. Não estavam nas Q1-Q6 originais. São decisões de **camada de aplicação** (workflow + UX), não de schema — T-100/T-101 podem começar sem elas, mas T-105 (soft-delete workflow) fica bloqueado até serem respondidas.

### Q7 — Cross-chain delete behavior (um Documento pode ser `is_documento_atual=true` para N Imóveis E `origem.documento_id` para M outros Lancamentos)

**Q7a** — Quando o usuário clica "remover" num Lancamento/Documento, qual o menu de opções na UI?
- **Resposta (Hiure, 2026-06-02): 🅱️ Menu: [Editar] [Mover] [Soft-delete]** — sem hard-delete na UI principal (admin usa rota separada). "Mover" precisa ser um botão distinto pra dar confiança ao usuário de que o trabalho não vai ser perdido. Hard-delete é admin-only, fora do menu padrão.
- A) Cascade só nos descendentes "privados" de I; Documentos compartilhados ficam visíveis com badge nas outras chains.

**Q7c (UX)** — Confirmação obrigatória antes de delete mostrando blast radius (N+M chains afetadas, M' Lancamentos), com botão padrão "Editar ao invés de apagar".

**Respostas parciais:**
- **Q7a = 🅱️ (Hiure, 2026-06-02)** — Menu: [Editar] [Mover] [Soft-delete]. Sem hard-delete na UI principal.
- **Q7b = 🅱️ (Hiure, 2026-06-02)** — Cascade conservador: só I + junctions soft-deletadas. L's todos preservados. D's I-exclusivos ficam "sem chain" e L's neles ficam "pendentes".

### Q8 — Restore semantics

Dada Q7b=🅱️ (soft-delete conservador: só I + junctions, L's preservados), o restore é simétrico por default. Mas vale a pena formalizar pra cobrir edge cases.

🅰️ **Restore simétrico (recomendação)** — undo exato do Q7b=B: `I.deleted_at = NULL` + restaurar as junctions (I, D) que foram soft-deletadas. L's já estavam preservados (nunca foram soft-deletados), então nada a fazer neles. D's I-exclusivos voltam a ter chain ativa via I; D's shared voltam a ter I na lista de chains.

🅱️ **Restore cascata reverso** — restore I + cascade restore em junctions + cascade restore em L's que tinham D I-exclusivos. (Não se aplica com Q7b=B, mas seria o simétrico do Q7b=B+.)

🅲️ **Restore minimal** — só I.deleted_at = NULL. Junctions ficam "pendentes" (não voltam). Usuário decide manualmente re-ativar cada junction. Mais trabalho pro usuário, mas mais seguro se o motivo do delete original era "I está errado".

🅳️ **Restore com revisão de pares** — antes de restaurar, mostra todas as junctions + L's que serão afetados. Usuário confirma cada um individualmente.

**Recomendação: 🅰️** — simétrico ao Q7b=B, intuitivo ("restaurar = desfazer"), e o soft-delete foi conservador (L's preservados), então não há "lixo" pra restaurar.

**DECIDIDO: 🅰️** (Hiure, 2026-06-03).

### Q9 — Trilha de análise do pesquisador (researcher attribution)

**Contexto correto (Hiure, 2026-06-03):** o sistema é usado por **pesquisadores de grilagem** que ingerem dados públicos de cartórios (read-only — não deletam, não editam certidões) e adicionam suas **próprias anotações analíticas** em cima. Não há "admin do cartório" dando hard-purge; há **pesquisador A** editando uma anotação feita por **pesquisador B**.

A pergunta real de auditoria é: **quando um pesquisador cria/edita/remove uma anotação analítica própria** (ex: "este Lancamento parece falsificado", "esta cadeia é suspeita"), o sistema deve rastrear **quem, quando, e qual era o conteúdo antes**?

🅰️ **Sem trilha** — última versão ganha. Simples, mas se Hiure publica um relatório dizendo "esta cadeia é grilada" e depois edita a anotação pra "na verdade é ok", não tem como provar o que foi dito originalmente. *(Perigoso em contexto jurídico.)*

🅱️ **Histórico de versões por anotação** — cada vez que o pesquisador edita, salva uma versão. UI mostra "v3 (atual) | v2 | v1". Restauração é trivial.

🅲️ **Histórico + provenance de criação** — igual a B, mas registra também **quem criou originalmente** (importante em equipe: Hiure cria, estagiário X edita, e depois o relatório precisa creditar a Hiure como autor original).

🅳️ **Tudo de C + exportação logada** — cada export (PDF, CSV, JSON) registra **o quê foi exportado, por quem, quando, e pra onde (download local vs share link)**. Chain-of-custody completa.

**DECIDIDO: 🅲️** (Hiure, 2026-06-03).

### Q13 — Operação MOVE/REASSIGN cross-chain (NOVA — surgiu do insight do Hiure)

> *"Ela não pode perder esses lançamentos. Eles precisam ser atrelados a outra cadeia dominial. Só enviar ele para outra cadeia dominial de outro imóvel."* (Hiure, 2026-06-02)

O sistema precisa de uma operação MOVE que:

- ✅ **Preserva o Lancamento byte-for-byte** (igualdade no MOVE = preservação de evidência)
- ✅ **Torna o Lancamento visível na chain do Documento de destino** (D'), sem mutar o L
- ✅ **É auditável** — registra o evento de move no log + na tabela append-only `lancamento_move_event`
- ✅ **Trigger de soft-delete no D de origem?** Se L é o ÚNICO Lancamento em D, mover L deixa D "órfão" (sem Lancamentos atuais). D vira soft-deleted automaticamente? Ou fica "pendente"?

- **Resposta (Hiure, 2026-06-02): 🅱️ MOVE preserva Lancamento; D de origem fica "pendente"** (sem Lancamentos ativos, mas NÃO soft-deletado) — usuário decide depois se quer fechar a chain, reatribuir D, ou deixar pendente pra futura análise.

**Implementação (event-sourced, alinhada com Codex critique 2026-06-03):**

**Ação é append-only — o Lancamento NÃO é mutado.**

```
Tabela lancamento_move_event (append-only, sem updated_at/deleted_at):
  id
  lancamento_id     -- FK lancamento
  from_documento_id -- D origem
  to_documento_id   -- D destino
  reason            -- text, obrigatório (Q12=🅓️)
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
2. UI mostra preview: "L [id] será movido de D [origem] para D' [destino]. L's já existem em D'? Mostra possíveis colisões." (Q12=🅓️)
3. Usuário confirma
4. Sistema: cria 1 row em `lancamento_move_event` por Lancamento movido
5. Sistema: cria 1 row em `audit_log` com `action='MOVE'`, `operation_id=UUID`, `payload_json` snapshot
6. **Lancamento NÃO é mutado.** Sua PK e FKs originais (incluindo `documento_id`) ficam intactas.
7. UI consulta `lancamento_move_event` para mostrar o L na chain de D' (regra de visualização: "L aparece na chain de D' se existe um move event com `to_documento_id = D'` mais recente que qualquer move event com `from_documento_id = D'`, OU se L foi criado direto em D' e nunca foi movido.")
8. D de origem fica "pendente" se não tem mais L's ativos apontando pra ele

**Por que append-only (não mutação em `lancamento`)?**

- **Evidência:** hash/byte do Lancamento é estável através do tempo. MOVE é um evento, não uma mutação do estado.
- **Auditoria:** histórico completo de moves (um L pode ter sido movido múltiplas vezes).
- **Restore simétrico (Q8=🅰️):** undo de MOVE = insert de move event reverso, não mutação.
- **Time-travel queries:** "onde o L estava em 2025-01-01?" = filtrar `lancamento_move_event` por `moved_at <= X`.

**Trigger automático (Hiure = 🅱️ D órfão):** se após o MOVE, D de origem fica sem L's ativos, D NÃO é auto-soft-deletado. Fica "pendente" — UI flag. Decisão posterior: fechar chain, reatribuir, ou deixar pendente.

---

### Q14 — Modelagem de "chain membership" (CRITICAL — v1 tinha bug estrutural)

> *"Não é para ser prioritário de nenhuma cadeia dominial esse histórico. Ele pertence igualmente a diferentes imóveis."* (Hiure, 2026-06-02)

**Contexto:** v1 (e v2 herdado) tinha `imovel ||--o{ documento : possui`, o que codificava "este Imóvel é o dono do Documento". Isso é **errado** — a cadeia histórica é **igualmente pertencente** a todos os Imóveis que a citam (matrícula compartilhada entre grileiros disputando, por exemplo).

- **Resposta (Hiure, 2026-06-02): 🅱️ Junction table `imovel_documento` (N:N completo)** — Documento perde `imovel_id` direto; chain membership fica explícita via junction. `is_documento_atual` vira per-par (não global). "Compartilhado" deixa de ser conceito especial — é o caso default.

**Schema resultante:**

```mermaid
imovel ||--o{ imovel_documento : ""
documento ||--o{ imovel_documento : ""
imovel_documento {
  int id PK
  int imovel_id FK
  int documento_id FK
  int is_documento_atual "0/1 INTEGER, per (Imovel, Documento) pair"
  int delete_operation_id "FK audit_log (Q8=A)"
  text created_at "ISO8601 TEXT"
  text deleted_at "soft-delete per chain membership"
}
documento {
  int id PK
  text numero
  text numero_raw
  text tipo
  text created_at "ISO8601 TEXT"
  text deleted_at "soft-delete"
  int delete_operation_id "FK audit_log"
  // imovel_id REMOVIDO (vai pra junction)
  // is_documento_atual REMOVIDO (vai pra junction, per-par)
}
```

**Como Q14=🅱️ simplifica Q7/Q7b/Q13:**

- **Q7a (delete Documento):** Documento some + cascade nas junctions. Sem "primário" pra preservar — todos iguais. Ver Q15 (delete de Documento shared — precisa decisão do Hiure).
- **Q7b (delete Imóvel):** Imóvel some + cascade **APENAS** nas junctions `imovel_documento` dele. **Documentos não são afetados** (eles podem estar em outras junctions). L's e `lancamento_pessoa` são preservados (evidência). Ver Q7b no final deste doc para a lógica completa.
- **Q13 (MOVE Lancamento):** MOVE é **append-only** em `lancamento_move_event` (Lancamento NÃO é mutado, `lancamento.documento_id` original permanece intacto). Cross-chain visibility vem de graça porque o UI consulta `lancamento_move_event` para mostrar L na chain de D'. Ver Q13 acima para a especificação event-sourced completa.

> **⚠️ Esta seção foi corrigida em 2026-06-03** (Codex critique): a versão anterior deste summary ainda dizia "MOVE muda `lancamento.documento_id` (FK simples)", o que **contradiz** a nova implementação event-sourced de Q13. Corrigido: agora o summary referencia a Q13 corrigida.

**Implicações em T-100 / T-101:**
- T-100 (re-draw ERD): adicionar `imovel_documento` ao ERD; remover `imovel_id` e `is_documento_atual` de `documento`
- T-101 (Drizzle schema): criar a tabela junction; ajustar FKs
- T-300 (legacy-fit): o legacy Django tinha `documento.imovel_id` (1:N); precisa popular a junction `imovel_documento` na migração

---

### Q7b (com Q14=🅱️) — Cascade ao soft-deletar um **Imóvel I**

**Conceito-chave (Hiure 2026-06-02):** A cadeia é construída **do Imóvel atual pro passado histórico** via Lancamentos. O cadastro do Imóvel atual inicia a jornada; cada Lancamento adiciona uma relação com um Documento passado; origens apontam pra Documentos ainda mais antigos. **Documentos são formados pelos Lancamentos** (do início da matrícula ao fim).

**Consequência:** um Documento D pode estar em chains de N Imóveis simultaneamente (compartilhar a história é o caso default). Quando deletar I, "deletar a história de I" significa deletar APENAS o sub-grafo que é exclusivo de I — não o que é co-pertencente a outros.

**DECIDIDO: 🅱️** (Hiure, 2026-06-03) — **Cascade conservador**: `I.deleted_at = NOW()` + soft-delete **SOMENTE** nas junctions `imovel_documento` daquele I. **L's e `lancamento_pessoa` NÃO são tocados** (Lancamentos são evidência — preservados mesmo órfãos).

> **⚠️ Clarificação crítica (Codex critique 2026-06-03):** o "Algoritmo proposto" anterior deste Q7b continha uma frase conflitante — "cascade soft-delete nos Lancamentos L onde L.documento_id = D" (D I-exclusivo). **Isso era o algoritmo da opção B+ (não escolhida).** A decisão final é 🅱️: **L's são preservados** (não tocados no cascade). Esta ambiguidade foi removida na versão 2026-06-03 do doc.
>
> **⚠️ 2ª clarificação (Codex critique 2026-06-03):** a versão anterior deste Q7b também soft-deletava `lancamento_pessoa` (junction L↔Pessoa) no passo 3. **ERRADO**: `nome_verbatim` é evidência da occurrence e deve sobreviver. **Versão correta:** cascade toca APENAS `imovel_documento`. L's preservados + lancamento_pessoa preservados. O que pode mudar é o `lancamento_pessoa.pessoa_id` (vira NULL se a pessoa foi anonimizada por LGPD) — mas a ROW e o `nome_verbatim` permanecem.

**Lógica correta do cascade Q7b=B (versão 2026-06-03, final):**

1. Soft-delete I (`imovel.deleted_at = NOW()`, `delete_operation_id = <audit_log_id>`)
2. Para cada junction (I, D) ativa em `imovel_documento`: soft-delete a junction (`deleted_at = NOW()`, `delete_operation_id = <audit_log_id>`)
3. **L's em si NÃO são soft-deletados** — eles continuam no banco. O `documento_id` do L não é mutado.
4. **Junction `lancamento_pessoa` NÃO é soft-deletada** — `nome_verbatim` é evidência, preservada. O `pessoa_id` pode virar NULL se a pessoa for anonimizada (LGPD), mas a ROW persiste.
5. **D's I-exclusivos** ficam sem chain (todas junctions que os ligavam foram soft-deletadas). D ainda existe, fica "pendente" — UI mostra como "Documento órfão" pra MOVE posterior.
6. **D's shared** preservam seus L's (as outras chains mantêm access via suas junctions ainda ativas).
7. **Cartórios NÃO são tocados** no cascade de I (eles podem emitir D's de outros I's).
8. **Pessoas NÃO são tocadas** no cascade de I (LGPD: anonimização é por requisição individual, não em cascata).

---

### Q15 — Delete de Documento compartilhado entre N Imóveis (NOVA — surgiu da critique do Codex em 2026-06-03)

**Contexto:** Q14 fez `Documento` ser compartilhável entre N Imóveis via junction `imovel_documento`. Q7a=🅱️ diz "soft-delete no menu" mas não distingue entre:

- **D está em 1 chain só** (I-exclusive) → soft-delete do D afeta 1 chain
- **D está em 3 chains** (shared entre I1, I2, I3) → soft-delete do D afeta 3 chains simultaneamente

O usuário que clica "Apagar" no D talvez **não perceba** que está afetando outras 2 chains. A UI precisa deixar isso explícito.

🅰️ **"Desvincular desta cadeia" (default)** — soft-delete só da junction `imovel_documento` ativa. D continua existindo nas outras chains. Operacional: usuário vê D como "removido da chain atual" mas pode re-vincular depois.

🅱️ **"Apagar globalmente" (admin-only)** — soft-delete do D + cascade em TODAS as junctions. Operacional: D some de TODAS as chains. Para D errado em todas as chains (ex: cadastro duplicado em todos os cartórios).

🅲️ **Two-step: tenta desvincular primeiro** — UI mostra preview: "D está em 3 chains. Opções: (a) Desvincular desta chain, (b) Apagar globalmente (afeta 3 chains)". Se usuário escolhe (b), abre dialog de confirmação com blast radius completo.

🅳️ **Igual C, mais "modo D órfão"** — se D fica sem junctions ativas (todos desvincularam), D vira "órfão" automaticamente. UI mostra como "Documento órfão — sem chain ativa" e oferece hard-delete admin-only.

@Hiure: A, B, C ou D?

> *Implementação de qualquer uma das opções está em T-105 (UX workflow). A escolha aqui determina o wording dos botões e o flow da UI.*

---

### Apêndice: Convenções SQLite/D1 (Codex critique 2026-06-03)

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
| Hash (cpf_hash) | n/a | `TEXT` (SHA-256 hex) — **N/A no v2** (sem PII para hashear; `pessoa.nome` uniqueness via FTS5 ou normalizado) |

**FTS5 (D1 suporta oficial):** tabela virtual `*_fts` para busca full-text BM25. Aplicar a:
- `pessoa.nome` (texto puro, sem criptografia — Q4=A)
- `documento.outorgante_nome`, `outorgado_nome`, `endereco`
- `cartorio.nome`
- `lancamento.descricao`, `observacoes`
- `anotacao_versao.texto`

**Partial UNIQUE indexes** (D1/SQLite suportam): `CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL` em junctions (`imovel_documento`, `lancamento_pessoa`, `tis_imovel`) para garantir unicidade só entre rows ativas. Mermaid não renderiza isto — aplicar via migration Drizzle.

**CHECK constraints** em todos os enums (`tipo_cartorio`, `lancamento_tipo.tipo`, `documento.tipo`, `origem.tipo`, `lancamento_pessoa.papel`, `audit_log.action`, `imovel.arquivado`, `imovel_documento.is_documento_atual`, `anotacao_versao.current_marker`) — aplicar via migration Drizzle.

**Nota sobre Mermaid ERD:** tipos `text` no Mermaid correspondem a `TEXT` no D1. Campos `*_encrypted` (quando existirem em tabelas com PII) são `BLOB` no D1 mas declarados como `text` no Mermaid por limitação de tipos suportados. A constraint de UNIQUE/CHECK no nível do DB vai via migration Drizzle, não no .mmd (Mermaid interpreta `--` e `|` em comentários como relações).

---

### Q11 — Raw vs normalized em campos string com variação real de cartório

**Contexto (Hiure, 2026-06-03):** `documento.numero` tem formato rígido (`<M|T>` + número). Cartório não erra — `_raw` ali é parsing ("M. 1234" vs "M-1234"), não preservação de erro.

**Onde a variação real existe** (campos onde cartório escreve diferente em certidões diferentes pra mesma coisa):

- `documento.outorgante_nome`, `documento.outorgado_nome` — "João da Silva" vs "JOÃO DA SILVA" vs "João da Silva Santos"
- `documento.endereco` — "Rua S. João, 100" vs "Rua São João, n. 100" vs "R. S. João, 100"
- `lancamento.descricao` — texto livre, pode ter abreviações
- `lancamento.outorgante_nome`, `lancamento.outorgado_nome` — mesma variação
- `origem.descricao` — texto livre
- `documento.cartorio_nome` — "1º Cartório de Registro de Imóveis" vs "1o. Cart. Reg. Imóveis"

A pergunta: o padrão `campo_raw` (verbatim) + `campo` (normalized pra busca) deve ser aplicado a esses campos variáveis?

🅰️ **Não** — versão única basta. Mais simples, mas matches de busca podem falhar ("São João" ≠ "S. João") e evidência verbatim se perde.

🅱️ **Sim, em todos os campos variáveis** (nomes, endereços, descrições, cartório) — cada um com `_raw` + normalized. Busca usa normalized; exibição mostra raw com highlight "este verbatim difere do normalizado". Tratamento padrão.

🅲️ **Sim em B, mais flag de "variação significativa"** — quando raw e normalized diferem muito (ex: normalizado tem 80%+ dos tokens do raw, mas com abreviações), marca o campo com `has_significant_variation = true` pra revisão.

🅳️ **Tudo de C, mais detecção de discrepância entre certidões** — quando o MESMO imóvel/documento tem múltiplas certidões com strings diferentes pro mesmo campo lógico, sistema **marca como discrepância** (potencial evidência de grilagem ou erro de cartório). Isso ALINHA com a regra "discrepâncias entre certidões são indicadores de fraude".

**DECIDIDO: 🅰️ com exceção de `cartorio_nome` (Hiure, 2026-06-03).**

**Implicação estrutural:** `cartorio` vira **entidade própria** (tabela `cartorio`), não string field em `documento`. Schema:

- `cartorio` table com campos espelhando a API do **Sistema Nacional de Cartórios** (schema exato TBD — buscar documentação)
- **Source 1 (preferencial):** API lookup → preenche/normaliza `cartorio` automaticamente
- **Source 2 (fallback):** cadastro manual pelo pesquisador, **com os mesmos campos** que a API fornece (consistência de schema)
- `documento.cartorio_id` é FK pra `cartorio.id` (não mais string)
- Cartórios menores do interior não cobertos pela API são cadastrados manualmente — **não tem campo "outros" / texto livre**; o pesquisador preenche a mesma estrutura da API, só que direto

**Por que essa é a escolha "🅱️" só pro cartório:** é o único campo onde a **busca exata + normalização** tem valor sistêmico (cruzar certidões que citam o mesmo cartório); pros outros campos (nomes, endereços, descrições), a busca fuzzy full-text sem _raw/_normalized é suficiente.

@Luandro: tarefa de follow-up — buscar schema da API do Sistema Nacional de Cartórios antes de T-101 (Drizzle schema) e T-300 (legacy-fit).

### Q12 — UX confirmation dialog (UX requirement explícita)

> *"É importante perguntar ao usuário se ele quer mesmo apagar ou se ele quer só editar alguma informação"* (Hiure, 2026-06-02)

Toda operação de delete (soft ou hard) passa por um dialog que:
- Lista blast radius (N+M chains, M' Lancamentos)
- Tem botão padrão "Editar ao invés de apagar" (não destrutivo)
- Tem botão destrutivo "Apagar mesmo assim" (vermelho, exige dupla confirmação)
- Mostra preview do que vai ficar visível/invisível depois do delete

**Recomendação proposta:** Obrigatório em T-105.

**DECIDIDO: 🅳️** (Hiure, 2026-06-03) — dialog sempre com **preview ANTES** (read-only read-back do que vai sumir) + dialog de confirmação. Dois cliques extras, zero ambiguidade.

**Comportamento final do delete (T-105):**

1. Usuário clica "Apagar" → **modal de preview read-only**: lista blast radius ("vai esconder: 1 chain com 3 L's, 1 junction, 0 certidões cross-chain"); permite CANCELAR ou AVANÇAR
2. AVANÇAR → **dialog de confirmação**:
   - Botão padrão (não destrutivo, foco do Enter): **"Editar ao invés de apagar"** → abre o form de edição
   - Botão destrutivo (vermelho, requer type-to-confirm com nome do registro): **"Apagar mesmo assim"**
   - Checkbox opcional: "não mostrar preview de novo nesta sessão" (com audit log)
3. Confirmação → soft-delete (Q7a/B/Q13=B) + audit log (Q9=C) + provenance (Q11)

---

## Próximos passos

1. **Luandro preenche a tabela de Decisões** (acima) com as opções escolhidas.
2. As decisões são commitadas neste arquivo (em um PR de docs).
3. O PR é mergeado na `v2`.
4. T-001 do `docs/TASKS.md` é marcado como concluído.
5. As tarefas T-100, T-101, T-200 etc. podem ser iniciadas.

**Perguntas ou discordâncias?** Abra um issue ou comente direto neste PR.
