> **LEGACY / REFERENCIA**: este documento foi consolidado. Fonte de verdade: `docs/db/SCHEMA_CONSOLIDATED.md` e ERD em `docs/db/SCHEMA_CONSOLIDATED_ERD.*`.
>
> Este arquivo e mantido apenas para contexto historico e pode conter regras desatualizadas.

# dominial_registrotipo

## Status: **REMOVER** ❌

Tabela de legado do Django, utilizada como lookup table para `Alteracoes.registro_tipo`. Não está sendo usada no novo modelo.

---

## Análise

### Origem

- **Arquivo**: `old/dominial/models/alteracao_models.py:17`
- **Módulo**: `alteracao_models.py`
- **Criação**: Migration `0001_initial.py`

### Estrutura

| Campo  | Tipo           | Descrição                |
| ------ | -------------- | ------------------------ |
| `id`   | AutoField      | PK                       |
| `tipo` | CharField(100) | Nome do tipo de registro |

### Relacionamento

- FK em `Alteracoes.registro_tipo` (opcional, `null=True, blank=True`)

```python
class RegistroTipo(models.Model):
    id = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=100)

    def __str__(self):
        return self.tipo
```

---

## Motivo da Remoção

1. **Tabela vazia/sem dados**: Não há dados populados nesta tabela
2. **Funcionalidade duplicada**: `LancamentoTipo` já cobre os tipos de lançamento (registro, averbação, inicio_matricula)
3. **Sem uso ativo**:
   - Não há APIs, views ou services usando `RegistroTipo`
   - Campo `registro_tipo` em `Alteracoes` é opcional
4. **Migração já realizada**: O modelo `Lancamento` substitui `Alteracoes` completamente

### Análise de uso no código legado

```python
# Em alteracao_models.py - linha 41
registro_tipo = models.ForeignKey(RegistroTipo, on_delete=models.CASCADE, null=True, blank=True)

# Campo é opcional e nunca populado
```

### Substituto no novo modelo

| Legado                                      | Novo Modelo  | Campo                     |
| ------------------------------------------- | ------------ | ------------------------- |
| `Alteracoes.registro_tipo` → `RegistroTipo` | `Lancamento` | `tipo` → `LancamentoTipo` |

---

## Verificações Realizadas

- [x] Não há referências em views/API
- [x] Não há referências em services
- [x] Não há referências em templates
- [x] Tabela está vazia ou sem dados
- [x] Funcionalidade coberta por `LancamentoTipo`

---

## Ações de Migração

### Remover do schema do banco

A tabela `dominial_registrotipo` não deve ser migrada para o novo banco SQLite.

### Verificar antes da remoção

```bash
# Verificar se há dados na tabela
python manage.py shell -c "from dominial.models import RegistroTipo; print(f'Registros: {RegistroTipo.objects.count()}')"
```

---

## Data da Análise

2026-01-27
