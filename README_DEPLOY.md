# 🚀 Deploy da Cadeia Dominial

Este guia explica como fazer deploy da aplicação Cadeia Dominial em diferentes plataformas.

## 📋 Pré-requisitos

- Conta no GitHub
- Conta na plataforma escolhida (Railway, Render, etc.)
- Python 3.11+
- Git

## 🎯 Plataformas Recomendadas

### 1. Railway (Recomendado)
- **Custo**: Gratuito para começar
- **Facilidade**: ⭐⭐⭐⭐⭐
- **Recursos**: PostgreSQL incluído, SSL gratuito
- **Guia**: [deploy_railway.md](deploy_railway.md)

### 2. Render
- **Custo**: Gratuito para começar
- **Facilidade**: ⭐⭐⭐⭐
- **Recursos**: PostgreSQL gratuito, SSL gratuito
- **URL**: [render.com](https://render.com)

### 3. Heroku
- **Custo**: $5-25/mês
- **Facilidade**: ⭐⭐⭐⭐
- **Recursos**: Muito estável, add-ons abundantes
- **URL**: [heroku.com](https://heroku.com)

## 🛠️ Preparação do Projeto

### 1. Verificar Arquivos
Certifique-se de que os seguintes arquivos estão presentes:
- ✅ `requirements.txt` - Dependências Python
- ✅ `Procfile` - Configuração do servidor
- ✅ `runtime.txt` - Versão do Python
- ✅ `cadeia_dominial/settings_prod.py` - Configurações de produção

### 2. Executar Script de Deploy
```bash
# Tornar executável (se necessário)
chmod +x deploy.sh

# Executar deploy
./deploy.sh
```

### 3. Deploy Manual
```bash
# Atualizar dependências
pip install -r requirements.txt

# Coletar arquivos estáticos
python manage.py collectstatic --noinput

# Commit e push
git add .
git commit -m "feat: preparar para deploy"
git push origin develop
```

## 🔧 Configurações de Produção

### Variáveis de Ambiente Necessárias
```env
# Django
SECRET_KEY=sua_chave_secreta_muito_segura
DEBUG=False
ALLOWED_HOSTS=seu-dominio.com

# Banco de Dados
DATABASE_URL=postgresql://usuario:senha@host:porta/nome_do_banco

# CSRF
CSRF_TRUSTED_ORIGINS=https://seu-dominio.com

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu_email@gmail.com
EMAIL_HOST_PASSWORD=sua_senha_de_app
```

### Comandos de Build
```bash
# Build Command
python manage.py collectstatic --noinput

# Start Command
gunicorn cadeia_dominial.wsgi
```

## 🗄️ Configuração do Banco

Após o deploy, execute:
```bash
# Migrar banco
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Carregar dados iniciais (se necessário)
python manage.py loaddata dados_iniciais.json
```

## 📊 Monitoramento

### Logs
- Railway: Dashboard → Logs
- Render: Dashboard → Logs
- Heroku: `heroku logs --tail`

### Métricas
- Uso de CPU e memória
- Requisições por minuto
- Tempo de resposta
- Erros 4xx/5xx

## 🔒 Segurança

### Checklist
- [ ] `DEBUG = False`
- [ ] `SECRET_KEY` segura
- [ ] `ALLOWED_HOSTS` configurado
- [ ] `CSRF_TRUSTED_ORIGINS` configurado
- [ ] SSL/HTTPS ativo
- [ ] Senhas fortes
- [ ] Backup configurado

### Backup
```bash
# Backup do banco
python manage.py dumpdata > backup.json

# Restore
python manage.py loaddata backup.json
```

## 🚨 Troubleshooting

### Problemas Comuns

1. **Erro de arquivos estáticos**
   ```bash
   python manage.py collectstatic --noinput
   ```

2. **Erro de migração**
   ```bash
   python manage.py migrate --run-syncdb
   ```

3. **Erro de permissão**
   ```bash
   chmod +x deploy.sh
   ```

4. **Timeout no deploy**
   - Verificar logs
   - Aumentar timeout na plataforma
   - Otimizar build

### Logs Úteis
```bash
# Ver logs em tempo real
tail -f logs/app.log

# Ver erros
grep ERROR logs/app.log

# Ver performance
grep "Request took" logs/app.log
```

## 📞 Suporte

- **Railway**: [docs.railway.app](https://docs.railway.app)
- **Render**: [render.com/docs](https://render.com/docs)
- **Heroku**: [devcenter.heroku.com](https://devcenter.heroku.com)

## 💰 Custos Estimados

| Plataforma | Plano Gratuito | Plano Pago |
|------------|----------------|------------|
| Railway    | 500h/mês       | $5-20/mês  |
| Render     | 750h/mês       | $7-25/mês  |
| Heroku     | Não disponível | $5-25/mês  |

## 🎉 Próximos Passos

1. ✅ Fazer deploy
2. ✅ Configurar domínio personalizado
3. ✅ Configurar SSL
4. ✅ Configurar backup automático
5. ✅ Configurar monitoramento
6. ✅ Configurar CI/CD
7. ✅ Testar em produção 

# Deploy Cadeia Dominial - Servidor Debian 12

## Informações do Servidor
- **IP**: 46.62.152.252
- **Sistema**: Debian 12
- **Aplicação**: Django Cadeia Dominial

## Deploy Inicial

### 1. Conectar ao Servidor
```bash
ssh root@46.62.152.252
```

### 2. Executar Script de Deploy
```bash
# Baixar o script de deploy
wget https://raw.githubusercontent.com/transistir/CadeiaDominial/main/deploy.sh
chmod +x deploy.sh

# Executar deploy
./deploy.sh
```

O script irá:
- ✅ Instalar todas as dependências do sistema
- ✅ Configurar PostgreSQL
- ✅ Criar usuário da aplicação
- ✅ Clonar o repositório
- ✅ Configurar ambiente Python
- ✅ Configurar Nginx e Supervisor
- ✅ Executar migrações
- ✅ Configurar firewall
- ✅ Iniciar todos os serviços

### 3. Criar Superusuário
```bash
su - cadeia
cd /home/cadeia/cadeia_dominial
source venv/bin/activate
python manage.py createsuperuser --settings=cadeia_dominial.settings_prod
```

## Atualizações

### Atualização Automática
```bash
# Baixar script de atualização
wget https://raw.githubusercontent.com/transistir/CadeiaDominial/main/update.sh
chmod +x update.sh

# Executar atualização
./update.sh
```

### Atualização Manual
```bash
# Parar aplicação
supervisorctl stop cadeia_dominial

# Atualizar código
su - cadeia -c "cd /home/cadeia/cadeia_dominial && git pull origin main"

# Atualizar dependências
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && pip install -r requirements.txt"

# Executar migrações
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && python manage.py migrate --settings=cadeia_dominial.settings_prod"

# Coletar arquivos estáticos
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && python manage.py collectstatic --settings=cadeia_dominial.settings_prod --noinput"

# Reiniciar aplicação
supervisorctl start cadeia_dominial
```

## Monitoramento

### Verificar Status dos Serviços
```bash
# Status da aplicação
supervisorctl status cadeia_dominial

# Status do Nginx
systemctl status nginx

# Status do PostgreSQL
systemctl status postgresql
```

### Verificar Logs
```bash
# Logs da aplicação
tail -f /var/log/cadeia_dominial/gunicorn.log

# Logs do Nginx
tail -f /var/log/nginx/cadeia_dominial_error.log

# Logs do Django
tail -f /var/log/cadeia_dominial/django.log
```

### Verificar Uso de Recursos
```bash
# CPU e memória
htop

# Espaço em disco
df -h

# Processos da aplicação
ps aux | grep gunicorn
```

## Backup e Restauração

### Backup do Banco de Dados
```bash
# Backup manual
sudo -u postgres pg_dump cadeia_dominial > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup automático (incluído no script de atualização)
./update.sh
```

### Restaurar Banco de Dados
```bash
# Parar aplicação
supervisorctl stop cadeia_dominial

# Restaurar backup
sudo -u postgres psql cadeia_dominial < backup.sql

# Reiniciar aplicação
supervisorctl start cadeia_dominial
```

## Configurações

### Variáveis de Ambiente
Arquivo: `/home/cadeia/cadeia_dominial/.env`
```env
DEBUG=False
SECRET_KEY=sua_chave_secreta_muito_segura_aqui
DB_NAME=cadeia_dominial
DB_USER=cadeia_user
DB_PASSWORD=sua_senha_segura_aqui
DB_HOST=localhost
DB_PORT=5432
ALLOWED_HOSTS=46.62.152.252,localhost,127.0.0.1
```

### Configurações do Nginx
Arquivo: `/etc/nginx/sites-available/cadeia_dominial`

### Configurações do Supervisor
Arquivo: `/etc/supervisor/conf.d/cadeia_dominial.conf`

## Troubleshooting

### Problemas Comuns

#### 1. Erro 502 Bad Gateway
```bash
# Verificar se a aplicação está rodando
supervisorctl status cadeia_dominial

# Verificar logs
tail -f /var/log/cadeia_dominial/gunicorn.log

# Reiniciar aplicação
supervisorctl restart cadeia_dominial
```

#### 2. Erro de Conexão com Banco
```bash
# Verificar se PostgreSQL está rodando
systemctl status postgresql

# Verificar conexão
sudo -u postgres psql -c "SELECT version();"

# Verificar configurações no .env
cat /home/cadeia/cadeia_dominial/.env
```

#### 3. Arquivos Estáticos não Carregam
```bash
# Verificar se collectstatic foi executado
ls -la /home/cadeia/cadeia_dominial/staticfiles/

# Executar collectstatic
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && python manage.py collectstatic --settings=cadeia_dominial.settings_prod --noinput"

# Verificar permissões
chown -R cadeia:cadeia /home/cadeia/cadeia_dominial/staticfiles/
```

#### 4. Erro de Permissões
```bash
# Verificar proprietário dos arquivos
ls -la /home/cadeia/cadeia_dominial/

# Ajustar permissões
chown -R cadeia:cadeia /home/cadeia/cadeia_dominial/
chmod -R 755 /home/cadeia/cadeia_dominial/
```

## Comandos Úteis

### Gerenciamento de Serviços
```bash
# Reiniciar aplicação
supervisorctl restart cadeia_dominial

# Parar aplicação
supervisorctl stop cadeia_dominial

# Iniciar aplicação
supervisorctl start cadeia_dominial

# Ver status
supervisorctl status cadeia_dominial

# Ver logs em tempo real
supervisorctl tail cadeia_dominial
```

### Gerenciamento do Django
```bash
# Acessar shell do Django
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && python manage.py shell --settings=cadeia_dominial.settings_prod"

# Executar comando personalizado
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && python manage.py [comando] --settings=cadeia_dominial.settings_prod"
```

### Monitoramento do Sistema
```bash
# Ver processos
ps aux | grep -E "(gunicorn|nginx|postgres)"

# Ver portas em uso
netstat -tlnp

# Ver uso de memória
free -h

# Ver uso de disco
df -h
```

## Segurança

### Firewall
O firewall (ufw) está configurado para permitir apenas:
- SSH (porta 22)
- HTTP (porta 80)
- HTTPS (porta 443)

### Usuários
- **cadeia**: Usuário da aplicação (sem senha, acesso via sudo)
- **cadeia_user**: Usuário do banco de dados
- **postgres**: Superusuário do PostgreSQL

### Logs
Todos os logs são mantidos em:
- `/var/log/cadeia_dominial/` - Logs da aplicação
- `/var/log/nginx/` - Logs do Nginx
- `/var/log/supervisor/` - Logs do Supervisor

## Contato e Suporte

Para problemas ou dúvidas sobre o deploy:
1. Verificar logs da aplicação
2. Verificar status dos serviços
3. Consultar este README
4. Verificar documentação do Django 