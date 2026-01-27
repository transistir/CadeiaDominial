# dominial_alteracoes

## Status: **REMOVER** ❌

Tabela de legado do Django. Já foi migrada para o novo modelo `Lancamento` + `Documento`.

---

## Análise

### Origem

- **Arquivo**: `old/dominial/models/alteracao_models.py`
- **Módulo**: `alteracao_models.py`
- **Criação**: Migration `0001_initial.py`

### Modelos relacionados

| Modelo           | Propósito                                    |
| ---------------- | -------------------------------------------- |
| `Alteracoes`     | Tabela principal de alterações               |
| `AlteracoesTipo` | Tipos: registro, averbacao, nao_classificado |
| `RegistroTipo`   | Tipos de registro (legado)                   |
| `AverbacoesTipo` | Tipos de averbação (legado)                  |

### Motivo da remoção

1. **Migração já realizada**: Comando `migrate_documento_lancamento.py` transfere dados para `Lancamento` + `Documento`
2. **Sem uso ativo**: Não há views, services ou APIs usando este modelo
3. **Funcionalidade duplicada**: `Lancamento` substitui completamente `Alteracoes`
4. **Admin básico**: Apenas registro padrão no Django admin

### Mapeamento para novo modelo

| Campo (legado)      | Novo modelo          | Campo (novo)             |
| ------------------- | -------------------- | ------------------------ |
| `tipo_alteracao_id` | Lancamento           | `tipo` → LancamentoTipo  |
| `data_alteracao`    | Lancamento/Documento | `data`                   |
| `transmitente`      | Lancamento           | `transmitente` → Pessoas |
| `adquirente`        | Lancamento           | `adquirente` → Pessoas   |
| `valor_transacao`   | Lancamento           | `valor_transacao`        |
| `area`              | Lancamento           | `area`                   |
| `cartorio`          | Documento            | `cartorio` → Cartorios   |
| `livro`/`folha`     | Documento            | `livro`/`folha`          |

---

## Ações de migração

### Remover de `tables.yaml`

```yaml
# Remover linha:
dominial_alteracoes: v_dominial_alteracoes
```

### Remover de `04_copy_db_to_sqlite.py`

```python
# Remover linha:
"dominial_alteracoes",
```

### Verificar dados antes da remoção

```bash
# Verificar se há dados pendentes de migração
python manage.py shell -c "from dominial.models import Alteracoes; print(f'Registros: {Alteracoes.objects.count()}')"
```

---

## Data da análise

2026-01-27
