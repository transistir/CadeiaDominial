# 📚 Boas Práticas: Commitar Migrations no Django

## ✅ SIM - Migrations DEVEM ser commitadas

### Por quê?

#### 1. **Sincronização entre Desenvolvedores**
- Todos os desenvolvedores precisam aplicar as mesmas mudanças no banco
- Migrations garantem que o schema seja idêntico em todos os ambientes
- Evita conflitos e inconsistências de dados

#### 2. **Histórico de Mudanças**
- Migrations são um registro histórico do schema do banco
- Permite rastrear quando e como campos foram criados/modificados
- Essencial para auditoria e debugging

#### 3. **Deploy em Produção**
- Produção precisa aplicar as mesmas migrations que desenvolvimento
- Sem migrations versionadas, não há como sincronizar o banco
- Deploy automatizado depende das migrations no repositório

#### 4. **Rollback e Recuperação**
- Permite reverter mudanças no schema se necessário
- Facilita recuperação de problemas em produção
- Documenta todas as alterações do banco

#### 5. **CI/CD e Automação**
- Pipelines de CI precisam das migrations para testar
- Deploy automatizado executa `python manage.py migrate`
- Sem migrations versionadas, automação não funciona

## 📋 O que NÃO commitar

### ❌ NÃO commitar:
- `db.sqlite3` (banco de dados local)
- `__pycache__/` (arquivos compilados Python)
- `*.pyc` (bytecode Python)
- Arquivos temporários

### ✅ SIM, commitar:
- `dominial/migrations/*.py` (todas as migrations)
- `dominial/migrations/__init__.py` (arquivo necessário)

## 🔍 Verificação no Projeto

No seu `.gitignore`:
```gitignore
# Django
*.log
db.sqlite3          # ✅ Banco local NÃO commitado
db.sqlite3-journal

# Python
__pycache__/         # ✅ Cache NÃO commitado
*.py[cod]
```

**Migrations NÃO estão no .gitignore** ✅ - Isso está correto!

## 📦 Estrutura Correta

```
dominial/
├── migrations/
│   ├── __init__.py                    # ✅ Commitado
│   ├── 0001_initial.py                # ✅ Commitado
│   ├── 0002_alter_imovel.py           # ✅ Commitado
│   ├── ...
│   └── 0042_fix_matricula_unique_constraint.py  # ✅ Commitado
```

## 🚀 Fluxo de Trabalho Recomendado

### 1. Criar Migration
```bash
python manage.py makemigrations
```

### 2. Revisar a Migration
```bash
# Ver o SQL que será executado
python manage.py sqlmigrate dominial 0042

# Verificar se está correta
python manage.py makemigrations --check
```

### 3. Testar Localmente
```bash
python manage.py migrate
# Testar funcionalidades
```

### 4. Commit
```bash
git add dominial/migrations/0042_fix_matricula_unique_constraint.py
git commit -m "fix: Corrige constraint de matrícula"
```

### 5. Deploy
```bash
# Em produção
git pull origin main
python manage.py migrate  # Aplica a migration commitada
```

## ⚠️ Problemas se NÃO Commitar Migrations

### ❌ Problema 1: Desenvolvimento
- Dev A cria migration localmente
- Dev B não tem a migration
- Dev B tenta rodar o código → **ERRO**: "Table doesn't exist"
- Schema fica inconsistente entre desenvolvedores

### ❌ Problema 2: Produção
- Migration criada localmente
- Deploy em produção sem a migration
- Código espera campo que não existe → **ERRO**: "Column doesn't exist"
- Sistema quebra em produção

### ❌ Problema 3: CI/CD
- Pipeline tenta rodar testes
- Migration não está no repositório
- Testes falham → **ERRO**: "Migration missing"
- Deploy automatizado quebra

## ✅ Conclusão

**Migrations DEVEM ser commitadas sempre!**

É uma prática fundamental do Django e desenvolvimento profissional. Sem migrations versionadas:
- ❌ Impossível sincronizar ambientes
- ❌ Deploy quebra
- ❌ CI/CD não funciona
- ❌ Equipe não consegue trabalhar junto

**No seu caso específico:**
- ✅ `0042_fix_matricula_unique_constraint.py` DEVE ser commitado
- ✅ É parte essencial da correção da constraint
- ✅ Produção precisa dessa migration para aplicar a mudança

## 📚 Referências

- [Django Migrations Documentation](https://docs.djangoproject.com/en/stable/topics/migrations/)
- [Django Best Practices - Migrations](https://docs.djangoproject.com/en/stable/topics/migrations/#version-control)
- [Git Best Practices](https://www.atlassian.com/git/tutorials/comparing-workflows)

