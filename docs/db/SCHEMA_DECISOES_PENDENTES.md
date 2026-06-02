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

> 👇 **Esta seção deve ser preenchida por Luandro** com a escolha de cada pergunta. O blocker T-001 do `docs/TASKS.md` só é considerado fechado quando todas as 6 tiverem uma resposta aqui.

| # | Pergunta | Escolha | Justificativa |
|---|---|---|---|
| Q1 | Cascade em Imovel | _pendente_ | |
| Q2 | Soft-delete vs hard-delete | _pendente_ | |
| Q3 | Cardinalidade OrigemFimCadeia | _pendente_ | |
| Q4 | PII encryption at rest | _pendente_ | |
| Q5 | Validação CPF/CNPJ (DB vs app) | _pendente_ | |
| Q6 | React Flow: atual vs completo | _pendente_ | |

**Formato sugerido para preencher:**

```markdown
| Q1 | Cascade em Imovel | **Opção C** (soft-delete + CASCADE) | Permite restaurar cadastros errados sem perder histórico. Auditoria cartorial exige. |
| Q2 | Soft-delete | **Opção C** (anonimização LGPD) | Único caminho que atende LGPD e mantém navegação do grafo. |
| Q3 | Cardinalidade OrigemFimCadeia | **Opção B** (1:N, como Django) | Preserva toda informação. Compatibilidade com legado. |
| Q4 | PII encryption | **Opção A** (texto puro) | Ambiente interno controlado, sem exposição à internet. Decidir de novo se mudar. |
| Q5 | Validação CPF/CNPJ | **Opção C** (normalizado no banco) | CHECK constraint garante integridade; app valida dígitos. |
| Q6 | React Flow visualização | **Opção C** (toggle) | Melhor para múltiplos públicos. Custo de UI aceitável. |
```

---

## Próximos passos

1. **Luandro preenche a tabela de Decisões** (acima) com as opções escolhidas.
2. As decisões são commitadas neste arquivo (em um PR de docs).
3. O PR é mergeado na `v2`.
4. T-001 do `docs/TASKS.md` é marcado como concluído.
5. As tarefas T-100, T-101, T-200 etc. podem ser iniciadas.

**Perguntas ou discordâncias?** Abra um issue ou comente direto neste PR.
