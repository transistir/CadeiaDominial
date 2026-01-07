# 🔍 Diagnóstico - Nginx Unhealthy

## 📋 O Que Está Acontecendo

### Sequência de Eventos

1. Você executou `docker-compose down` - parou todos os containers
2. Executou `docker-compose up -d --build` - tentou subir tudo de uma vez
3. O **web** começou a iniciar (precisa de ~40 segundos para ficar healthy)
4. O **nginx** tentou iniciar **ANTES** do web ficar healthy
5. O nginx falhou porque depende do web estar healthy

### Por Que Funcionava Antes?

Provavelmente você:
- Não fazia `down` completo (só `restart`)
- Ou o web já estava rodando quando subia o nginx
- Ou havia mais tempo entre os comandos

## 🔍 Diagnóstico Passo a Passo

### 1. Verificar Status Atual dos Containers

```bash
# Ver status de todos
docker-compose ps

# Ver detalhes do web
docker inspect cadeia_dominial_web | grep -A 5 Health

# Ver detalhes do nginx
docker inspect cadeia_dominial_nginx | grep -A 5 Health
```

### 2. Ver Logs do Nginx

```bash
# Ver logs do nginx para entender o erro
docker-compose logs nginx

# Ver últimas 50 linhas
docker-compose logs nginx --tail=50
```

**O que procurar**:
- Erros de conexão com web
- Erros de configuração nginx
- Problemas com certificados SSL
- Problemas de rede

### 3. Ver Logs do Web

```bash
# Ver logs do web
docker-compose logs web

# Ver se web está respondendo
docker-compose exec web curl http://localhost:8000/admin/
```

### 4. Verificar Rede

```bash
# Verificar se containers estão na mesma rede
docker network inspect cadeiadominial_cadeia_network

# Testar conectividade do nginx para web
docker-compose exec nginx ping -c 3 web
```

## 🎯 Possíveis Causas

### Causa 1: Web Ainda Não Está Healthy

**Sintoma**: Nginx tenta iniciar antes do web estar pronto

**Healthcheck do web**:
- Testa: `curl -f http://localhost:8000/admin/`
- Tem 40 segundos para iniciar (`start_period: 40s`)
- Mas pode demorar mais se houver migrações ou inicialização lenta

**Solução**: Aguardar web ficar healthy antes de subir nginx

### Causa 2: Nginx Não Consegue Fazer Healthcheck

**Sintoma**: Nginx inicia mas healthcheck falha

**Healthcheck do nginx**:
- Testa: `curl -f http://localhost/health`
- Precisa que nginx esteja rodando e respondendo

**Possíveis problemas**:
- Nginx não iniciou corretamente
- Configuração nginx com erro
- Porta 80/443 ocupada

### Causa 3: Problema de Rede Entre Containers

**Sintoma**: Nginx não consegue conectar ao web

**Verificar**:
- Containers na mesma rede?
- DNS resolvendo corretamente?
- Firewall bloqueando?

### Causa 4: Problema com Certificados SSL

**Sintoma**: Nginx falha ao configurar SSL

**Verificar**:
- Certificados existem?
- Permissões corretas?
- Configuração nginx correta?

## 🔧 Comandos de Diagnóstico (Execute no Servidor)

```bash
# 1. Ver status atual
docker-compose ps

# 2. Ver logs do nginx (o mais importante)
docker-compose logs nginx --tail=100

# 3. Ver logs do web
docker-compose logs web --tail=50

# 4. Verificar se web está healthy
docker inspect cadeia_dominial_web --format='{{.State.Health.Status}}'

# 5. Testar healthcheck do nginx manualmente
docker-compose exec nginx curl -f http://localhost/health

# 6. Verificar configuração nginx
docker-compose exec nginx nginx -t

# 7. Verificar se nginx está rodando
docker-compose exec nginx ps aux | grep nginx
```

## 💡 O Que Provavelmente Está Acontecendo

Baseado no erro, o mais provável é:

1. **Web demorou mais que o esperado para ficar healthy**
   - Migrações podem demorar
   - Inicialização do Django pode demorar
   - Banco pode estar lento

2. **Nginx tentou iniciar antes do web estar pronto**
   - Docker Compose tenta iniciar tudo em paralelo
   - Mesmo com `depends_on: condition: service_healthy`, pode haver race condition

3. **Nginx falhou no healthcheck próprio**
   - Nginx iniciou mas não conseguiu responder em `/health`
   - Pode ser problema de configuração

## ✅ Solução Manual (Sem Script)

### Opção 1: Subir em Etapas

```bash
# 1. Subir db e web primeiro
docker-compose up -d db web

# 2. Aguardar web ficar healthy (verificar)
docker-compose ps
# Repetir até web mostrar "healthy"

# 3. Depois subir nginx
docker-compose up -d nginx
```

### Opção 2: Verificar e Corrigir o Problema Real

```bash
# Ver logs do nginx para entender o erro específico
docker-compose logs nginx

# Se for problema de configuração, corrigir
# Se for problema de rede, verificar
# Se for problema de certificado, corrigir
```

## 🎯 Próximo Passo

**Execute no servidor**:
```bash
docker-compose logs nginx --tail=100
```

Isso vai mostrar **exatamente** o que está causando o nginx ficar unhealthy. Com essa informação, podemos corrigir o problema específico.

---

**O problema não é necessariamente com sua mudança - pode ser timing ou algo que mudou no ambiente. Os logs vão revelar a causa real.**

