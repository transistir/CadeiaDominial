# Guia de Deploy - Servidor Debian 12

## Informações do Servidor
- **IP**: 46.62.152.252
- **Sistema**: Debian 12
- **Aplicação**: Django Cadeia Dominial

## Pré-requisitos

### 1. Conectar ao Servidor
```bash
ssh root@46.62.152.252
```

### 2. Atualizar o Sistema
```bash
apt update && apt upgrade -y
```

### 3. Instalar Dependências do Sistema
```bash
# Python e ferramentas básicas
apt install -y python3 python3-pip python3-venv python3-dev

# Nginx (servidor web)
apt install -y nginx

# PostgreSQL (banco de dados)
apt install -y postgresql postgresql-contrib

# Git (para clonar o repositório)
apt install -y git

# Supervisor (para gerenciar processos)
apt install -y supervisor

# Ferramentas úteis
apt install -y curl wget unzip
```

## Configuração do Banco de Dados PostgreSQL

### 1. Configurar PostgreSQL
```bash
# Acessar PostgreSQL como superusuário
sudo -u postgres psql

# Criar banco de dados
CREATE DATABASE cadeia_dominial;

# Criar usuário
CREATE USER cadeia_user WITH PASSWORD 'sua_senha_segura_aqui';

# Dar permissões
GRANT ALL PRIVILEGES ON DATABASE cadeia_dominial TO cadeia_user;

# Sair do PostgreSQL
\q
```

### 2. Configurar Acesso Remoto (opcional)
```bash
# Editar configuração do PostgreSQL
nano /etc/postgresql/*/main/postgresql.conf

# Descomentar e alterar:
# listen_addresses = '*'

# Editar pg_hba.conf
nano /etc/postgresql/*/main/pg_hba.conf

# Adicionar linha para permitir conexões:
# host    all             all             0.0.0.0/0               md5

# Reiniciar PostgreSQL
systemctl restart postgresql
```

## Configuração da Aplicação

### 1. Criar Usuário para a Aplicação
```bash
# Criar usuário
adduser cadeia --disabled-password --gecos ""

# Adicionar ao grupo sudo (se necessário)
usermod -aG sudo cadeia
```

### 2. Clonar o Repositório
```bash
# Mudar para o usuário da aplicação
su - cadeia

# Clonar o repositório
git clone https://github.com/transistir/CadeiaDominial.git /home/cadeia/cadeia_dominial

# Voltar para root
exit
```

### 3. Configurar Ambiente Python
```bash
# Mudar para o diretório da aplicação
cd /home/cadeia/cadeia_dominial

# Criar ambiente virtual
python3 -m venv venv

# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Instalar gunicorn (servidor WSGI)
pip install gunicorn
```

### 4. Configurar Variáveis de Ambiente
```bash
# Criar arquivo .env
nano /home/cadeia/cadeia_dominial/.env
```

Conteúdo do arquivo `.env`:
```env
DEBUG=False
SECRET_KEY=sua_chave_secreta_muito_segura_aqui
DATABASE_URL=postgresql://cadeia_user:sua_senha_segura_aqui@localhost/cadeia_dominial
ALLOWED_HOSTS=46.62.152.252,localhost,127.0.0.1
```

### 5. Configurar Settings de Produção
```bash
# Editar settings_prod.py
nano /home/cadeia/cadeia_dominial/cadeia_dominial/settings_prod.py
```

## Configuração do Gunicorn

### 1. Criar Arquivo de Configuração do Gunicorn
```bash
nano /home/cadeia/cadeia_dominial/gunicorn.conf.py
```

Conteúdo:
```python
# Gunicorn configuration file
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
```

### 2. Configurar Supervisor
```bash
nano /etc/supervisor/conf.d/cadeia_dominial.conf
```

Conteúdo:
```ini
[program:cadeia_dominial]
command=/home/cadeia/cadeia_dominial/venv/bin/gunicorn --config /home/cadeia/cadeia_dominial/gunicorn.conf.py cadeia_dominial.wsgi:application
directory=/home/cadeia/cadeia_dominial
user=cadeia
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/cadeia_dominial/gunicorn.log
environment=DJANGO_SETTINGS_MODULE="cadeia_dominial.settings_prod"
```

### 3. Criar Diretório de Logs
```bash
mkdir -p /var/log/cadeia_dominial
chown cadeia:cadeia /var/log/cadeia_dominial
```

## Configuração do Nginx

### 1. Criar Configuração do Site
```bash
nano /etc/nginx/sites-available/cadeia_dominial
```

