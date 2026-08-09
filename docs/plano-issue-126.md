# Plano de Fix — Issue #126

**Issue:** [transistir/CadeiaDominial#126](https://github.com/transistir/CadeiaDominial/issues/126)
**Branch:** `fix/issue-126-string-none` (de `origin/develop` @ `e8ff3d2d`)
**Data:** 2026-08-06

---

## Problema

A string literal `"None"` aparece na coluna Título (e em campos adjacentes) em
vez de `"-"` (ou não aparecer). Causa raiz: imports legados persistiram
`str(None)` — a representação textual de um `None` Python — em campos
`CharField`/`TextField` anuláveis. O filtro `default_if_none` do Django só
detecta `None` real, não a string `"None"`, então ela passa direto para a
renderização.

## Estratégia

Três camadas de defesa:

1. **Limpeza de dados** — migration one-shot converte string `"None"` → `NULL`
2. **Filtro de template** — exibe `"-"` (ou suprime o bloco) para `None`, `"None"`, e vazio
3. **Normalização nas views/API** — impede que um futuro import reintroduza o bug

---

## Fase 1 — Migration de limpeza de dados

### Arquivo

`dominial/migrations/0056_normaliza_none_textual.py`

Dependência: `("dominial", "0055_add_data_presumida_documento")`

### Inventário completo de campos (corrigido pelo Claude Opus)

> ⚠️ **MUST-FIX M-2:** O plano original do Codex listava 12 campos. A revisão do
> Claude Opus identificou **10 campos adicionais** em modelos já enumerados,
> campos estes exibidos na mesma tabela com `default_if_none:"-"`.

| Modelo | Tabela | Campos |
|---|---|---|
| `Lancamento` | `dominial_lancamento` | `titulo`, `forma`, `descricao`, `origem`, `detalhes`, `observacoes`, `numero_lancamento`, `livro_transacao`, `folha_transacao`, `livro_origem`, `folha_origem` |
| `Documento` | `dominial_documento` | `origem`, `observacoes` |
| `Imovel` | `dominial_imovel` | `observacoes` |
| `Alteracoes` | `dominial_alteracoes` | `titulo`, `observacoes`, `livro`, `folha`, `livro_origem`, `folha_origem` |
| `FimCadeia` | `dominial_fimcadeia` | `descricao`, `sigla` |

**Total: 22 campos** (12 originais + 10 adicionados pela revisão).

### Código

```python
from django.db import migrations


CAMPOS_POR_MODELO = {
    "Lancamento": (
        "titulo",
        "forma",
        "descricao",
        "origem",
        "detalhes",
        "observacoes",
        "numero_lancamento",
        "livro_transacao",
        "folha_transacao",
        "livro_origem",
        "folha_origem",
    ),
    "Documento": ("origem", "observacoes"),
    "Imovel": ("observacoes",),
    "Alteracoes": (
        "titulo",
        "observacoes",
        "livro",
        "folha",
        "livro_origem",
        "folha_origem",
    ),
    "FimCadeia": ("descricao", "sigla"),
}


def normalizar_none_textual(apps, schema_editor):
    db_alias = schema_editor.connection.alias

    for model_name, campos in CAMPOS_POR_MODELO.items():
        model = apps.get_model("dominial", model_name)

        for campo in campos:
            # NICE-TO-HAVE N-4: registrar contagem antes de atualizar
            # para que o log de deploy documente o que foi destruído.
            qs = model.objects.using(db_alias).filter(**{campo: "None"})
            count = qs.count()
            if count:
                print(f"  [0056] {model_name}.{campo}: {count} linha(s) afetada(s)")
                qs.update(**{campo: None})


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("dominial", "0055_add_data_presumida_documento"),
    ]

    operations = [
        migrations.RunPython(
            normalizar_none_textual,
            migrations.RunPython.noop,
        ),
    ]
```

### Decisões

- **Apenas `"None"` exata** — não reescrever `"none"`, `"NONE"`, ou `" None "`
  sem auditar amostras primeiro (risco de alterar texto legítimo).
- **Reversão = no-op** — converter sentinela para `NULL` é logicamente
  irreversível: um `NULL` original legítimo não pode ser distinguido depois. Não
  implementar reversão que recrie `"None"`.
- **`QuerySet.update()` bypassa `save()`/signals** — comportamento correto e
  determinístico para limpeza.
- **`atomic = True`** — limpeza atômica, sem estado parcial.

### Ação pré-deploy (obrigatória)

Fazer backup do banco de produção antes de aplicar. Para Postgres:
```bash
pg_dump -t dominial_lancamento -t dominial_documento -t dominial_imovel \
        -t dominial_alteracoes -t dominial_fimcadeia > backup_pre_0056.sql
```

---

## Fase 2 — Filtro de template + helper

### Helper: `dominial/utils/formatacao_utils.py`

Adicionar ao final do arquivo:

```python
def normalizar_texto_opcional(valor, padrao=None):
    """Substitui valores textuais ausentes ou o sentinela legado 'None'."""
    if valor is None:
        return padrao

    if isinstance(valor, str):
        valor_comparacao = valor.strip()
        if not valor_comparacao or valor_comparacao == "None":
            return padrao

    return valor
```

### Re-export: `dominial/utils/__init__.py`

> ⚠️ **NICE-TO-HAVE N-3:** O `__init__.py` re-exporta todas as funções de
> `formatacao_utils` com `__all__`. Atualizar para manter a convenção do pacote.

Adicionar `normalizar_texto_opcional` ao import e ao `__all__`.

### Filtro: `dominial/templatetags/dominial_extras.py`

```python
from dominial.utils.formatacao_utils import normalizar_texto_opcional


@register.filter
def limpar_none(valor, padrao="-"):
    """Exibe o padrão para None, string 'None' ou texto vazio."""
    return normalizar_texto_opcional(valor, padrao)
```

### Regras de implementação

- **NÃO usar `@stringfilter`** — coercer input não-string antes da normalização
- **NÃO usar `mark_safe`** — autoescaping do Django deve permanecer ativo
- `padrao` configurável: `{{ valor|limpar_none:"" }}` suprime; `{{ valor|limpar_none }}` → `"-"`
- Colisão de nome: verificada — nenhum dos 9 filtros existentes em `dominial_extras.py` usa `limpar_none`

---

## Fase 3 — Templates

> ⚠️ **MUST-FIX M-1:** Dois templates fora do conjunto original dos 8 NÃO têm
> `{% load dominial_extras %}`. Usar o filtro neles sem o load causa
> `TemplateSyntaxError` (500). `{% load %}` é por-arquivo e **não** propaga via
> `{% include %}` ou `{% extends %}`.

### Templates que já têm `{% load dominial_extras %}`

#### Substituições diretas de exibição

| Arquivo | Linha | Antes | Depois |
|---|---:|---|---|
| `cadeia_dominial_tabela.html` | 243 | `{{ lancamento.titulo\|default_if_none:"-" }}` | `{{ lancamento.titulo\|limpar_none }}` |
| `cadeia_dominial.html` | 149 | `{{ lancamento.titulo\|default_if_none:"-" }}` | `{{ lancamento.titulo\|limpar_none }}` |
| `documento_detalhado.html` | 199 | `{{ lancamento.titulo\|default_if_none:"-" }}` | `{{ lancamento.titulo\|limpar_none }}` |
| `cadeia_completa_pdf.html` | 189 | `{{ lancamento.titulo\|default_if_none:"-" }}` | `{{ lancamento.titulo\|limpar_none }}` |
| `cadeia_dominial_pdf.html` | 144 | `{{ lancamento.titulo\|default_if_none:"-" }}` | `{{ lancamento.titulo\|limpar_none }}` |
| `_lancamento_resumo_card.html` | 68 | `{{ lancamento.titulo\|default:"-" }}` | `{{ lancamento.titulo\|limpar_none }}` |

Paths completos sob `templates/dominial/`.

#### Condicionais — padrão `{% with %}`

**`tronco_principal.html:131`**

```django
{# Antes #}
{% if lancamento.titulo %}
<div class="lancamento-detail">
    <strong>Título:</strong> {{ lancamento.titulo }}
</div>
{% endif %}

{# Depois #}
{% with titulo=lancamento.titulo|limpar_none:"" %}
    {% if titulo %}
    <div class="lancamento-detail">
        <strong>Título:</strong> {{ titulo }}
    </div>
    {% endif %}
{% endwith %}
```

**`documento_lancamentos.html:97`**

```django
{# Antes #}
{% if lancamento.titulo %}
    <div class="detalhe-item">
        <span class="detalhe-label">Título:</span>
        <span class="detalhe-valor">{{ lancamento.titulo|truncatechars:25 }}</span>
    </div>
{% endif %}

{# Depois #}
{% with titulo=lancamento.titulo|limpar_none:"" %}
    {% if titulo %}
        <div class="detalhe-item">
            <span class="detalhe-label">Título:</span>
            <span class="detalhe-valor">{{ titulo|truncatechars:25 }}</span>
        </div>
    {% endif %}
{% endwith %}
```

**`lancamento_detail.html:132-135` e `:362-365`** — dois blocos de exibição,
aplicar o mesmo padrão `{% with titulo=... %}`.

### Templates que PRECISAM de `{% load dominial_extras %}` adicionado

#### `lancamento_form.html`

> ⚠️ **MUST-FIX M-1 + NICE-TO-HAVE N-2:** Este template carrega apenas
> `{% load static %}` (linha 2). Deve receber `{% load dominial_extras %}`.
> Além disso, o `{% if %}` composto precisa do rewrite completo, não apenas do
> filtro na saída — senão `"None"` ainda é truthy e o `elif` fallback é pulado.

```django
{# Linha 2: adicionar #}
{% load dominial_extras %}

{# Linha ~117: antes #}
{% if modo_edicao and lancamento.titulo %}
    ... value="{{ lancamento.titulo }}" ...
{% elif form_data and form_data.titulo %}
    ...
{% endif %}

{# Depois #}
{% with titulo_limpo=lancamento.titulo|limpar_none:"" %}
    {% if modo_edicao and titulo_limpo %}
        ... value="{{ titulo_limpo }}" ...
    {% elif form_data and form_data.titulo %}
        ...
    {% endif %}
{% endwith %}
```

#### `_cartorio_form.html`

> **NICE-TO-HAVE N-1:** Este template é **dead code** — zero referências no
> repo (nenhum `{% include %}`, nenhum `render()`). Editá-lo é trabalho
> desperdiçado. **Remover do escopo deste fix.** Deletar o órfão pode ser feito
> em limpeza separada.

---

## Fase 4 — Views

### `cadeia_dominial_views.py`

**`cadeia_dominial_dados` — linha 213:**

```python
# Antes
'titulo': lancamento.titulo or '',

# Depois
'titulo': normalizar_texto_opcional(lancamento.titulo, ''),
```

Aplicar aos campos suscetíveis adjacentes:

```python
'forma': normalizar_texto_opcional(lancamento.forma, ''),
'descricao': normalizar_texto_opcional(lancamento.descricao, ''),
'titulo': normalizar_texto_opcional(lancamento.titulo, ''),
'observacoes': normalizar_texto_opcional(lancamento.observacoes, ''),
'numero_lancamento': normalizar_texto_opcional(lancamento.numero_lancamento, ''),
'livro_transacao': normalizar_texto_opcional(lancamento.livro_transacao, ''),
'folha_transacao': normalizar_texto_opcional(lancamento.folha_transacao, ''),
```

Também normalizar `documento.origem` no ponto de serialização da árvore.

**Excel export — linha 582:**

```python
# Antes
value=lancamento.titulo or "-"

# Depois
value=normalizar_texto_opcional(lancamento.titulo, "-")
```

### `api_views.py`

> ⚠️ **MUST-FIX M-3:** O plano original cobria 5 campos mas omitia 3 que o JS
> renderiza com `|| '-'`: `numero_lancamento`, `livro_transacao`,
> `folha_transacao`. Estes são serializados em `api_views.py:372,384,385`.

**`get_cadeia_dominial_atualizada` — linha 375:**

```python
# Antes
'titulo': lancamento.titulo,

# Depois
'titulo': normalizar_texto_opcional(lancamento.titulo),
```

Usar o default `None` preserva a semântica da API (ausência = JSON `null`).

Lista completa de normalização:

```python
'forma': normalizar_texto_opcional(lancamento.forma),
'titulo': normalizar_texto_opcional(lancamento.titulo),
'descricao': normalizar_texto_opcional(lancamento.descricao),
'origem': normalizar_texto_opcional(lancamento.origem),
'observacoes': normalizar_texto_opcional(lancamento.observacoes),
'numero_lancamento': normalizar_texto_opcional(lancamento.numero_lancamento),       # M-3
'livro_transacao': normalizar_texto_opcional(lancamento.livro_transacao),             # M-3
'folha_transacao': normalizar_texto_opcional(lancamento.folha_transacao),             # M-3
```

`detalhes` não é serializado por este endpoint (verificado).

Isto também protege os paths JS em `static/dominial/js/cadeia_dominial_tabela.js`
(linhas 451, 454, 455) onde `"None"` é truthy.

---

## Fase 5 — Scripts (opcional, fora da branch)

Os dois scripts são arquivos untracked em outra worktree, não fonte do bug:

- `scripts/exporta_tapayuna.py`
- `scripts/sync_test_to_prod.py`

Ambos já tratam `None` real corretamente via `query_json()` (Postgres `NULL` →
Python `None`). Não aplicar mudanças neles nesta branch. Se permanecerem
operacionais, endurecer os SELECTs com `NULLIF`:

```sql
NULLIF(titulo, 'None') AS titulo,
NULLIF(forma, 'None') AS forma,
NULLIF(descricao, 'None') AS descricao,
NULLIF(origem, 'None') AS origem,
NULLIF(detalhes, 'None') AS detalhes,
NULLIF(observacoes, 'None') AS observacoes,
NULLIF(numero_lancamento, 'None') AS numero_lancamento,
NULLIF(livro_transacao, 'None') AS livro_transacao,
NULLIF(folha_transacao, 'None') AS folha_transacao
```

`NULLIF` escopado por campo é preferível a alterar o `esc()` genérico — mudança
global poderia afetar colunas legítimas como nomes ou identificadores.

---

## Fase 6 — Testes

### Filtro e helper — `dominial/tests/test_issue_126_string_none.py`

Usar `SimpleTestCase` para testes diretos do filtro/helper.

```python
- test_limpar_none_converte_none_real_em_hifen
- test_limpar_none_converte_string_none_em_hifen
- test_limpar_none_aceita_padrao_personalizado
- test_limpar_none_trata_string_vazia_e_espacos_como_ausente
- test_limpar_none_preserva_texto_valido
- test_limpar_none_preserva_zero_e_false
- test_normalizador_pode_retornar_none_para_json
- test_condicional_de_titulo_nao_renderiza_string_none
```

O teste condicional deve renderizar um fragmento de template com
`{% load dominial_extras %}` e verificar que nem `None` real nem `"None"` entram
no bloco de título.

### Endpoints

```python
- test_cadeia_dominial_dados_serializa_titulo_none_textual_como_vazio
- test_api_cadeia_atualizada_serializa_titulo_none_textual_como_null
- test_api_normaliza_demais_campos_textuais_suscetiveis          # inclui M-3
```

### Migration — `dominial/tests/test_migracao_issue_126_string_none.py`

Seguir a convenção existente de `MigrationExecutor` + `TransactionTestCase`
(cf. `test_migracao_identidade_canonica.py`).

```python
migrate_from = [("dominial", "0055_add_data_presumida_documento")]
migrate_to = [("dominial", "0056_normaliza_none_textual")]
```

Testes recomendados:

```python
- test_migracao_converte_todos_os_campos_auditados_em_null
    # Seed de instâncias de Lancamento, Documento, Imovel, Alteracoes, FimCadeia
    # com "None" em TODOS os 22 campos do inventário (incluindo os 10 do M-2)
    # Migrar forward e assert que cada valor é Python None
- test_migracao_preserva_textos_validos_e_vazios
    # Seed: texto comum, "", None real, "none", " None "
    # Assert: apenas "None" exata vira NULL
- test_migracao_e_idempotente
    # Invocar a função forward duas vezes; segunda vez reporta 0 linhas
- test_reversao_nao_recria_string_none
    # Migrar backward com no-op; confirmar que valores limpos permanecem NULL
- test_migracao_usa_todos_os_modelos_historicos
    # Garantir que a migration é independente de imports de model atuais
```

Rodar a suite focada depois a suite completa de `dominial.tests`.

---

## Avaliação de Riscos

| Risco | Mitigação |
|---|---|
| **Ambiguidade de dados** | Título genuinamente pretendido como a palavra inglesa `"None"` seria perdido. Auditar contagens (`N-4`) e IDs representativos antes do deploy. |
| **Locking da migration** | Cada `UPDATE` escaneia campo nullable sem índice dedicado. Em Postgres prod pode bloquear brevemente; checar contagens antes de escolher janela de deploy. |
| **Atomicidade** | `atomic = True` — limpeza sem estado parcial. |
| **Signals** | `QuerySet.update()` bypassa `save()` e signals intencionalmente — correto para limpeza determinística. |
| **Rollback** | Logicamente irreversível: `NULL` original não distinguível de `NULL` limpo. Não implementar reversão que recrie `"None"`. Código pode ser revertido deixando dados limpos intactos; restauração completa requer backup pré-deploy. |
| **Race condition** | Importer externo pode recriar valores sujos após a migration. Deployar hardening de import junto ou imediatamente após. |
| **Compatibilidade de apresentação** | Filtro configurável mantém blocos condicionais ocultos com `padrao=""` e exibe `"-"` em células de tabela. |
| **Mudança visual de string vazia** (`N-5`) | `default_if_none:"-"` renderizava `""` (célula em branco) para título vazio; `limpar_none` renderiza `"-"` pois trata `""`/whitespace como ausente. Melhoria defensável, mas é mudança visível além do escopo da issue — flagada aqui. |
| **Compatibilidade de API** | Retornar JSON `null` da API (não `""`) preserva semântica atual. |
| **Escaping** | Filtro novo deve manter autoescaping normal do Django; não usar `safe` internamente. |

---

## Histórico de Revisão

| Agente | Modelo | Papel | Veredito |
|---|---|---|---|
| Codex | GPT-5.6-sol (xhigh) | Investigação read-only + plano | `VERDICT: PLAN COMPLETE` |
| Claude Code | Opus 5 | Revisão de arquitetura/corretude | `14 PASS / 3 MUST-FIX / 5 NICE-TO-HAVE — REJEITA` |

### Correções incorporadas neste plano final

| ID | Severidade | Correção | Onde |
|---|---|---|---|
| M-1 | MUST-FIX | Adicionar `{% load dominial_extras %}` em `lancamento_form.html` | Fase 3 |
| M-2 | MUST-FIX | Adicionar 10 campos nullable à migration (total: 22) | Fase 1 |
| M-3 | MUST-FIX | Adicionar `numero_lancamento`, `livro_transacao`, `folha_transacao` à normalização da API | Fase 4 |
| N-1 | NICE | Remover `_cartorio_form.html` do escopo (dead code) | Fase 3 |
| N-2 | NICE | Especificar rewrite completo do `{% if %}` no form template | Fase 3 |
| N-3 | NICE | Atualizar `utils/__init__.py` com re-export | Fase 2 |
| N-4 | NICE | Adicionar logging de contagem na migration | Fase 1 |
| N-5 | NICE | Flagar mudança visual `""` → `"-"` | Riscos |

---

## Checklist de Implementação

- [ ] **Fase 1:** Criar `0056_normaliza_none_textual.py` com 22 campos
- [ ] **Fase 2:** Adicionar `normalizar_texto_opcional` em `formatacao_utils.py`
- [ ] **Fase 2:** Atualizar `utils/__init__.py` (`N-3`)
- [ ] **Fase 2:** Registrar filtro `limpar_none` em `dominial_extras.py`
- [ ] **Fase 3:** Substituir em 6 templates de exibição direta
- [ ] **Fase 3:** Rewrite `{% with %}` em `tronco_principal.html`, `documento_lancamentos.html`, `lancamento_detail.html` (×2)
- [ ] **Fase 3:** Adicionar `{% load %}` + rewrite completo em `lancamento_form.html` (M-1, N-2)
- [ ] **Fase 4:** Normalizar 8 campos em `cadeia_dominial_views.py:213`
- [ ] **Fase 4:** Normalizar Excel export em `cadeia_dominial_views.py:582`
- [ ] **Fase 4:** Normalizar 8 campos em `api_views.py:375` (inclui M-3)
- [ ] **Fase 6:** Criar `test_issue_126_string_none.py` (8 testes)
- [ ] **Fase 6:** Criar `test_migracao_issue_126_string_none.py` (5 testes)
- [ ] Rodar `python manage.py test dominial.tests`
- [ ] **Pré-deploy:** Backup das 5 tabelas afetadas
