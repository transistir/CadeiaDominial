# Análise: OrigemFimCadeia vs FimCadeia

## Status: `FimCadeia` deve ser REMOVIDA

---

## Estrutura das Tabelas

### OrigemFimCadeia (dados operacionais)

**Arquivo:** `old/dominial/models/lancamento_models.py:151`

| Campo                      | Tipo            | Obrigatório | Descrição                                     |
| -------------------------- | --------------- | ----------- | --------------------------------------------- |
| `lancamento`               | FK → Lancamento | ✅          | Vinculado ao lançamento                       |
| `indice_origem`            | Integer         | ✅          | Índice da origem (0, 1, 2...)                 |
| `fim_cadeia`               | Boolean         | ✅          | Se é fim de cadeia                            |
| `tipo_fim_cadeia`          | CharField(50)   | Condicional | `destacamento_publico`, `outra`, `sem_origem` |
| `especificacao_fim_cadeia` | TextField       | Condicional | Especificação para tipo "outra"               |
| `classificacao_fim_cadeia` | CharField(50)   | Condicional | `origem_lidima`, `sem_origem`, `inconclusa`   |

**Constraints:**

- `unique_together = ['lancamento', 'indice_origem']`

**Validações:**

- Se `fim_cadeia = True`, então `tipo_fim_cadeia` e `classificacao_fim_cadeia` são obrigatórios
- Se `tipo_fim_cadeia = 'outra'`, então `especificacao_fim_cadeia` é obrigatório

---

### FimCadeia (catálogo de referência - REDUNDANTE)

**Arquivo:** `old/dominial/models/lancamento_models.py:204`

| Campo              | Tipo           | Descrição                                     |
| ------------------ | -------------- | --------------------------------------------- |
| `id`               | AutoField      | Primary key                                   |
| `nome`             | CharField(100) | Nome único (ex: "INCRA", "Estado da Bahia")   |
| `tipo`             | CharField(50)  | `destacamento_publico`, `outra`, `sem_origem` |
| `classificacao`    | CharField(50)  | `origem_lidima`, `sem_origem`, `inconclusa`   |
| `sigla`            | CharField(50)  | Sigla do órgão                                |
| `descricao`        | TextField      | Descrição detalhada                           |
| `ativo`            | Boolean        | Se está ativo                                 |
| `data_criacao`     | DateTime       | Auto_now_add                                  |
| `data_atualizacao` | DateTime       | Auto_now                                      |

**Métodos:**

- `get_cor_css()` - Retorna cor CSS baseada na classificação
- `get_cor_borda_css()` - Retorna cor da borda

---

## Análise de Redundância

### Problema Identificado

`FimCadeia` foi criada como um **catálogo de tipos predefinidos** para facilitar a seleção no frontend D3. porém:

1. **Nunca é usada no código ativo:**
   - Zero referências em services ativos
   - Zero referências em views/API
   - Apenas referenciada em código legado em `backups/`

2. **Reformulação já realizada:**
   - A documentação `old/docs/REFORMULACAO_FIM_CADEIA.md` (17/09/2025) mostra que a arquitetura foi reformulada
   - O sistema atual usa `OrigemFimCadeia` + formato string no campo `Lancamento.origem`
   - `FimCadeia` é resquício de uma abordagem anterior

3. **Uso real verificado no código:**
   ```python
   # old/dominial/services/lancamento_campos_service.py:345-353
   OrigemFimCadeia.objects.create(
       lancamento=lancamento,
       indice_origem=i,
       fim_cadeia=True,
       tipo_fim_cadeia=tipo_fim_cadeia,
       especificacao_fim_cadeia=especificacao_fim_cadeia,
       classificacao_fim_cadeia=classificacao_fim_cadeia
   )
   ```

---

## Veredito Final

| Tabela            | Decisão     | Justificativa                        |
| ----------------- | ----------- | ------------------------------------ |
| `OrigemFimCadeia` | **MANTER**  | Armazena dados reais dos lançamentos |
| `FimCadeia`       | **REMOVER** | Catálogo não usado, redundante       |

---

## Análise de Campos - OrigemFimCadeia

