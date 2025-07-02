# 🐳 Cadeia Dominial - Docker

Este documento explica como executar o sistema Cadeia Dominial usando Docker, incluindo configuração automática de SSL com Let's Encrypt.

## 📋 Pré-requisitos

- Docker (versão 20.10+)
- Docker Compose (versão 2.0+)
- Domínio configurado (para SSL)
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

# Configurações do SSL/Let's Encrypt
DOMAIN_NAME=seu-dominio.com
CERTBOT_EMAIL=seu-email@exemplo.com

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

# Iniciar todo o sistema
./scripts/start.sh
```

## 🏗️ Arquitetura

O sistema é composto pelos seguintes containers:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx + SSL   │    │   Django App    │    │   PostgreSQL    │
│   (Port 80/443) │◄──►│   (Port 8000)   │◄──►│   (Port 5432)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Serviços

- **Nginx**: Proxy reverso com SSL automático
- **Django**: Aplicação web principal
- **PostgreSQL**: Banco de dados
- **Certbot**: Gerenciamento de certificados SSL

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
# Configurar SSL inicial
./scripts/init-ssl.sh

# Renovar certificados
./scripts/renew-ssl.sh

# Verificar status dos certificados
docker-compose run --rm certbot certificates
```

## 🔒 Configuração SSL

### Configuração Automática

O sistema configura automaticamente SSL com Let's Encrypt:

1. **Primeira execução**: Execute `./scripts/init-ssl.sh`
2. **Renovação automática**: Configure um cron job:

```bash
# Adicionar ao crontab (renovar a cada 12 horas)
0 */12 * * * cd /caminho/para/CadeiaDominial && ./scripts/renew-ssl.sh
```

### Configuração Manual

Se preferir usar certificados próprios:

1. Coloque os certificados em `certbot/conf/live/seu-dominio.com/`
2. Reinicie o Nginx: `docker-compose restart nginx`

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

- **Nginx**: `/var/log/nginx/` (dentro do container)
- **Django**: `docker-compose logs web`
- **PostgreSQL**: `docker-compose logs db`

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
docker-compose run --rm certbot certificates

# Recriar certificados
docker-compose run --rm certbot delete --cert-name $DOMAIN_NAME
./scripts/init-ssl.sh
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

### Limpeza Completa

```bash
# Parar e remover tudo
docker-compose down -v
docker system prune -a
rm -rf certbot/conf/*
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

- Renove certificados SSL automaticamente
- Faça backup regular do banco
- Monitore logs de erro
- Mantenha containers atualizados

## 🤝 Suporte

Para problemas ou dúvidas:

1. Verifique os logs: `docker-compose logs`
2. Consulte a documentação do Django
3. Abra uma issue no GitHub
4. Entre em contato com a equipe de desenvolvimento

---

**Versão**: 1.0  
**Última atualização**: $(date)  
**Compatível com**: Docker 20.10+, Docker Compose 2.0+ 