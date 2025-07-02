# 🐳 Cadeia Dominial - Docker com SSL Automático

Este documento explica como executar o sistema Cadeia Dominial usando Docker com **SSL automático plug-and-play**, incluindo configuração automática de certificados Let's Encrypt.

## ✨ Novidades - SSL Automático Plug-and-Play

O sistema agora inclui **SSL automático** que funciona desde o primeiro build:

- 🔐 **Certificados automáticos**: Obtém certificados Let's Encrypt automaticamente
- 🚀 **Zero configuração**: Funciona sem scripts manuais
- 🔄 **Renovação automática**: Renova certificados automaticamente
- 🛡️ **Fallback seguro**: Funciona via HTTP se SSL falhar
- 📱 **Health checks**: Monitoramento automático de saúde

## 📋 Pré-requisitos

- Docker (versão 20.10+)
- Docker Compose (versão 2.0+)
- Domínio configurado (para SSL automático)
- Acesso root no servidor

## 🚀 Início Rápido

### 1. Configuração Inicial

```bash
# Clonar o repositório
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial

# Copiar arquivo de configuração
cp env.example .env

# Editar configurações
nano .env
```

### 2. Configurar Variáveis de Ambiente

Edite o arquivo `.env` com suas configurações:

```env
# Configurações do Django
DEBUG=False
SECRET_KEY=sua_chave_secreta_muito_segura_aqui
ALLOWED_HOSTS=localhost,127.0.0.1,seu-dominio.com

# Configurações do Banco de Dados
DB_NAME=cadeia_dominial
DB_USER=cadeia_user
DB_PASSWORD=sua_senha_segura_aqui
DB_HOST=db
DB_PORT=5432

# Configurações do SSL/Let's Encrypt (OBRIGATÓRIO para SSL)
DOMAIN_NAME=seu-dominio.com
CERTBOT_EMAIL=seu-email@exemplo.com

# Configurações do Usuário Admin (OBRIGATÓRIO)
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@cadeiadominial.com.br
ADMIN_PASSWORD=sua_senha_admin_muito_segura_aqui

# Configurações de Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua_senha_de_app
```

### 3. Iniciar o Sistema

```bash
# Dar permissão de execução aos scripts
chmod +x scripts/*.sh

# Iniciar todo o sistema (inclui SSL automático)
./scripts/start.sh
```

**🎉 Pronto!** O sistema estará disponível em:
- **HTTP**: http://seu-dominio.com
- **HTTPS**: https://seu-dominio.com (ativado automaticamente)

## 🏗️ Arquitetura SSL Automático

```
┌─────────────────────────────────────────────────────────────┐
│                    Nginx Container                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   HTTP (80)     │  │   HTTPS (443)   │  │   Certbot   │ │
│  │   (Sempre ativo)│  │   (Automático)  │  │   (Auto)    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
           │                           │
           ▼                           ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Django App    │    │   PostgreSQL    │    │   SSL Certs     │
│   (Port 8000)   │◄──►│   (Port 5432)   │    │   (Auto-renew)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Como Funciona o SSL Automático

1. **Inicialização**: Container Nginx inicia com certificados dummy
2. **Detecção**: Verifica se DOMAIN_NAME é um domínio real
3. **Obtenção**: Certbot obtém certificados Let's Encrypt automaticamente
4. **Ativação**: Nginx recarrega com certificados reais
5. **Renovação**: Cron renova certificados automaticamente

## 🔧 Comandos Úteis

### Gerenciamento de Containers

```bash
# Ver status dos containers
docker-compose ps

# Ver logs em tempo real
docker-compose logs -f

# Ver logs de um serviço específico
docker-compose logs -f web
docker-compose logs -f nginx
docker-compose logs -f db

# Parar todos os containers
docker-compose down

# Reiniciar um serviço
docker-compose restart web

# Reconstruir containers
docker-compose up -d --build
```

### Banco de Dados

```bash
# Fazer backup do banco
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup.sql

# Restaurar backup
docker-compose exec -T db psql -U $DB_USER $DB_NAME < backup.sql

# Acessar shell do PostgreSQL
docker-compose exec db psql -U $DB_USER -d $DB_NAME
```

### Django

```bash
# Executar migrações
docker-compose exec web python manage.py migrate

# Criar superusuário
docker-compose exec web python manage.py createsuperuser

# Coletar arquivos estáticos
docker-compose exec web python manage.py collectstatic --noinput

# Acessar shell do Django
docker-compose exec web python manage.py shell
```

### SSL/Let's Encrypt

```bash
# Verificar status dos certificados
docker-compose exec nginx certbot certificates

# Renovar certificados manualmente
docker-compose exec nginx certbot renew

# Ver logs do SSL
docker-compose logs nginx | grep SSL

