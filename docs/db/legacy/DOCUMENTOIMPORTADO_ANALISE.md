> **LEGACY / REFERENCIA**: este documento foi consolidado. Fonte de verdade: `docs/db/SCHEMA_CONSOLIDATED.md` e ERD em `docs/db/SCHEMA_CONSOLIDATED_ERD.*`.
>
> Este arquivo e mantido apenas para contexto historico e pode conter regras desatualizadas.

# Análise: dominial_documentoimportado

## Propósito Original

Tabela criada para rastrear documentos importados de outras cadeias dominiais.

**Funcionalidades propostas:**

- Identificar quais documentos foram importados
- Rastrear de qual imóvel foram importados
- Registrar quem fez a importação e quando
- Evitar importações duplicadas

## Estrutura

| Campo           | Tipo           | Descrição               |
| --------------- | -------------- | ----------------------- |
| documento       | FK → Documento | Documento importado     |
| imovel_origem   | FK → Imovel    | Imóvel de origem        |
| data_importacao | DateTime       | Data/hora da importação |
| importado_por   | FK → User      | Usuário que importou    |

## Uso na Visualização D3

No frontend (`cadeia_dominial_d3.js`), o flag `is_importado` controla:

- Borda laranja
- Badge com "✓"
- Linhas tracejadas
- Tooltip com informações de importação

## Problema Identificado

**CRÍTICO:** O campo `is_importado` está **hardcoded como `False`** no backend:

```python
# Em hierarquia_arvore_service.py, _criar_no_documento()
'is_importado': False,  # Sempre False!
```

**Não existe nenhum lugar no código que seta `is_importado = True`.**

A funcionalidade de visualização diferenciada para documentos importados **nunca funcionou**.

## Veredito: REMOVER

### Justificativa

1. Documentos importados devem ser tratados igualmente aos outros no novo sistema
2. A diferença é apenas a sequência de lançamento
3. A funcionalidade de cor diferenciada nunca foi implementada
4. Não há necessidade de auditoria de "quem importou quando"
5. O código que usaria essa tabela (`DocumentoImportadoService`) também não é usado

### Impacto da Remoção

- Backend: Remover modelo `DocumentoImportado` e service `DocumentoImportadoService`
- Frontend: Remover estilos e badges para `is_importado` (opcional, para limpar código)

### Alternativa Futura

Se precisar identificar documentos importados, adicionar flag booleano simples no modelo `Documento`:

```sql
-- No modelo Documento
foi_importado BOOLEAN DEFAULT FALSE
```

A origem pode ser determinada pela própria cadeia através de `Lancamento.documento_origem`.

## Arquivos Relacionados

| Arquivo                                             | Propósito                |
| --------------------------------------------------- | ------------------------ |
| `old/dominial/models/documento_importado_models.py` | Modelo Django            |
| `backups/services/documento_importado_service.py`   | Service (não usado)      |
| `scripts/pg_sqlite_migration/config/tables.yaml`    | Configuração de migração |
| `static/dominial/js/cadeia_dominial_d3.js`          | Visualização D3          |

---

**Data da análise:** 2026-01-27
**Analista:** Claude Code
**Status:** Aprovado para remoção
