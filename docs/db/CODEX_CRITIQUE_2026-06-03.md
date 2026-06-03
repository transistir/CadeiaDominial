# Codex Critique 2026-06-03 — Cadeia Dominial v2 Schema (Q1-Q15 + Q11b + ERD)

> Gerado por Codex gpt-5.5 (reasoning: high) lendo `docs/db/SCHEMA_DECISOES_PENDENTES.md` + `docs/db/erd-v2.mmd`. Tokens: 104,514. Verdict: **NEEDS REWORK, medium severity**.

## 1. Q11b é direcionalmente correto, mas `cri` precisa de unicidade canônica

A constraint em si está certa para a regra "matrícula 12345 no 1º CRI Salvador != matrícula 12345 no 2º CRI Salvador":

```sql
documento {
  int cri_id FK
  text tipo
  text numero
  UNIQUE (cri_id, tipo, numero)
}
```

Mas `cri` tem `cns_codigo` como "TBD" sem unicidade visível. Se usuários podem criar linhas duplicadas pro mesmo CRI, o UNIQUE do documento é burlado atribuindo o mesmo documento a dois `cri.id` duplicados. Adicionar um UNIQUE ativo real pra `cri`, idealmente CNS quando disponível.

**Refs:** `erd-v2.mmd:31-40`, `SCHEMA_DECISOES_PENDENTES.md:611-617`

## 2. Evidência pode ser perdida normalizando números de origem/documento agressivamente

O doc diz que o número do documento tem formato rígido e "cartório não erra nesse campo" — a suposição mais arriscada do design dado o contexto de grilagem.

```mmd
documento.numero     "normalizado, so digitos"
documento.numero_raw "valor original, so para referencia"
origem.numero        "so digitos"  // ⚠️ SEM numero_raw!
```

`documento` ao menos tem `numero_raw`; `origem` não tem. Citações de origem são exatamente onde certidões divergentes podem expor fraude. Se uma certidão diz um número de origem de jeito esquisito/errado/sufixo, `origem.numero` "só dígitos" pode apagar evidência. Mínimo: preservar verbatim origin number separado do normalized searchable number.

**Refs:** `erd-v2.mmd:79-80`, `erd-v2.mmd:153`

## 3. Atores de audit estão confundidos com Pessoas do domínio

O ERD usa `pessoa` tanto pra pessoas que aparecem em registros cartorários quanto pra pesquisadores que executam ações no sistema:

```mmd
pessoa ||--o{ lancamento_move_event : "moved_by"
audit_log.actor_id FK "pessoa que executou"
anotacao_versao.created_by_id FK "pessoa"
```

Isto vai morder. Um João da Silva no cartório não é o mesmo tipo de entidade que uma conta de pesquisador. Manter `pessoa` de domínio pra registros copiados; usar `user`/`pesquisador` separado pra audit.

**Refs:** `erd-v2.mmd:25`, `erd-v2.mmd:180`, `erd-v2.mmd:204`

## 4. Q13 resolve documentos compartilhados, mas sub-especifica constraints ativo/atual

A junction N:N é o movimento certo. Edge cases ainda precisam constraints de migração:

- **active pair uniqueness:** `(imovel_id, documento_id) WHERE deleted_at IS NULL`
- **provavelmente um único current per imóvel:** `(imovel_id) WHERE is_documento_atual = 1 AND deleted_at IS NULL`
- **decidir se um Lancamento MOVIDO pra um Documento compartilhado por 3 imóveis deve aparecer nas 3 chains.** Sob a regra Q13 "belongs equally", sim, mas a UX precisa deixar esse blast radius explícito.

**Refs:** `SCHEMA_DECISOES_PENDENTES.md:706-735`, `erd-v2.mmd:65-74`

## 5. Q14 append-only MOVE é defensível, mas invariantes de current-state estão faltando

Não é over-engineering automático. Se `lancamento.documento_id` significa "onde o registro copiado originalmente vivia", então event-sourcing MOVE é apropriado. **Mas a regra atual é UI-derivada e frágil.** Você precisa de lógica determinística de current-location: order by `(moved_at, id)`, enforce `from_documento_id` = current document no momento do move, e prevenir dois latest moves competidores. Senão em 2 anos você vai debugar lançamentos fantasma. Uma **SQL view ou projection mantida** basta; não precisa de arquitetura nova.

**Refs:** `SCHEMA_DECISOES_PENDENTES.md:761-787`, `erd-v2.mmd:184-194`

## 6. Q15 recomendação: escolher D, com "órfão" como estado derivado

Dado Q13 e Q12, B não deve ser default. A é fraco demais (esconde delete global). C é aceitável, mas D é a escolha limpa:

```
D está em N chains:
- default: desvincular desta cadeia
- admin-only: apagar globalmente
- if no active imovel_documento remains: D is orphaned
```

**Caveat importante:** "órfão" deve ser **derivado** de `NOT EXISTS active imovel_documento`, não uma mutação destrutiva automática.

**Refs:** `SCHEMA_DECISOES_PENDENTES.md:798-816`

## 7. Apêndice SQLite/D1 está no caminho certo, mas incompleto pra migrations reais

**Correto:** D1 suporta FTS5, FK PRAGMAs, partial indexes (per Cloudflare docs).

**Faltando:**
- SQLite/D1 não tem `NOW()` do PostgreSQL; app deve escrever UTC ISO8601 ou usar funções datetime do SQLite consistentemente.
- FTS5 precisa de sync strategy: triggers ou rebuild/update path explícito.
- FK actions devem ser explícitas nas migrations; Mermaid não pode mostrar `ON DELETE`.
- Datas copiadas do cartório podem ser parciais/incertas; strict ISO date fields forçam precisão falsa.

## 8. Mermaid esconde o bastante pra mascarar bugs reais do schema

O ERD usa colunas fake tipo:

```mmd
text UNIQUE_NOTE "UNIQUE (cri_id, tipo, numero)"
text UNIQUE_NOTE "UNIQUE (documento_id, numero_lancamento)"
```

Isto é OK como documentação, mas perigoso se alguém tratar o ERD como schema. A **migration Drizzle deve ser canônica** pra UNIQUE, partial UNIQUE, CHECK, FK actions, triggers, e indexes. Mermaid também não pode mostrar filtros de soft-delete ou constraints "current".

**Refs:** `erd-v2.mmd:93`, `erd-v2.mmd:133`, `erd-v2.mmd:159`

---

## Verdict

**NEEDS REWORK, medium severity.** A direção conceitual é sólida: Q11b FK direto é correto, Q13 N:N é correto, Q14 append-only é defensível. Os blockers são nível-implementação mas importantes: **unicidade canônica do CRI, preservação verbatim dos números de origem, identidade separada de pesquisador, e current/partial constraints explícitos antes de T-101 migrations**.