# Verificar configuração SSL
docker-compose exec nginx nginx -t
```

## 🔒 Configuração SSL

### Configuração Automática (Recomendado)

O SSL é configurado automaticamente quando você define:

```env
DOMAIN_NAME=seu-dominio.com
CERTBOT_EMAIL=seu-email@exemplo.com
```

**O que acontece automaticamente:**
1. ✅ Certificados são obtidos via Let's Encrypt
2. ✅ Nginx é configurado com HTTPS
3. ✅ Redirecionamento HTTP → HTTPS é ativado
4. ✅ Renovação automática é configurada
5. ✅ Headers de segurança são aplicados

### Configuração Manual (Avançado)

Se preferir usar certificados próprios:

1. Coloque os certificados em volumes Docker:
   ```bash
   # Montar certificados existentes
   docker run -v /path/to/certs:/etc/letsencrypt nginx
   ```

2. Reinicie o Nginx:
   ```bash
   docker-compose restart nginx
   ```

## 🛠️ Desenvolvimento

Para desenvolvimento local, use o arquivo `docker-compose.dev.yml`:

```bash
# Iniciar ambiente de desenvolvimento
docker-compose -f docker-compose.dev.yml up -d

# Ver logs
docker-compose -f docker-compose.dev.yml logs -f

# Parar ambiente de desenvolvimento
docker-compose -f docker-compose.dev.yml down
```

### Diferenças do Ambiente de Desenvolvimento

- **DEBUG=True**: Logs detalhados
- **Volume do código**: Mudanças no código são refletidas imediatamente
- **Sem SSL**: Acesso via HTTP na porta 8000
- **Django runserver**: Servidor de desenvolvimento

## 📊 Monitoramento

### Logs

Os logs são armazenados em:

- **Nginx**: `docker-compose logs nginx`
- **Django**: `docker-compose logs web`
- **PostgreSQL**: `docker-compose logs db`

### Health Checks

```bash
# Verificar saúde dos containers
docker-compose ps

# Verificar endpoint de saúde
curl http://localhost/health

# Verificar logs de erro
docker-compose logs nginx | grep error
```

### Métricas

```bash
# Uso de recursos dos containers
docker stats

# Espaço em disco
docker system df

# Limpar recursos não utilizados
docker system prune
```

## 🔧 Troubleshooting

### Problemas Comuns

#### 1. Container não inicia

```bash
# Verificar logs
docker-compose logs [nome_do_servico]

# Verificar se as portas estão livres
netstat -tulpn | grep :80
netstat -tulpn | grep :443
```

#### 2. Erro de SSL

```bash
# Verificar certificados
docker-compose exec nginx certbot certificates

# Verificar logs do SSL
docker-compose logs nginx | grep -i ssl

# Recriar certificados
docker-compose exec nginx certbot delete --cert-name $DOMAIN_NAME
docker-compose restart nginx
```

#### 3. Erro de banco de dados

```bash
# Verificar conexão
docker-compose exec web python manage.py dbshell

# Resetar banco (CUIDADO!)
docker-compose down -v
docker-compose up -d
```

#### 4. Arquivos estáticos não carregam

```bash
# Recriar arquivos estáticos
docker-compose exec web python manage.py collectstatic --noinput --clear
docker-compose restart nginx
```

#### 5. SSL não ativa automaticamente

```bash
# Verificar variáveis de ambiente
echo "DOMAIN_NAME: $DOMAIN_NAME"
echo "CERTBOT_EMAIL: $CERTBOT_EMAIL"

# Verificar logs do entrypoint
docker-compose logs nginx | grep -i "ssl\|cert"

# Forçar obtenção de certificados
docker-compose exec nginx /usr/local/bin/ssl-init.sh $DOMAIN_NAME $CERTBOT_EMAIL
```

### Limpeza Completa

```bash
# Parar e remover tudo
docker-compose down -v
docker system prune -a
rm -rf staticfiles/*
```

## 📝 Notas Importantes

### Segurança

- **Nunca** commite o arquivo `.env` no Git
- Use senhas fortes para o banco de dados
- Mantenha o sistema atualizado
- Configure firewall adequadamente

### Performance

- Para produção, considere usar volumes persistentes
- Configure backup automático do banco
- Monitore uso de recursos
- Configure cache Redis se necessário

### Manutenção

- Certificados são renovados automaticamente
- Faça backup regular do banco
- Monitore logs de erro
- Mantenha containers atualizados

## 🎯 Benefícios do SSL Automático

### ✅ Zero Configuração
- Não precisa rodar scripts manuais
- Funciona desde o primeiro `docker-compose up`

### ✅ Alta Disponibilidade
- Sistema funciona via HTTP se SSL falhar
- Certificados dummy garantem inicialização

### ✅ Segurança Automática
- Renovação automática de certificados
- Headers de segurança configurados
- Redirecionamento HTTP → HTTPS

### ✅ Monitoramento
- Health checks automáticos
- Logs detalhados de SSL
- Status de certificados visível

## 🤝 Suporte

Para problemas ou dúvidas:

1. Verifique os logs: `docker-compose logs`
2. Consulte a documentação do Django
3. Abra uma issue no GitHub
4. Entre em contato com a equipe de desenvolvimento

---

**Versão**: 2.0 (SSL Automático)  
**Última atualização**: $(date)  
**Compatível com**: Docker 20.10+, Docker Compose 2.0+ 