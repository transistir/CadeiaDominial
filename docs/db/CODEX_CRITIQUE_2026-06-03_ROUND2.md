# Codex Critique 2026-06-03 — Round 2

> Crítica rodada por Codex gpt-5.5 (xhigh reasoning) em 2026-06-03 sobre o ERD v2 + SCHEMA_DECISOES_PENDENTES.md após aplicação de D1-D4 + T1-T4.

## Verdict

**NEEDS-MINOR-FIXES** — 2 BLOCKERS, 1 NICE-TO-HAVE, 4 inconsistências textuais.

Direção conceitual permanece sólida. Erros são nível-documentação (campo errado, FK faltando, snippet obsoleto).

## Round 1 Closure Check (1-8)

| # | Achado round 1 | Endereçado? |
|---|---|---|
| 1 | CRI active uniqueness | ✅ `cri.UNIQUE_NOTE` documenta partial UNIQUE; apêndice inclui `uq_cri_cns` |
| 2 | Raw origin/document numbers | ✅ `origem.numero_raw` presente; `documento.numero_raw` mantido |
| 3 | User vs pessoa identity | ⚠️ **PARCIAL** — MOVE/audit/editor agora usam `user`, mas `anotacao_versao.autor_original_id` ainda aponta para domain `pessoa` (F1 abaixo) |
| 4 | Q13 active/current constraints | ✅ `imovel_documento` tem metadata per-pair + ambos partial UNIQUE documentados |
| 5 | Q14 current-location invariant | ⚠️ **PARCIAL** — eventos append-only + `v_lancamento_current_location` documentados; **falta invariante write-time** de que `from_documento_id` = current location |
| 6 | Q15 orphan mode | ✅ `v_documento_orfao` documentado, nenhuma coluna `is_orfao` aparece |
| 7 | SQLite/D1 appendix | ⚠️ **PARCIAL** — types, `NOW()`, FTS5, partial indexes cobertos; **FK actions incompletas** apesar de a doc afirmar "toda FK precisa de onDelete explícito" |
| 8 | Mermaid is not schema | ✅ T4 disclaimer aparece no ERD, legend, e decisions doc |

## New Findings

### F1 — BLOCKER — Annotation authorship aponta para entidade errada

**Q9 é "researcher attribution"** — pesquisadores criam/editam/removem anotações. O ERD atualmente documenta `anotacao_versao.autor_original_id` como `PESSOA` (cartório), mas a pergunta Q9 fala de **pesquisador** criando a anotação. Isso contradiz a separação D3 de `user` vs `pessoa`.

**Ação:**
- Mudar `anotacao_versao.autor_original_id` de `pessoa_id` (FK) para `user_id` (FK)
- Atualizar visual edge: `pessoa ||--o{ imovel_documento : "anotou"` está **errado geometricamente** — o FK mora em `anotacao_versao`, não em `imovel_documento`
- Corrigir para: `user ||--o{ anotacao_versao : "autor_original (Q9=C, imutavel)"`
- Manter `user ||--o{ anotacao_versao : "created_by (D3, editor, pode diferir do autor original)"` (já existe)

**Justificativa (de Q9):** *"Pesquisadores de grilagem ingerem dados públicos de cartórios (read-only) e adicionam anotações analíticas próprias."* — o "quem" da anotação é o pesquisador, não uma pessoa do cartório.

### F2 — BLOCKER — `anotacao_versao` é documentada como soft-deletable mas falta `deleted_at`

A legend (linha 96) diz: *"deleted_at (Q2=B): presente em imovel, documento, lancamento, lancamento_pessoa, imovel_documento, pessoa, anotacao_versao, cri."* — mas a definição da tabela `anotacao_versao` no .mmd não tem `deleted_at`.

**Ação:**
- Adicionar `text deleted_at "soft-delete (Q2=B)"` à definição de `anotacao_versao` no .mmd
- Documentar a interação com `is_current`: soft-delete da anotação inteira (todas as versões) vs `is_current=0` numa versão específica (marca como não-atual, mas mantém no histórico)

### F3 — NICE-TO-HAVE — T3 FK-action coverage + visual FK coverage ainda incompletas

**FK actions faltando no apêndice (T3):**
- `lancamento.tipo_id` → `lancamento_tipo.id`
- `anotacao_versao.created_by_id` → `user.id` (D3)
- `anotacao_versao.operation_id` → `audit_log.id`
- `lancamento_move_event.audit_log_id` → `audit_log.id`
- `origem.documento_id` → `documento.id`
- `tis.terra_referencia_id` → `terra_indigena_referencia.id`

**Relacionamento visual faltando:**
- `lancamento_tipo ||--o{ lancamento` — `lancamento.tipo_id FK` existe; a legend descreve "classifica"; mas o .mmd não tem a edge

**Ação:**
- Completar a tabela de FK actions
- Adicionar `lancamento_tipo ||--o{ lancamento : "classifica (tipo_id)"` ao .mmd

## Schema Inconsistencies (textuais, não estruturais)

1. **Q2 section still recommends Option C, while final decisions table says Q2 is Option B.** — Verificar que o `### ✅ Recomendação` de Q2 (linha ~170) diz "Opção C" mas a tabela de Decisões (linha ~879) diz "**B**". A recomendação foi escrita antes da decisão final.
2. **Decisions intro still says Q15 is open, while Q15 is later decided as D.** — Já corrigido em "Próximos passos" mas a intro do Q1 (linha 5) diz "10 deles não podem ser resolvidos sem decisão humana. São as 6 perguntas abaixo (Q1 a Q6)" — incoerente com 15 perguntas decididas.
3. **Q11b "schema final" snippet still shows `documento.imovel_id` and `documento.is_documento_atual`** — Q13 remove ambos para `imovel_documento`. Snippet obsoleto.
4. **Q14 invariante write-time faltando** — `lancamento_move_event.from_documento_id` deve ser igual ao `current_documento_id` ANTERIOR ao MOVE. Sem CHECK, um bug pode inserir move event com `from` errado. Documentar como invariante (no CHECK constraint ou na app).

## Q14 / Q15 Invariant Check (revisitado)

- ✅ `lancamento` não tem `current_documento_id` coluna (preserva Q14 append-only)
- ✅ Sem FK de "back-reference" para L movido (UI sempre consulta `v_lancamento_current_location`)
- ✅ Sem `is_orfao` flag (Q15=🅳️ corretamente usa view)

## Specific Line Citations

- F1: `docs/db/erd-v2.mmd:19-20`, `:34`, `:192-202`; `docs/db/erd-v2-legend.md:78-80`, `:99`; `docs/db/SCHEMA_DECISOES_PENDENTES.md:529-542`
- F2: `docs/db/erd-v2.mmd:192-203`; `docs/db/erd-v2-legend.md:96`, `:101`; `docs/db/SCHEMA_DECISOES_PENDENTES.md:529-532`, `:911`
- F3: `docs/db/erd-v2.mmd:15-38`, `:116-141`, `:202-213`, `:233`; `docs/db/SCHEMA_DECISOES_PENDENTES.md:975-995`
- Q14 write-time invariant: `docs/db/SCHEMA_DECISOES_PENDENTES.md:761-807` (Q14 section)
- Q15: `docs/db/SCHEMA_DECISOES_PENDENTES.md:846-879` (Q15=🅳️ section)

## Recommended Action

Aplicar F1, F2, F3 + as 4 inconsistências textuais antes do PR. **Espera-se** re-renderizar o ERD e fazer nova crítica round 3 (esperado: READY-TO-MERGE).
