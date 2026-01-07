# 🚀 Deploy da Alteração de TI - Docker Compose

## ⚡ Deploy Rápido (Sem Derrubar Todos os Containers)

### ✅ O que NÃO precisa fazer:
- ❌ **NÃO** precisa derrubar o container do banco (`db`)
- ❌ **NÃO** precisa derrubar o container do nginx
- ❌ **NÃO** precisa fazer `docker-compose down`
- ❌ **NÃO** precisa aplicar migrações (não há mudanças no banco)

### ✅ O que precisa fazer:
- ✅ Atualizar código (`git pull`)
- ✅ Reconstruir apenas o container `web`
- ✅ Coletar arquivos estáticos (se necessário)
- ✅ Reiniciar o container `web`

---

## 📋 Passo a Passo Completo

### 1. Backup (Recomendado - 1 min)

```bash
# Backup do banco (opcional, mas recomendado)
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup_antes_alteracao_ti_$(date +%Y%m%d_%H%M%S).sql

# Verificar se foi criado
ls -lh backup_antes_alteracao_ti_*.sql
```

### 2. Atualizar Código (30 seg)

```bash
# No diretório do projeto
cd /caminho/do/projeto

# Atualizar código do repositório
git pull origin main
```

### 3. Reconstruir Container Web (2-3 min)

```bash
# Reconstruir apenas o container web (sem derrubar os outros)
docker-compose up -d --build web
```

**O que acontece:**
- ✅ Container `web` é reconstruído com o novo código
- ✅ Containers `db` e `nginx` continuam rodando normalmente
- ✅ Sem downtime do banco de dados
- ✅ Nginx continua servindo (pode ter um pequeno downtime de ~10-30 segundos enquanto o web reinicia)

### 4. Coletar Arquivos Estáticos (30 seg - se necessário)

```bash
# Se houver mudanças em arquivos estáticos (CSS, JS, etc)
docker-compose exec web python manage.py collectstatic --noinput
```

**Nota:** Para esta alteração específica (admin), geralmente não é necessário, mas não faz mal executar.

### 5. Verificar se Está Funcionando (30 seg)

```bash
# Verificar logs do container web
docker-compose logs web --tail=20

# Verificar se o container está healthy
docker-compose ps
```

**✅ Resultado esperado:**
- Container `web` deve estar com status `Up` e `healthy`
- Sem erros nos logs

### 6. Testar no Navegador

1. Acesse: `https://seu-dominio.com/admin/`
2. Vá em **Imóveis** → Selecione um imóvel
3. Verifique se o botão **"🔄 Alterar Terra Indígena (TI)"** aparece
4. Teste a funcionalidade

---

## 🎯 Comandos Resumidos (Copy & Paste)

```bash
# 1. Backup (opcional)
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup_antes_alteracao_ti_$(date +%Y%m%d_%H%M%S).sql

# 2. Atualizar código
git pull origin main

# 3. Reconstruir container web
docker-compose up -d --build web

# 4. Coletar estáticos (opcional)
docker-compose exec web python manage.py collectstatic --noinput

# 5. Verificar logs
docker-compose logs web --tail=20

# 6. Verificar status
docker-compose ps
```

---

## ⚠️ O Que Acontece Durante o Deploy

### Container `web` (Django):
- 🔄 Para de receber requisições
- 🔨 É reconstruído com novo código
- ✅ Reinicia automaticamente
- ⏱️ Downtime: ~10-30 segundos

### Container `db` (PostgreSQL):
- ✅ **Continua rodando normalmente**
- ✅ **Sem interrupção**
- ✅ **Dados preservados**

### Container `nginx`:
- ✅ **Continua rodando normalmente**
- ⚠️ Pode retornar erro 502 durante ~10-30 segundos enquanto o `web` reinicia
- ✅ Volta ao normal automaticamente

---

## 🔍 Troubleshooting

### Problema: Container web não sobe

```bash
# Verificar logs detalhados
docker-compose logs web

# Verificar se há erros de sintaxe
docker-compose exec web python manage.py check
```

### Problema: Erro 502 no navegador

```bash
# Aguardar alguns segundos (container pode estar iniciando)
# Verificar se o container está healthy
docker-compose ps

# Se não estiver healthy, verificar logs
docker-compose logs web --tail=50
```

### Problema: Mudanças não aparecem

```bash
# Verificar se o código foi atualizado
docker-compose exec web ls -la /app/dominial/admin.py

# Forçar reconstrução sem cache
docker-compose build --no-cache web
docker-compose up -d web
```

### Problema: Erro de permissão

```bash
# Verificar permissões dos arquivos
ls -la templates/admin/dominial/imovel/

# Se necessário, ajustar permissões
chmod -R 755 templates/admin/
```

---

## ✅ Checklist de Deploy

- [ ] Backup criado (opcional mas recomendado)
- [ ] Código atualizado (`git pull`)
- [ ] Container web reconstruído (`docker-compose up -d --build web`)
- [ ] Arquivos estáticos coletados (se necessário)
- [ ] Logs verificados (sem erros)
- [ ] Container web está healthy
- [ ] Funcionalidade testada no navegador
- [ ] Botão "Alterar TI" aparece na edição de imóvel
- [ ] Página de alteração carrega corretamente
- [ ] Alteração de TI funciona

---

## 📊 Tempo Total Estimado

- **Backup**: 1 minuto (opcional)
- **Git pull**: 30 segundos
- **Rebuild web**: 2-3 minutos
- **Collectstatic**: 30 segundos (opcional)
- **Verificação**: 1 minuto
- **Teste**: 2 minutos

**Total: ~5-7 minutos** (sem contar testes)

---

## 🎯 Vantagens Desta Abordagem

✅ **Sem downtime do banco de dados**
✅ **Nginx continua servindo** (apenas pequeno downtime durante restart do web)
✅ **Deploy rápido** (~5 minutos)
✅ **Sem risco de perda de dados**
✅ **Rollback fácil** (apenas fazer `git pull` do commit anterior e rebuild)

---

## 🔄 Rollback (Se Necessário)

Se algo der errado, é fácil reverter:

```bash
# 1. Voltar para commit anterior
git log --oneline -5  # Ver commits
git checkout <commit-anterior>
# ou
git reset --hard HEAD~1

# 2. Reconstruir container
docker-compose up -d --build web

# 3. Verificar
docker-compose logs web --tail=20
```

---

**Pronto!** Esta é a forma mais segura e rápida de fazer deploy desta alteração. 🚀
