# Relatório de Cartórios Suspeitos (Issue #110)

**Command:** `relatorio_cartorios_suspeitos`
**Branch base:** `develop` (contém squash do #109)
**Último commit:** `8640d20c`
**Read-only:** ✅ 3 camadas de proteção (código, DB, teste)

> ⚠️ **AVISO:** Este command é **diagnosticamente read-only**. Nenhum `.save()`, `.update()`, `.delete()`, `get_or_create()` ou `transaction.atomic()` com commit. A simulação de merge (`--merge-plan`) **nunca executa** merges — apenas valida e reporta conflitos.

---

## 1. Como executar

### Dependências
Instale as dependências do projeto (Django 5.2+, weasyprint 62.2):

```bash
pip install -r requirements.txt
```

### Comandos básicos

```bash
# Relatório CSV (diagnóstico completo)
python manage.py relatorio_cartorios_suspeitos \
  --output relatorio.csv \
  --format csv

# Relatório JSON (para ingestão automatizada)
python manage.py relatorio_cartorios_suspeitos \
  --output relatorio.json \
  --format json

# Com lista de cartórios conhecidos (para hash de reprodutibilidade)
python manage.py relatorio_cartorios_suspeitos \
  --output relatorio.csv \
  --known-list cartorios_conhecidos.csv

# Simulação de merge (NUNCA executa, apenas simula)
python manage.py relatorio_cartorios_suspeitos \
  --merge-plan decisao.csv \
  --output merge_simulacao.json
```

### Flags

| Flag | Obrigatório | Descrição |
|---|---|---|
| `--output PATH` | ✅ | Caminho do arquivo de saída (`.csv` ou `.json`). Refusa sobrescrever sem `--force`. |
| `--format csv\|json` | ✅ | Formato de saída. |
| `--known-list PATH` | ❌ | CSV com lista de cartórios conhecidos. Usado para `known_list_hash` no metadado. |
| `--merge-plan PATH` | ❌ | CSV com mapeamento `fantasma_id,correto_id`. Simulação apenas. |
| `--force` | ❌ | Permite sobrescrever arquivo de saída existente. |

---

## 2. Como interpretar a saída

A saída contém **6 tipos de registro** (`record_type`), ordenados por `id ASC`:

### `FANTASMA` — Cartórios CRI suspeitos

```
record_type,id,nome,cns,cidade,estado,signals,severidade,ref_counts
```

| Campo | Descrição |
|---|---|
| `signals` | Lista de sinais: `ESTADO_AUSENTE`, `CNS_SINTETICO`, `LOCALIDADE_COPIADA`, `SEM_VINCULOS` |
| `severidade` | `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` (ver §4) |
| `ref_counts` | JSON com contagens por FK: `{"Documento": 5, "Imovel": 3, "Alteracoes": 0, ...}` |

### `DOCUMENTO` — Documentos associados a fantasmas

```
record_type,id,numero,tipo,cartorio_id,tem_lancamentos,qtd_lanc,criado_por_inicio_mat,referenciado_como_origem,em_cadeia,classificacao,duplicata_id
```

| `classificacao` | Condição |
|---|---|
| **`ATIVO`** | Tem lançamentos + NÃO existe duplicata no cartório correto |
| **`AMBIGUO`** | Tem lançamentos + duplicata também existe |
| **`EM_CADEIA`** | Sem lançamentos próprios + referenciado como `documento_origem` |
| **`ORFAO`** | Sem lançamentos + não em cadeia + existe duplicata |
| **`DESCARTAVEL`** | Sem lançamentos + não em cadeia + sem duplicata |

### `LANCAMENTO` — Lançamentos afetados (ATIVO/AMBIGUO)

```
record_type,id,documento_id,tipo,cartorio_origem_id
```

### `CADEIA` — Cadeias que referenciam EM_CADEIA

```
record_type,documento_id,lancamento_origem_id,documento_pai_id
```

### `SUGESTAO` — Candidatos sugeridos (não vinculante)

```
record_type,fantasma_id,candidato_id,metodo,status
```

| `metodo` | `normalizacao` (NFKD+casefold) ou `manual` (do `--known-list`) |
|---|---|
| `status` | `SUGERIDO`, `NAO_VERIFICADO`, `SEM_CANDIDATO` |

### `RESUMO` — Totais por categoria

```
record_type,metrica,valor
RESUMO,fantasmas_cri,42
RESUMO,documentos_total,1172
RESUMO,documentos_ativos,23
RESUMO,documentos_em_cadeia,15
RESUMO,documentos_ambiguos,12
RESUMO,documentos_orfaos,890
RESUMO,documentos_descartaveis,232
RESUMO,lancamentos_afetados,67
```

### Metadados (reprodutibilidade)

```json
{
  "timestamp": "2026-08-01T15:00:00Z",
  "git_commit": "fff533a5",
  "db_vendor": "sqlite",
  "schema_version": "0049",
  "total_cartorios": 3840,
  "known_list_hash": "sha256:...",
  "ordenacao": "id ASC em todas as seções"
}
```

---

## 3. Fluxo de trabalho recomendado

```
1. Relatório →
2. Revisão humana →
3. CSV de decisão →
4. Simulação de merge →
5. (Futuro) Merge transacional
```

### Passo 1: Gerar relatório
```bash
python manage.py relatorio_cartorios_suspeitos --output suspeitos.csv --format csv
```

### Passo 2: Revisar em planilha
Abrir `suspeitos.csv`, filtrar por `classificacao`:
- **ATIVO / AMBIGUO** — prioridade alta (documentos com lançamentos reais)
- **EM_CADEIA** — verificar cadeia inteira antes de qualquer ação
- **ORFAO** — provavelmente já foram corrigidos (órfãos de merges anteriores)
- **DESCARTAVEL** — lixo provável

### Passo 3: Criar CSV de decisão
```csv
fantasma_id,correto_id
3488,1347
3529,1347
3707,2891
3983,3102
```

> **Importante:** Use IDs reais do relatório. O `fantasma_id` é o cartório suspeito; o `correto_id` é o cartório CRI com estado preenchido.

### Passo 4: Simular merge
```bash
python manage.py relatorio_cartorios_suspeitos \
  --merge-plan decisao.csv \
  --output simulacao.json \
  --format json
```

Verifique os status de cada par:
- **`SEGURO`** — zero conflitos, pronto para merge futuro
- **`CONFLITO`** — colisão de unicidade, precisa de intervenção
- **`CICLO`** — source é target de outro merge
- **`CASCADE_RISCO`** — Alteracoes seriam apagadas
- **`CADEIA_AFETADA`** — documentos EM_CADEIA seriam reatribuídos

### Passo 5: Merge (NÃO automatizado — issue futura)
O merge transacional será implementado em uma issue separada. Este command **nunca executa** merges.

---

## 4. Severidade (ordem total)

| Severidade | Condição |
|---|---|
| **`CRITICAL`** | CNS sintético + documentos ATIVOS ou EM_CADEIA vinculados |
| **`HIGH`** | CNS sintético + apenas órfãos/descartáveis |
| **`MEDIUM`** | Duplicidade por nome + documentos ativos |
| **`LOW`** | Sem vínculos (CRI legítimo não usado) |

**Regra de cálculo:** todos os sinais são avaliados; a severidade máxima vence.

### Sinais

| Sinal | Código | Regra |
|---|---|---|
| Estado ausente | `ESTADO_AUSENTE` | `estado IS NULL` OR vazio/só espaços |
| CNS sintético | `CNS_SINTETICO` | `UPPER(TRIM(cns)) LIKE 'CNS%'` |
| Localidade copiada | `LOCALIDADE_COPIADA` | cidade = `ASSIS BRASIL` AND CNS sintético |
| Sem vínculos | `SEM_VINCULOS` | Zero referências em todas as 8 FKs CRI |

---

## 5. CNS (Cartão Nacional de Saúde) — evidência, não decisão

| Critério | Resultado |
|---|---|
| `UPPER(TRIM(cns)).startswith('CNS')` | CNS sintético (criação automática confirmada) |
| 15 dígitos, DV módulo 10 (Luhn) | CNS canônico válido |
| `8888xx` | Institucional (Registro de Imóveis do Brasil) |
| Falha de DV | `DV_NAO_CONFERE` — **nunca** prova de inexistência. Registro oficial prevalece. |

**Nenhum bloqueio por CNS.** CNS sintético é um sinal de evidência no relatório, não um critério de decisão.

---

## 6. FKs auditadas (escopo CRI)

**8 foreign keys** verificadas — todas com `on_delete=PROTECT` exceto as de `Alteracoes`:

| # | Model | Campo | on_delete |
|---|---|---|---|
| 1 | `Imovel` | `cartorio` | PROTECT |
| 2 | `Documento` | `cartorio` | PROTECT |
| 3 | `Documento` | `cri_atual` | PROTECT |
| 4 | `Documento` | `cri_origem` | PROTECT |
| 5 | `Lancamento` | `cartorio_origem` | PROTECT |
| 6 | `LancamentoOrigem` | `cartorio` | PROTECT |
| 7 | `Alteracoes` | `cartorio` | CASCADE ⚠️ |
| 8 | `Alteracoes` | `cartorio_origem` | CASCADE ⚠️ |

**Fora do escopo:** `Lancamento.cartorio_transmissao`, `Lancamento.cartorio_transacao` (transmissão, não CRI).

**Orçamento de queries:** 8 agregações agrupadas (`values(fk_id).annotate(n=Count("pk"))`) + combinação em Python = ~9 queries. Máximo: 11.

**Proteção contra FK nova:** o command compara `Cartorios._meta.related_objects` com uma allowlist. Se uma nova relação aparecer em produção, o command **falha explicitamente** em vez de omitir silenciosamente.

---

## 7. Garantia read-only (3 camadas)

### Camada 1: Código
- Apenas `SELECT` via ORM
- Nenhum `.save()`, `.update()`, `.delete()`, `get_or_create()`
- Nenhum `transaction.atomic()` com commit

### Camada 2: Banco
- **PostgreSQL:** transação externa com `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY`; verifica `SHOW transaction_read_only = on` antes de prosseguir
- **SQLite:** conexão com URI `file:...?mode=ro`

### Camada 3: Teste de integração (prova)
- Nos **dois** backends (SQLite + PostgreSQL, skip se sem PG):
  1. Executa o command
  2. Tentativa de escrita deliberada → **DEVE FALHAR**
  3. Hash de todas as tabelas antes/depois → **idêntico**
- Captura de SQL como defesa complementar
- Bloqueado: `INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|TRUNCATE|MERGE|COPY|WITH...UPDATE|WITH...DELETE|WITH...INSERT`

---

## 8. Limitações

| Limite | Detalhe |
|---|---|
| Normalização | Não trata ordinais ("1º" vs "Primeiro"), siglas ("CRI" vs "RI"), prefixos ("Cartório de" vs "") |
| CNS DV | Falha de dígito verificador ≠ inexistência. Registro oficial prevalece. |
| Matching automático | Não faz matching fantasma→correto automaticamente. Sugere, mas exige CSV de decisão. |
| Transmissão | Cartórios de transmissão (OUTRO) com ASSIS BRASIL são problema separado (issue futura). |
| Merge | A simulação é **read-only**. O merge transacional é uma issue futura. |

---

## 9. Testes

Suite: `dominial/tests/test_relatorio_cartorios_suspeitos.py` + `dominial/tests/test_cns_utils.py`

```bash
python manage.py test \
  dominial.tests.test_cns_utils \
  dominial.tests.test_relatorio_cartorios_suspeitos \
  --settings=cadeia_dominial.settings_test -v2
```

### Fixtures críticas (4 fantasmas)

| ID | Nome | CNS | Severidade |
|---|---|---|---|
| 3488 | 1º CRI Dourados | CNS2339110126 | CRITICAL |
| 3529 | CRI Ponta Porã | CNS1089051924 | CRITICAL |
| 3707 | CRI Caarapó | CNS1687534899 | CRITICAL |
| 3983 | CRI Iguatemi | CNS1472193567 | CRITICAL |

### Testes de simulação

| Teste | Valida |
|---|---|
| `test_simulacao_seguro` | Zero conflitos → `SEGURO` |
| `test_simulacao_conflito` | Colisão → 2 PKs reportados |
| `test_simulacao_ciclo` | A→B e B→A → `CICLO` |
| `test_simulacao_cascade` | Alteracoes → `CASCADE_RISCO` |
| `test_simulacao_cadeia_afetada` | Docs EM_CADEIA → `CADEIA_AFETADA` |
| `test_simulacao_schema_divergente` | Drift de schema → `SCHEMA_DIVERGENTE` |
| `test_fk_nova_falha` | Nova FK → erro explícito |
| `test_escrita_atomica` | Arquivo existente sem `--force` → erro |
| `test_read_only_sqlite` | SQLite mode=ro, escrita deliberada FALHA |
| `test_read_only_postgres` | PG READ ONLY, escrita FALHA (skip se sem PG) |

---

## 10. Riscos residuais (fora do escopo)

| Item | Status |
|---|---|
| Command de merge transacional | Issue futura |
| Cartórios de transmissão com ASSIS BRASIL | Problema separado (issue #110 follow-up) |
| Verificação ONR/CNJ | Requer API externa |
| Correção da criação automática | Issue #109 (já resolvida via PR #111) |
| Normalização avançada (ordinal, siglas, stopwords) | v2 |
| Matching automático fantasma→correto | v2 — com confirmação humana obrigatória |
| Interface admin | Command é mais seguro para v1 |

---

*Última atualização: `8640d20c` (2026-08-01)*
*Próxima revisão: após aprovação do PR #112*
