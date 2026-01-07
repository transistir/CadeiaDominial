# 🚀 Deploy em Produção - Guia Rápido

## ⚡ Checklist Rápido (5 minutos)

### 1. Backup (OBRIGATÓRIO - 2 min)
```bash
# No servidor de produção
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup_antes_migracao_$(date +%Y%m%d_%H%M%S).sql

# Verificar se o backup foi criado
ls -lh backup_antes_migracao_*.sql
```

### 2. Atualizar Código (1 min)
```bash
# No diretório do projeto
git pull origin main

# Verificar se não há mudanças não commitadas
git status
```

### 3. Reconstruir Container (1 min)
```bash
# Reconstruir container web com novo código
docker-compose up -d --build web
```

### 4. Verificar Dados (1 min)
```bash
# AGORA o comando existe (depois do git pull e rebuild)
docker-compose exec web python manage.py verificar_matricula_constraint
```

**Resultado esperado**: ✅ Nenhuma duplicata no mesmo cartório

### 5. Aplicar Migração (30 seg)
```bash
# Aplicar migração
docker-compose exec web python manage.py migrate

# Verificar se foi aplicada
docker-compose exec web python manage.py showmigrations dominial | grep 0042
```

**Resultado esperado**: `[X] 0042_fix_matricula_unique_constraint`

### 6. Verificar Constraints (30 seg)
```bash
# Verificar se a constraint foi criada
docker-compose exec db psql -U $DB_USER -d $DB_NAME -c "\d dominial_imovel" | grep -E "(unique|index)"
```

**Deve mostrar**:
- `unique_matricula_por_cartorio`
- `dom_imovel_mat_cart_idx`

### 7. Reiniciar Serviços (30 seg)
```bash
# Reiniciar web (se necessário)
docker-compose restart web

# Verificar logs
docker-compose logs web --tail=20 | grep -i error
```

## ✅ Teste Rápido Pós-Deploy (2 min)

1. **Acessar sistema**: `https://cadeiadominial.com.br`
2. **Testar cadastro**: Tentar cadastrar imóvel com matrícula existente em outro cartório ✅
3. **Verificar erro**: Tentar cadastrar no mesmo cartório (deve dar erro claro) ❌

## ⚠️ Pontos de Atenção

### Se a Migração Falhar

**Erro**: "Matrículas duplicadas no mesmo cartório"
```bash
# 1. Ver detalhes
docker-compose exec web python manage.py verificar_matricula_constraint

# 2. Resolver duplicatas manualmente no banco
# 3. Tentar migração novamente
```

### Se Houver Problemas

**Rollback rápido**:
```bash
# Restaurar backup
docker-compose exec -T db psql -U $DB_USER -d $DB_NAME < backup_antes_migracao_YYYYMMDD_HHMMSS.sql

# Reverter código (se necessário)
git revert HEAD
```

## 📋 Comandos Completos (Copy & Paste)

```bash
# 1. Backup
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup_antes_migracao_$(date +%Y%m%d_%H%M%S).sql

# 2. Atualizar código
cd /caminho/do/projeto
git pull origin main

# 3. Reconstruir container
docker-compose up -d --build web

# 4. Verificar dados (AGORA o comando existe)
docker-compose exec web python manage.py verificar_matricula_constraint

# 5. Aplicar migração
docker-compose exec web python manage.py migrate

# 6. Verificar migração
docker-compose exec web python manage.py showmigrations dominial | grep 0042

# 7. Verificar constraints
docker-compose exec db psql -U $DB_USER -d $DB_NAME -c "\d dominial_imovel" | grep unique

# 8. Reiniciar (se necessário)
docker-compose restart web

# 9. Verificar logs
docker-compose logs web --tail=50
```

## 🎯 Tempo Total Estimado

- **Backup**: 2 minutos
- **Atualizar código**: 1 minuto
- **Reconstruir container**: 1 minuto
- **Verificar dados**: 1 minuto
- **Aplicar migração**: 1 minuto
- **Validação**: 1 minuto
- **Total**: ~7 minutos

## ✅ Checklist Final

- [ ] Backup criado e verificado
- [ ] Código atualizado (`git pull`)
- [ ] Container reconstruído (`docker-compose up -d --build web`)
- [ ] Verificação de dados executada (sem duplicatas)
- [ ] Migração aplicada com sucesso
- [ ] Constraints verificadas no banco
- [ ] Serviços reiniciados
- [ ] Teste de cadastro realizado
- [ ] Logs verificados (sem erros)

## 📞 Se Algo Der Errado

1. **Não entre em pânico** - O backup está salvo
2. **Verificar logs**: `docker-compose logs web`
3. **Consultar**: `CHECKLIST_PRODUCAO_MATRICULA.md` para mais detalhes
4. **Rollback**: Restaurar backup se necessário

---

**Boa sorte com o deploy! 🚀**

