> **LEGACY / REFERENCIA**: este documento foi consolidado. Fonte de verdade: `docs/db/SCHEMA_CONSOLIDATED.md` e ERD em `docs/db/SCHEMA_CONSOLIDATED_ERD.*`.
>
> Este arquivo e mantido apenas para contexto historico e pode conter regras desatualizadas.

# Análise: dominial_tis_imovel

## Status: **REMOVER** ✅

Tabela many-to-many entre TIs e Imóveis, mas é **redundante** e **não utilizada**.

---

## Estrutura Atual

| Campo         | Tipo        | Descrição        |
| ------------- | ----------- | ---------------- |
| id            | AutoField   | PK               |
| tis_codigo_id | FK → TIs    | TIs associada    |
| imovel_id     | FK → Imovel | Imóvel associado |

**Schema SQL:**

```sql
CREATE TABLE "dominial_tis_imovel" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "imovel_id" integer NOT NULL,
    "tis_codigo_id" integer NOT NULL
);
```

---

## Problema Identificado

### Redundância com `Imovel.terra_indigena_id`

O modelo `Imovel` já tem uma FK direta para `TIs`:

```python
# Em imovel_models.py
class Imovel(models.Model):
    terra_indigena_id = models.ForeignKey('TIs', on_delete=models.PROTECT)
```

**Cada imóvel já aponta para uma TI diretamente através de `terra_indigena_id`.**

A tabela `TIs_Imovel` seria necessária apenas se:

- Um imóvel pudesse pertencer a **múltiplas** TIs
- Uma TI pudesse ter **múltiplos** imóveis de forma many-to-many

Mas isso **nunca foi implementado** e a tabela está vazia.

---

## Verificação de Uso

| Onde      | Resultado           |
| --------- | ------------------- |
| Services  | ❌ Não encontrado   |
| Views     | ❌ Não encontrado   |
| Queries   | ❌ Não encontrado   |
| Templates | ❌ Não encontrado   |
| Dados     | ❌ **Tabela vazia** |

**Conclusão:** A tabela `TIs_Imovel` nunca foi utilizada em produção.

---

## Veredito: **REMOVER**

### Justificativa

1. **Redundância:** `Imovel.terra_indigena_id` já conecta imóvel → TI
2. **Sem uso:** Nenhum service/view/query usa essa tabela
3. **Tabela vazia:** Não há dados para migrar
4. **Modelos relacionados:** O modelo `TIs_Imovel` existe mas nunca foi populado

---

## Ações de Migração

### 1. Remover do `tables.yaml`

```yaml
# Remover linha:
dominial_tis_imovel: v_dominial_tis_imovel
```

### 2. Remover modelo Django

```python
# Remover de old/dominial/models/tis_models.py
class TIs_Imovel(models.Model):
    tis_codigo = models.ForeignKey(TIs, on_delete=models.CASCADE)
    imovel = models.ForeignKey('Imovel', on_delete=models.CASCADE)
```

### 3. Remover do `models/__init__.py`

```python
# Remover importação e exportação:
from .tis_models import TIs_Imovel
```

### 4. Remover migrations (opcional)

```bash
# Remover referências em:
old/dominial/migrations/0001_initial.py
```

---

## Arquivos Relacionados

| Arquivo                                   | Propósito                          |
| ----------------------------------------- | ---------------------------------- |
| `old/dominial/models/tis_models.py`       | Modelo `TIs_Imovel`                |
| `old/dominial/models/imovel_models.py`    | FK `terra_indigena_id` em `Imovel` |
| `old/dominial/models/__init__.py`         | Exportação do modelo               |
| `old/dominial/migrations/0001_initial.py` | Criação da tabela                  |
| `schema.cleaned.core.no-auth.no-fk.sql`   | Schema SQL                         |

---

**Data da análise:** 2026-01-27
**Analista:** Claude Code
**Status:** Aprovado para remoção
