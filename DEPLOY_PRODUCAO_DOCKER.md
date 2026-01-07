# 🚀 Deploy em Produção - Docker Compose

## ⚡ Passos Rápidos (7 minutos)

### 1. Backup (OBRIGATÓRIO - 2 min)

```bash
# No diretório do projeto (onde está docker-compose.yml)
cd /caminho/do/projeto

# Backup do banco via Docker
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup_antes_migracao_matricula_$(date +%Y%m%d_%H%M%S).sql

# Verificar se foi criado
ls -lh backup_antes_migracao_matricula_*.sql
```

### 2. Atualizar Código (1 min)

```bash
# Atualizar código do repositório
git pull origin main
```

### 3. Verificar Dados (1 min)

```bash
# AGORA o comando existe (depois do git pull)
docker-compose exec web python manage.py verificar_matricula_constraint
```

**✅ Resultado esperado**: "NENHUM PROBLEMA ENCONTRADO! A migração pode ser aplicada com segurança!"

**❌ Se houver duplicatas**: Resolver antes de continuar!

### 4. Reconstruir Container (se necessário - 1 min)

```bash
# Se houver mudanças no código, reconstruir
docker-compose up -d --build web
```

### 5. Aplicar Migração (1 min)

```bash
# Aplicar migração
docker-compose exec web python manage.py migrate
```

### 6. Verificar Migração (30 seg)

```bash
# Verificar se foi aplicada
docker-compose exec web python manage.py showmigrations dominial | grep 0042
```

**✅ Resultado esperado**: `[X] 0042_fix_matricula_unique_constraint`

### 7. Verificar Constraints no Banco (30 seg)

```bash
# Verificar constraint no PostgreSQL via Docker
docker-compose exec db psql -U $DB_USER -d $DB_NAME -c "\d dominial_imovel" | grep -E "(unique|index)"
```

**✅ Deve mostrar**:
- `unique_matricula_por_cartorio` (constraint)
- `dom_imovel_mat_cart_idx` (index)

### 8. Reiniciar Serviços (30 seg)

```bash
# Reiniciar web (se necessário)
docker-compose restart web

# Verificar logs
docker-compose logs web --tail=20 | grep -i error
```

### 9. Teste Rápido (1 min)

1. Acessar: `https://cadeiadominial.com.br`
2. Tentar cadastrar imóvel com matrícula existente em **OUTRO cartório** ✅ (deve funcionar)
3. Tentar cadastrar no **MESMO cartório** ❌ (deve dar erro claro)

## 📋 Script Completo (Copy & Paste)

```bash
#!/bin/bash
# Deploy - Migração de Constraint de Matrícula (Docker)

set -e

echo "🚀 Deploy - Migração de Constraint de Matrícula"
echo "================================================"

# 1. Backup
echo "📦 1. Criando backup..."
BACKUP_FILE="backup_antes_migracao_matricula_$(date +%Y%m%d_%H%M%S).sql"
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > "$BACKUP_FILE"
echo "✅ Backup criado: $BACKUP_FILE"
ls -lh "$BACKUP_FILE"

# 2. Atualizar código
echo "📥 2. Atualizando código..."
git pull origin main

# 3. Reconstruir container (se necessário)
echo "🔨 3. Reconstruindo container..."
docker-compose up -d --build web

# 4. Verificar dados
echo "🔍 4. Verificando dados..."
docker-compose exec web python manage.py verificar_matricula_constraint

# 5. Aplicar migração
echo "🚀 5. Aplicando migração..."
docker-compose exec web python manage.py migrate

# 6. Verificar migração
echo "✅ 6. Verificando migração..."
docker-compose exec web python manage.py showmigrations dominial | grep 0042

# 7. Verificar constraints
echo "🔍 7. Verificando constraints..."
docker-compose exec db psql -U $DB_USER -d $DB_NAME -c "\d dominial_imovel" | grep -E "(unique|index)"

# 8. Reiniciar
echo "🔄 8. Reiniciando serviço..."
docker-compose restart web

# 9. Verificar logs
echo "📋 9. Verificando logs..."
sleep 3
docker-compose logs web --tail=20

echo ""
echo "✅ Deploy concluído!"
echo "💾 Backup salvo em: $BACKUP_FILE"
```

## ⚠️ Se Algo Der Errado

### Erro: "Matrículas duplicadas no mesmo cartório"

```bash
# Ver detalhes
docker-compose exec web python manage.py verificar_matricula_constraint

# Resolver duplicatas manualmente no banco
docker-compose exec db psql -U $DB_USER -d $DB_NAME

# Depois tentar migração novamente
docker-compose exec web python manage.py migrate
```

### Rollback (Se Necessário)

```bash
# 1. Restaurar backup
docker-compose exec -T db psql -U $DB_USER -d $DB_NAME < backup_antes_migracao_YYYYMMDD_HHMMSS.sql

# 2. Reverter código (se necessário)
git revert HEAD

# 3. Reconstruir e reiniciar
docker-compose up -d --build web
```

## ✅ Checklist Final

- [ ] Backup criado e verificado
- [ ] Código atualizado (`git pull`)
- [ ] Container reconstruído (se necessário)
- [ ] Verificação de dados executada (sem duplicatas)
- [ ] Migração aplicada (`migrate`)
- [ ] Migração verificada (`showmigrations`)
- [ ] Constraints verificadas no banco
- [ ] Serviço reiniciado (`docker-compose restart`)
- [ ] Teste de cadastro realizado
- [ ] Logs verificados (sem erros)

## 📊 Comandos Úteis Docker

```bash
# Ver status dos containers
docker-compose ps

# Ver logs em tempo real
docker-compose logs -f web

# Ver logs do banco
docker-compose logs -f db

# Acessar shell do Django
docker-compose exec web python manage.py shell

# Acessar shell do PostgreSQL
docker-compose exec db psql -U $DB_USER -d $DB_NAME

# Reiniciar todos os serviços
docker-compose restart

# Parar todos os serviços
docker-compose down

# Iniciar todos os serviços
docker-compose up -d
```

## 🎯 Dicas Importantes

1. **Backup é OBRIGATÓRIO** - Sem backup, não faça deploy
2. **git pull PRIMEIRO** - O comando de verificação só existe depois
3. **Reconstruir container** - Se houver mudanças no código Python
4. **Verificar logs** - Sempre após deploy
5. **Teste imediatamente** - Não espere, teste logo após deploy

---

**Boa sorte com o deploy! 🚀**

