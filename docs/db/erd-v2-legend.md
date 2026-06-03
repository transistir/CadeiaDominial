# Legenda - Diagrama de Entidades (ERD) v2

Este diagrama mostra **tabelas** (caixas) e **relacionamentos** (linhas) entre elas. A ideia e que qualquer pessoa consiga entender o que cada linha significa.

> **Decisoes de design** (Q1-Q15, Q11b, D1-D4, T1-T4) que ancoram este ERD: `docs/db/SCHEMA_DECISOES_PENDENTES.md`. **Schema canonico** (colunas, constraints, tipos SQLite/D1): `docs/db/SCHEMA_CONSOLIDATED.md`. **Critica completa do Codex gpt-5.5 (high)**: `docs/db/CODEX_CRITIQUE_2026-06-03.md`.
>
> **T4 — Mermaid NAO e schema.** O `.mmd` e documentacao visual. UNIQUE_NOTE, comentarios inline, e tipos no Mermaid nao sao enforcem em SQL. A versao canonica e a Drizzle migration (T-101) com partial UNIQUE indexes, CHECK constraints, FTS5 sync triggers, e views.

## 1) O que e cada caixa (tabela)

- Cada caixa representa uma **tabela** do banco de dados.
- Dentro da caixa estao os **campos** (colunas) com seu tipo (`int`, `text`, `integer`).
- `PK` = **Primary Key** (identificador unico da linha).
- `FK` = **Foreign Key** (campo que aponta para outra tabela).

### Tipos no ERD (convencao SQLite/D1 — ver Apêndice em SCHEMA_DECISOES_PENDENTES.md)

| Notacao no ERD | Tipo real (D1/SQLite) |
|---|---|
| `int` | `INTEGER` |
| `text` | `TEXT` |
| `integer` com `0/1` no comment | `INTEGER` + `CHECK (col IN (0,1))` (boolean) |
| `date` / `data` | `TEXT` ISO8601 (`'2026-06-03'`) |
| `datetime` | `TEXT` ISO8601 com hora (`'2026-06-03T14:30:00Z'`) |
| `decimal valor_transacao` | `INTEGER` em **centavos** (evita rounding errors) |
| `decimal area` | `INTEGER` em **centiares** (1 are = 100 m²) |

## 2) Como ler os relacionamentos

O formato e do tipo: `A ||--o{ B : rotulo`

- **A** e a tabela de origem
- **B** e a tabela relacionada
- **rotulo** explica o sentido da relacao em linguagem humana

### Cardinalidade (quantidade de registros)

- `||` = exatamente 1
- `o|` = 0 ou 1 (opcional)
- `o{` = 0 ou muitos
- `|{` = 1 ou muitos

### Exemplos simples (Q11b aplicado)

- `cri ||--o{ documento : emite (Q11b=C, FK direto, sem junction)`
  - Um **CRI** pode emitir **varios documentos**.
  - Um documento pertence a **um** CRI (FK direto, sem tabela intermediaria).
  - **Constraint:** `UNIQUE (cri_id, tipo, numero)` — mesma matricula em CRIs diferentes = documentos diferentes.

- `imovel ||--o{ imovel_documento : pertence (Q13=B, N:N)`
  - Um **imovel** tem **varios** documentos (via junction).
  - Um **documento** pode estar em **varios** imoveis (compartilhamento de cadeia entre grileiros).
  - `is_documento_atual` e **per-par** (Imovel, Documento), nao global.

- `lancamento ||--o{ origem : possui (Q3=B)`
  - Um **lancamento** pode ter **varias origens**.
  - Cada origem pertence a **um** lancamento.
  - Cada origem pode ter (zero ou um) `origem_fim_cadeia` independente (classificacao por origem).

- `origem o|--o{ origem_fim_cadeia : "?"` (na verdade e 1:1)
  - Ver: `origem ||--o| origem_fim_cadeia : fim_cadeia` — uma origem pode ter zero ou um registro de fim de cadeia.

## 3) Significado dos rotulos (texto nas linhas)