Conteúdo:
```nginx
server {
    listen 80;
    server_name 46.62.152.252;

    # Logs
    access_log /var/log/nginx/cadeia_dominial_access.log;
    error_log /var/log/nginx/cadeia_dominial_error.log;

    # Arquivos estáticos
    location /static/ {
        alias /home/cadeia/cadeia_dominial/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy para aplicação Django
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Configurações de segurança
    client_max_body_size 10M;
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

### 2. Ativar o Site
```bash
# Criar link simbólico
ln -s /etc/nginx/sites-available/cadeia_dominial /etc/nginx/sites-enabled/

# Remover site padrão (opcional)
rm /etc/nginx/sites-enabled/default

# Testar configuração
nginx -t

# Reiniciar Nginx
systemctl restart nginx
```

## Deploy da Aplicação

### 1. Executar Migrações
```bash
# Mudar para usuário da aplicação
su - cadeia
cd /home/cadeia/cadeia_dominial
source venv/bin/activate

# Executar migrações
python manage.py migrate --settings=cadeia_dominial.settings_prod

# Coletar arquivos estáticos
python manage.py collectstatic --settings=cadeia_dominial.settings_prod --noinput

# Criar superusuário
python manage.py createsuperuser --settings=cadeia_dominial.settings_prod

# Voltar para root
exit
```

### 2. Iniciar Serviços
```bash
# Recarregar configurações do supervisor
supervisorctl reread
supervisorctl update

# Iniciar aplicação
supervisorctl start cadeia_dominial

# Verificar status
supervisorctl status cadeia_dominial
```

### 3. Configurar Firewall
```bash
# Instalar ufw (se não estiver instalado)
apt install -y ufw

# Configurar regras
ufw allow ssh
ufw allow 80
ufw allow 443

# Ativar firewall
ufw enable
```

## Configuração de SSL (Opcional)

### 1. Instalar Certbot
```bash
apt install -y certbot python3-certbot-nginx
```

### 2. Obter Certificado SSL
```bash
certbot --nginx -d seu-dominio.com
```

## Comandos Úteis para Manutenção

### Atualizar Aplicação
```bash
# Conectar ao servidor
ssh root@46.62.152.252

# Parar aplicação
supervisorctl stop cadeia_dominial

# Atualizar código
su - cadeia
cd /home/cadeia/cadeia_dominial
git pull origin main

# Ativar ambiente virtual
source venv/bin/activate

# Instalar novas dependências
pip install -r requirements.txt

# Executar migrações
python manage.py migrate --settings=cadeia_dominial.settings_prod

# Coletar arquivos estáticos
python manage.py collectstatic --settings=cadeia_dominial.settings_prod --noinput

# Voltar para root
exit

# Reiniciar aplicação
supervisorctl restart cadeia_dominial
```

### Verificar Logs
```bash
# Logs da aplicação
tail -f /var/log/cadeia_dominial/gunicorn.log

# Logs do Nginx
tail -f /var/log/nginx/cadeia_dominial_error.log

# Logs do supervisor
supervisorctl tail cadeia_dominial
```

### Backup do Banco de Dados
```bash
# Backup
pg_dump -U cadeia_user -h localhost cadeia_dominial > backup_$(date +%Y%m%d_%H%M%S).sql

# Restaurar
psql -U cadeia_user -h localhost cadeia_dominial < backup.sql
```

## Monitoramento

### 1. Verificar Status dos Serviços
```bash
systemctl status nginx
systemctl status postgresql
supervisorctl status cadeia_dominial
```

### 2. Verificar Uso de Recursos
```bash
# CPU e memória
htop

# Espaço em disco
df -h

# Logs do sistema
journalctl -f
```

## Troubleshooting

### Problemas Comuns

1. **Erro 502 Bad Gateway**
   - Verificar se o Gunicorn está rodando: `supervisorctl status cadeia_dominial`
   - Verificar logs: `tail -f /var/log/cadeia_dominial/gunicorn.log`

2. **Erro de Conexão com Banco**
   - Verificar se PostgreSQL está rodando: `systemctl status postgresql`
   - Verificar configurações de conexão no `.env`

3. **Arquivos Estáticos não Carregam**
   - Verificar se `collectstatic` foi executado
   - Verificar permissões do diretório `/staticfiles/`

4. **Erro de Permissões**
   - Verificar proprietário dos arquivos: `ls -la /home/cadeia/cadeia_dominial/`
   - Ajustar permissões se necessário: `chown -R cadeia:cadeia /home/cadeia/cadeia_dominial/` 