# Decisão de Schema: `pendencia_cartorio` (Fila de Pendências de Cartório)

> **Data:** 2026-07-24
> **Autor:** Hiure (implementador)
> **Status:** ⏳ Rascunho — aguardando aprovação de Luandro (decisor)
>
> Este documento segue o formato de `SCHEMA_DECISOES_PENDENTES.md` e registra a
> decisão de design para a tabela `pendencia_cartorio`, criada fora do roadmap
> original e registrada como dívida técnica [TD-001](../TASKS.md#technical-debt).

---

## Q-PC1 — O que é uma pendência de cartório?

### 🤔 A pergunta
Quando uma `origem` (citação a um documento anterior) referencia um documento
que **não pode ser automaticamente pareado** a um CRI (Cartório de Registro de
Imóveis) conhecido, como o sistema deve tratar esse match imperfeito?

### 📍 Como funciona hoje
O schema atual (`origem`) tem uma FK opcional `cri_id` e `documento_id`. Mas,
na migração do PostgreSQL legado, muitas origens têm apenas o texto cru do
documento citado (`numero_raw`) sem um `cri_id` ou `documento_id` resolvido.
No Django, isso simplesmente ficava NULL — sem registro de que um humano
precisava revisar.

### ⚖️ Decisão
**Criar uma fila revisável (`pendencia_cartorio`) com status auditável.**

Cada origem sem match automático gera um registro de pendência. Um operador
humano revisa esses registros (via endpoints de API) e pode **confirmar**
(associar o CRI correto) ou **rejeitar** (marcar como falso positivo).

---

## Q-PC2 — Qual o confidence check?

### 🤔 A pergunta
Toda origem não resolvida vira pendência, mas nem toda pendência é igual — como
distinguir sugestões automáticas com diferentes níveis de certeza?

### 📍 Como funciona hoje
Não existe. O `legacy-fit` cria pendências para toda origem com
`documento_id IS NULL`, todas com confiança `fraca`.

### ⚖️ Decisão

| Confiança | Quando usar |
|-----------|-------------|
| `fraca` | Match automático entre CRIs diferentes (cross-cartório) sem confirmação explícita. |
| `forte` | Documento com alta similaridade textual (ex: mesmo número em cartório diferente). *Reservado para uso futuro.* |
| `alerta` | Conflito: duas origens apontam para o mesmo documento como origens diferentes, ou dados auto-contraditórios. *Reservado.* |

### 🗄️ CHECK constraint

```sql
CONSTRAINT "pendencia_cartorio_confianca_check"
  CHECK("pendencia_cartorio"."confianca" IN ('fraca', 'forte', 'alerta'))
```

---

## Q-PC3 — Ciclo de vida de uma pendência

### 🤔 A pergunta
Qual o fluxo de resolução?

### ⚖️ Decisão

```
pendente → confirmada (match aceito pelo humano)
pendente → rejeitada  (falso positivo)
```

Quando confirmada:
- `cri_confirmado_id` é preenchido (pode ser diferente do `cri_sugerido_id`)
- `documento_id` pode ser atualizado na `origem` correspondente
- A `origem` recebe o `cri_id` confirmado

Quando rejeitada:
- A pendência é arquivada, mas a `origem` **não** é alterada
- A origem continua sem CRI — pode ser revisada novamente se um novo mecanismo
  de match surgir

### 🗄️ Status enum

```sql
CONSTRAINT "pendencia_cartorio_status_check"
  CHECK("pendencia_cartorio"."status" IN ('pendente', 'confirmada', 'rejeitada'))
```

### 🌳 Como fica no grafo
- **Enquanto pendente:** a origem aparece no grafo com um indicador visual
  (ícone/exclamação) mostrando que o CRI não foi confirmado.
- **Depois de confirmada:** o grafo reflete o CRI confirmado (normal).
- **Depois de rejeitada:** a origem permanece no grafo sem CRI, mas sem o
  indicador de alerta.

---

## Q-PC4 — Rastreamento de auditoria

### 🤔 A pergunta
O histórico de quem e quando resolveu uma pendência é necessário?

### ⚖️ Decisão
**Sim.** Toda resolução registra:
- `resolvido_por` — JWT `sub` do operador
- `resolvido_em` — ISO timestamp da resolução
- `cri_confirmado_id` — qual CRI foi apontado (pode divergir da sugestão)

Isso garante rastreamento completo e alinhado com a decisão Q9 (audit log) do
schema v2.

---

## Q-PC5 — Cascade vs soft-delete

### 🤔 A pergunta
O que acontece quando uma `origem` ou `cri` referenciado por uma pendência é
apagado?

### ⚖️ Decisão

| FK | Comportamento | Justificativa |
|----|---------------|---------------|
| `origem_id` | `CASCADE` | Pendência sem origem não faz sentido |
| `cri_sugerido_id` | `SET NULL` | A sugestão pode desaparecer, mas a pendência continua válida |
| `cri_confirmado_id` | `SET NULL` | Mesmo motivo — a confirmação persiste como histórico |

---

## Resumo

| Item | Decisão |
|------|---------|
| **Tabela** | `pendencia_cartorio` |
| **FKs** | `origem_id` (CASCADE), `cri_sugerido_id`/`cri_confirmado_id` (SET NULL) |
| **Confiança** | `fraca` \| `forte` \| `alerta` (CHECK) |
| **Status** | `pendente` → `confirmada` \| `rejeitada` (CHECK) |
| **Auditoria** | `resolvido_por`, `resolvido_em` |
| **Timestamps** | `created_at` (not null) |
| **Convite à ação** | A confiança `forte` e `alerta` não são geradas por nenhum mecanismo atual — o `legacy-fit` só produz `fraca`. Mecanismos de matching mais sofisticados podem usar esses níveis no futuro. |

---

## Pendências futuras (não resolvidas aqui)

1. **CRI selection in confirmation flow** — the current UI sends a generic "confirm" without allowing the operator to pick which CRI to associate. A dropdown/autocomplete for CRI selection should be added.
2. **Reabertura de pendências** — uma pendência rejeitada poderia ser reaberta se novos dados aparecerem? Ainda não implementado.
3. **Notificação** — quando uma pendência de alta confiança (`forte`) surgir, notificar operadores? Fora do escopo por enquanto.
4. **Mutação atômica** — a confirmação atual faz dois UPDATES (pendência + origem) em statements separados. Se o segundo falhar, a pendência fica como `confirmada` sem a origem atualizada. Uma transação atômica (D1 batch ou exec multi-statement) resolveria isso quando suportada pelas types do projeto.
