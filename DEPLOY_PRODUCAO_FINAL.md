# 🚀 Deploy em Produção - Docker Compose (FINAL)

## ⚡ Comandos Corretos (Copy & Paste)

### Passo a Passo Completo

```bash
# 1. Backup (OBRIGATÓRIO)
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup_antes_migracao_matricula_$(date +%Y%m%d_%H%M%S).sql
ls -lh backup_antes_migracao_matricula_*.sql

# 2. Atualizar código
git pull origin main

# 3. Reconstruir container (IMPORTANTE - traz o novo comando)
docker-compose up -d --build web

# 4. Verificar dados (AGORA o comando existe)
docker-compose exec web python manage.py verificar_matricula_constraint

# 5. Aplicar migração
docker-compose exec web python manage.py migrate

# 6. Verificar migração aplicada
docker-compose exec web python manage.py showmigrations dominial | grep 0042

# 7. Verificar constraints no banco
docker-compose exec db psql -U $DB_USER -d $DB_NAME -c "\d dominial_imovel" | grep -E "(unique|index)"

# 8. Reiniciar serviço
docker-compose restart web

# 9. Verificar logs
docker-compose logs web --tail=20
```

## ⚠️ Por Que o Erro Aconteceu?

Você tentou executar `verificar_matricula_constraint` **ANTES** de:
1. ✅ Fazer `git pull` (atualizar código)
2. ✅ Reconstruir container (`docker-compose up -d --build web`)

O comando só existe **DEPOIS** desses dois passos!

## ✅ Solução Imediata

Execute na ordem:

```bash
# 1. Atualizar código
git pull origin main

# 2. Reconstruir container
docker-compose up -d --build web

# 3. AGORA o comando funciona
docker-compose exec web python manage.py verificar_matricula_constraint
```

## 📋 Checklist Completo

- [ ] Backup criado (`docker-compose exec db pg_dump...`)
- [ ] Código atualizado (`git pull`)
- [ ] Container reconstruído (`docker-compose up -d --build web`)
- [ ] Verificação executada (sem duplicatas)
- [ ] Migração aplicada (`migrate`)
- [ ] Migração verificada (`showmigrations`)
- [ ] Constraints verificadas no banco
- [ ] Serviço reiniciado (`docker-compose restart web`)
- [ ] Teste realizado
- [ ] Logs verificados

## 🎯 Tempo Total: ~7 minutos

---

**Agora você tem os comandos corretos para Docker! 🚀**