| Campo                      | Manter?    | Justificativa                                       |
| -------------------------- | ---------- | --------------------------------------------------- |
| `lancamento`               | ✅ Sim     | FK necessária para vincular ao lançamento           |
| `indice_origem`            | ✅ Sim     | Necessário para suportar múltiplas origens          |
| `fim_cadeia`               | ⚠️ Avaliar | Pode ser inferido de `tipo_fim_cadeia` não null     |
| `tipo_fim_cadeia`          | ✅ Sim     | Diferencia tipo de fim de cadeia                    |
| `especificacao_fim_cadeia` | ✅ Sim     | Necessário para tipo "outra" (sentenças, processos) |
| `classificacao_fim_cadeia` | ✅ Sim     | Usado para visualização (cores na árvore D3)        |

**Sugestão de simplificação futura:** O campo `fim_cadeia` pode ser removido e inferido como `tipo_fim_cadeia IS NOT NULL`.

---

## Tipos de Fim de Cadeia (valores possíveis)

### Tipos (`tipo_fim_cadeia`)

| Valor                  | Descrição                                         |
| ---------------------- | ------------------------------------------------- |
| `destacamento_publico` | Origem em órgão público (INCRA, Estado, União)    |
| `outra`                | Situações especiais (sentença judicial, processo) |
| `sem_origem`           | Não há origem documentada                         |

### Classificações (`classificacao_fim_cadeia`)

| Valor           | Cor D3             | Descrição                                  |
| --------------- | ------------------ | ------------------------------------------ |
| `origem_lidima` | Verde (#28a745)    | Origem legítima e documentada              |
| `sem_origem`    | Vermelho (#dc3545) | Sem origem documentada                     |
| `inconclusa`    | Amarelo (#ffc107)  | Situação inconclusive, requer investigação |

---

## Formato de Armazenamento no Campo `Lancamento.origem`

Além de `OrigemFimCadeia`, o sistema também armazena o fim de cadeia como string no campo `Lancamento.origem`:

```
Tipo:Valor:Classificação

Exemplos:
Destacamento Público:INCRA:Origem Lídima
Outra:Processo 1234567-89.2023.8.05.0001, Vara Cível:Situação Inconclusa
Sem Origem::Sem Origem
```

---

## Arquivos Relacionados

| Arquivo                                              | Propósito                       |
| ---------------------------------------------------- | ------------------------------- |
| `old/dominial/models/lancamento_models.py:151`       | Modelo OrigemFimCadeia          |
| `old/dominial/models/lancamento_models.py:204`       | Modelo FimCadeia                |
| `old/dominial/services/lancamento_campos_service.py` | Service que usa OrigemFimCadeia |
| `old/docs/REFORMULACAO_FIM_CADEIA.md`                | Documentação da reformulação    |
| `docs/cadeia-dominial/FIM_DE_CADEIA.md`              | Documentação conceitual         |

---

## Ações de Migração

### 1. Remover `FimCadeia`

```sql
-- Remover tabela do schema D1
DROP TABLE IF EXISTS fim_cadeia;
```

### 2. Manter `OrigemFimCadeia`

```sql
-- Manter com возможные simplificações futuras
CREATE TABLE origem_fim_cadeia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lancamento_id INTEGER NOT NULL REFERENCES lancamento(id),
    indice_origem INTEGER NOT NULL,
    fim_cadeia BOOLEAN DEFAULT FALSE,
    tipo_fim_cadeia TEXT CHECK(tipo_fim_cadeia IN ('destacamento_publico', 'outra', 'sem_origem')),
    especificacao_fim_cadeia TEXT,
    classificacao_fim_cadeia TEXT CHECK(classificacao_fim_cadeia IN ('origem_lidima', 'sem_origem', 'inconclusa')),
    UNIQUE(lancamento_id, indice_origem)
);
```

### 3. Possível Simplificação Futura

Remover campo `fim_cadeia` e inferir de `tipo_fim_cadeia IS NOT NULL`:

```sql
-- Migration futura
ALTER TABLE origem_fim_cadeia DROP COLUMN fim_cadeia;
```

---

## Data da Análise

2026-01-27

**Analista:** Claude Code

**Status:** Aprovado para migração - `FimCadeia` deve ser removida