- **emite (Q11b=C)**: CRI registra um documento. FK direto, sem junction. UNIQUE (cri_id, tipo, numero).
- **registra (Q11b=B, fixo)**: CRI esta associado a um imovel. **Fixo, sem historico no v1** (pesquisadores trabalham com documentos ja consolidados).
- **pertence (Q13=B, N:N)**: imovel_documento (junction) — Documento e **igualmente pertencente** a todos os imoveis que o citam.
- **proprietario**: pessoa relacionada ao imovel como proprietario. Pode ser NULL apos anonimizacao LGPD.
- **gera**: documento gera lancamentos.
- **classifica**: tipo que define regras (UI flags) do lancamento.
- **envolve / participa (Q2=B)**: ligacao entre lancamento e pessoa via `lancamento_pessoa`. `nome_verbatim` preserva evidencia mesmo se `pessoa_id` vira NULL (LGPD).
- **referencia (cri_origem, Q11b=A)**: origem aponta para um CRI. **Este campo ja e o "cri_origem_id" do Lancamento** (NÃO adicionar coluna separada).
- **origem_doc**: origem aponta para um documento (opcional, NULL se tipo=fim_cadeia).
- **movido (Q14=B, append-only)**: lancamento_move_event registra MOVE cross-chain. Lancamento NAO e mutado.
- **from_doc / to_doc (Q14=B)**: D origem e D destino do MOVE.
- **moved_by (D3)**: `user` (pesquisador) que executou o MOVE. NAO `pessoa` (que e do dominio cartorio).
- **actor (D3)**: `user` (pesquisador) que executou a acao registrada no `audit_log`. NAO `pessoa`.
- **created_by (D3)**: `user` editor da `anotacao_versao`. DIFERENTE de `autor_original_id`, que permanece como `pessoa` (criador original, imutavel por Q9=C).
- **anotado_em (Q9=C)**: anotacao_versao registra anotacoes analiticas do pesquisador. Trilha de versoes + provenance de criacao.
- **anotou (Q9=C)**: autor_original_id da anotacao. **NUNCA muda** (mesmo se outrem editar a anotacao depois).
- **vincula_TI**: imovel associado a uma Terra Indigena (N:N via tis_imovel).
- **referencia (TI)**: TI aponta para a tabela de referencia oficial (terra_indigena_referencia).

## 4) Campos importantes explicados em linguagem simples

- **documento.numero**: normalizado, so digitos. Mesmo formato `M` ou `T` + numero.
- **documento.numero_raw**: valor original do cartorio (com pontos, tracos, etc). **NUNCA usado em busca** (e so para referencia).
- **documento.outorgante_nome / outorgado_nome / endereco**: busca fuzzy FTS5 (Q10=A — sem `_raw` + `_normalized`; variacao real entre certidões e preservada).
- **imovel_documento.is_documento_atual (Q13=B)**: per-par (Imovel, Documento). "Documento X e o atual pro imovel Y" — pode ser FALSE pra outros imoveis.
- **imovel.cri_id (Q11b=B)**: FIXO, sem historico no v1. Se comarca mudar na historia do imovel, criar `imovel_cri_historico` depois.
- **origem.tipo**: `matricula`, `transcricao` ou `fim_cadeia`.
- **origem.documento_id**: documento de origem (opcional, quando tipo != `fim_cadeia`).
- **origem.indice**: ordem das origens dentro de um lancamento (0, 1, 2...). UNIQUE (lancamento_id, indice), contiguo (enforce via app).
- **origem.cri_id (Q11b=A)**: CRI de origem. **NÃO** duplicar em `lancamento.cri_origem_id`.
- **origem_fim_cadeia.sigla_patrimonio_publico**: sigla do orgao (ex: INCRA, SPU) quando aplicavel.
- **lancamento.numero_lancamento**: numero informado pelo usuario (nao e derivado); usado para compor a sigla exibida (ex: `AV5 M123`). UNIQUE (documento_id, numero_lancamento).
- **lancamento.cartorio_transmissao_nome (Q11b)**: FREE-FORM TEXT, sem FK. Tabelionato de notas (compra e venda, etc) — pode ser qualquer um, nao precisa ser normalizado.
- **lancamento_move_event (Q14=B)**: append-only. Registra MOVE cross-chain. Lancamento NAO e mutado. `from_documento_id` e `to_documento_id` sao os D origem e destino.
- **anotacao_versao.autor_original_id (Q9=C)**: pessoa que criou a anotacao. **IMUTAVEL** (so o editor muda entre versoes, nao o autor).
- **anotacao_versao.current_marker (Q9=C)**: marca a versao atual da anotacao. `partial UNIQUE (imovel_documento_id) WHERE is_current=1`.
- **deleted_at (Q2=B)**: presente em imovel, documento, lancamento, lancamento_pessoa, imovel_documento, pessoa, anotacao_versao, cri. Soft-delete e a estrategia padrao. Hard-delete admin-only.

## 5) Observacoes sobre obrigatoriedade

- Um campo marcado como `FK` pode ser **obrigatorio ou opcional** dependendo da regra de negocio.
- A obrigatoriedade especifica esta definida no documento `docs/db/SCHEMA_CONSOLIDATED.md`.
- **UNIQUE constraints** vao via migration Drizzle (Mermaid nao suporta `UNIQUE` em declaracao de campo).
- **CHECK constraints** vao via migration Drizzle (Mermaid interpreta `--` e `|` em comentarios como relacoes — usar `text` com descricao em vez de constraint syntax).
- **Cascade conservador (Q7b=B)**: soft-delete de Imovel toca APENAS `imovel_documento` (junctions). Lancamentos, lancamento_pessoa, Documentos, Pessoas, CRIs **NAO sao tocados** (evidencia preservada).
