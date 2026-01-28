> **LEGACY / REFERENCIA**: este documento foi consolidado. Fonte de verdade: `docs/db/SCHEMA_CONSOLIDATED.md` e ERD em `docs/db/SCHEMA_CONSOLIDATED_ERD.*`.
>
> Este arquivo e mantido apenas para contexto historico e pode conter regras desatualizadas.

# Análise: dominial_documento

## Status: **ALTERAÇÃO NECESSÁRIA** ⚠️

Tabela principal do sistema. Algumas colunas podem ser simplificadas/removidas para migração.

---

## Schema Atual

| Campo                    | Tipo               | Descrição                                          |
| ------------------------ | ------------------ | -------------------------------------------------- |
| id                       | AutoField          | PK                                                 |
| numero                   | varchar(50)        | Número do documento (pode conter letra do tipo)    |
| data                     | DateField          | Data do documento                                  |
| livro                    | varchar(50)        | Livro                                              |
| folha                    | varchar(50)        | Folha                                              |
| observacoes              | TextField          | Observações                                        |
| data_cadastro            | DateField          | Data de cadastro automático                        |
| cartorio_id              | FK → Cartorios     | Cartório do documento                              |
| imovel_id                | FK → Imovel        | Imóvel associado                                   |
| tipo_id                  | FK → DocumentoTipo | Tipo: transcrição/matrícula                        |
| **origem**               | TextField          | **MENSAGEM AUTOMÁTICA ERRADA - REMOVER**           |
| **nivel_manual**         | Integer            | **DADO DE VISUALIZAÇÃO - REMOVER**                 |
| cri_atual_id             | FK → Cartorios     | CRI atual do documento                             |
| cri_origem_id            | FK → Cartorios     | CRI de origem (documentos criados automaticamente) |
| classificacao_fim_cadeia | varchar(50)        | Classificação de fim de cadeia                     |
| sigla_patrimonio_publico | varchar(50)        | Sigla do patrimônio público                        |

---

## Alterações Propostas

### 1. Remover `nivel_manual` ✅

**Justificativa:** Campo de visualização, não de negócio. O nível do documento na árvore D3 deve ser calculado dinamicamente.

**Impacto:**

- Backend: Remover do modelo `Documento`
- Frontend: Ajustar `hierarquia_arvore_service.py` para calcular nível automaticamente

---

### 2. Remover `origem` ✅

**Justificativa:** Campo com mensagem automática errada, não tem utilidade.

**Verificação:** Confirmado pelo analista - pode remover sem dúvidas.

**Impacto:**

- Backend: Remover do modelo `Documento`
- Frontend: Remover referências em templates/views

---

### 3. Normalizar `numero` ⚠️

**Problema:** Contém letra do tipo misturada (ex: `"M123"`, `"123A"`)

**Solução:** Extrair letras para campo `tipo_id`, deixar `numero` apenas numérico

**Exemplo de transformação:**

```sql
-- Antes
numero = 'M12345' (tipo='matricula')

-- Depois
numero = '12345'
tipo_id = (matricula)
```

**Observação:** Requer análise de dados antes da migration para garantir que a extração funciona para todos os registros.

---

### 4. Renomear `observacoes` → `origem_lancamento` ⚠️

**Proposta:** Renomear para nome mais semântico

**Alternativas:**

- `origem_lancamento` - se só guarda info de origem
- Manter `observacoes` - se guarda observações diversas

**Recomendação:** Aguardar definição do usuário sobre o uso real deste campo.

---

### 5. Manter `cri_origem` e `cri_atual` 🤔

**Uso atual:** Rastrear CRI ao longo da cadeia dominial

**Exemplo de fluxo:**

```
DocumentoTranscrição(CRI=Santana)
  → cria Matrícula(CRI_origem=Santana, CRI_atual=Centro)
  → imóvel agora registrado no Centro
```

**Decisão:** Manter por enquanto. Se no novo sistema só precisar do CRI atual, pode unificar depois.

---

## Schema Proposto

```sql
CREATE TABLE IF NOT EXISTS "dominial_documento" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "numero" varchar(50) NOT NULL,          -- ALTERAR: só números, sem letra
    "data" date NOT NULL,
    "livro" varchar(50) NOT NULL,
    "folha" varchar(50) NOT NULL,
    "observacoes" text NULL,                -- RENOMEAR: origem_lancamento?
    "data_cadastro" date NOT NULL,
    "cartorio_id" bigint NOT NULL,          -- MANTER: cartório do documento
    "imovel_id" integer NOT NULL,
    "tipo_id" bigint NOT NULL,              -- MANTER: transcrição/matrícula
    -- "origem" text NULL,                  -- REMOVIDO: mensagem automática errada
    -- "nivel_manual" integer NULL,         -- REMOVIDO: dado de visualização
    "cri_atual_id" bigint NULL,             -- MANTER: CRI atual
    "cri_origem_id" bigint NULL,            -- MANTER: CRI de origem
    "classificacao_fim_cadeia" varchar(50) NULL,
    "sigla_patrimonio_publico" varchar(50) NULL
);
```

---

## Ações de Migração

### Antes da Migração (Django)

1. **Verificar dados do `numero`:**

```python
# Verificar se extração de letras funciona para todos
Documento.objects.all().values_list('numero', 'tipo__tipo')
```

2. **Exportar dados existentes:**

```bash
python manage.py dumpdata dominial.Documento > documento_backup.json
```

### Durante Migração (tables.yaml)

```yaml
# Remover campos do schema
dominial_documento: v_dominial_documento
```

### Depois da Migração (Schema novo)

1. Criar migration para normalizar `numero`
2. Remover campos `nivel_manual` e `origem`
3. Renomear `observacoes` se necessário

---

## Comparativo: Antes x Depois

| Campo                    | Antes    | Depois                 |
| ------------------------ | -------- | ---------------------- |
| id                       | ✅       | ✅                     |
| numero                   | `"M123"` | `"123"`                |
| data                     | ✅       | ✅                     |
| livro                    | ✅       | ✅                     |
| folha                    | ✅       | ✅                     |
| observacoes              | ✅       | → `origem_lancamento`? |
| data_cadastro            | ✅       | ✅                     |
| cartorio_id              | ✅       | ✅                     |
| imovel_id                | ✅       | ✅                     |
| tipo_id                  | ✅       | ✅                     |
| origem                   | ✅       | ❌ **REMOVIDO**        |
| nivel_manual             | ✅       | ❌ **REMOVIDO**        |
| cri_atual_id             | ✅       | ✅                     |
| cri_origem_id            | ✅       | ✅                     |
| classificacao_fim_cadeia | ✅       | ✅                     |
| sigla_patrimonio_publico | ✅       | ✅                     |

---

## Decisões Pendentes

| Item                            | Status   | Quem decide |
| ------------------------------- | -------- | ----------- |
| Renomear `observacoes`          | Pendente | Usuário     |
| Manter `cri_origem`/`cri_atual` | Pendente | Usuário     |

---

**Data da análise:** 2026-01-27
**Analista:** Claude Code
**Status:** Aguardando validação das decisões pendentes
