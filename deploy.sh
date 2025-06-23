#!/bin/bash

# Script de Deploy para Servidor Debian 12
# Cadeia Dominial - Django Application

set -e  # Parar em caso de erro

echo "=== Deploy Cadeia Dominial ==="
echo "Servidor: 46.62.152.252"
echo "Data: $(date)"
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para log colorido
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then
    log_error "Este script deve ser executado como root"
    exit 1
fi

# 1. Atualizar sistema
log_info "Atualizando sistema..."
apt update && apt upgrade -y

# 2. Instalar dependências do sistema
log_info "Instalando dependências do sistema..."
apt install -y python3 python3-pip python3-venv python3-dev \
    nginx postgresql postgresql-contrib git supervisor \
    curl wget unzip ufw

# 3. Configurar PostgreSQL
log_info "Configurando PostgreSQL..."
systemctl start postgresql
systemctl enable postgresql

# Criar banco e usuário
sudo -u postgres psql -c "CREATE DATABASE cadeia_dominial;" || log_warn "Banco já existe"
sudo -u postgres psql -c "CREATE USER cadeia_user WITH PASSWORD 'sua_senha_segura_aqui';" || log_warn "Usuário já existe"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE cadeia_dominial TO cadeia_user;"

# 4. Criar usuário da aplicação
log_info "Criando usuário da aplicação..."
id -u cadeia &>/dev/null || adduser cadeia --disabled-password --gecos ""

# 5. Clonar/atualizar repositório
log_info "Configurando repositório..."
if [ ! -d "/home/cadeia/cadeia_dominial" ]; then
    su - cadeia -c "git clone https://github.com/transistir/CadeiaDominial.git /home/cadeia/cadeia_dominial"
else
    su - cadeia -c "cd /home/cadeia/cadeia_dominial && git pull origin main"
fi

# 6. Configurar ambiente Python
log_info "Configurando ambiente Python..."
cd /home/cadeia/cadeia_dominial

# Criar ambiente virtual se não existir
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Ativar ambiente e instalar dependências
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 7. Configurar variáveis de ambiente
log_info "Configurando variáveis de ambiente..."
cat > /home/cadeia/cadeia_dominial/.env << EOF
DEBUG=False
SECRET_KEY=sua_chave_secreta_muito_segura_aqui_$(date +%s)
DB_NAME=cadeia_dominial
DB_USER=cadeia_user
DB_PASSWORD=sua_senha_segura_aqui
DB_HOST=localhost
DB_PORT=5432
ALLOWED_HOSTS=46.62.152.252,localhost,127.0.0.1
EOF

# 8. Configurar Supervisor
log_info "Configurando Supervisor..."
mkdir -p /var/log/cadeia_dominial
chown cadeia:cadeia /var/log/cadeia_dominial

cat > /etc/supervisor/conf.d/cadeia_dominial.conf << EOF
[program:cadeia_dominial]
command=/home/cadeia/cadeia_dominial/venv/bin/gunicorn --config /home/cadeia/cadeia_dominial/gunicorn.conf.py cadeia_dominial.wsgi:application
directory=/home/cadeia/cadeia_dominial
user=cadeia
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/cadeia_dominial/gunicorn.log
environment=DJANGO_SETTINGS_MODULE="cadeia_dominial.settings_prod"
EOF

# 9. Configurar Nginx
log_info "Configurando Nginx..."
cat > /etc/nginx/sites-available/cadeia_dominial << EOF
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
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }

    # Configurações de segurança
    client_max_body_size 10M;
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
EOF

# Ativar site
ln -sf /etc/nginx/sites-available/cadeia_dominial /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 10. Executar migrações e setup da aplicação
log_info "Configurando aplicação Django..."
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && python manage.py migrate --settings=cadeia_dominial.settings_prod"
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && python manage.py collectstatic --settings=cadeia_dominial.settings_prod --noinput"

# 11. Configurar permissões
log_info "Configurando permissões..."
chown -R cadeia:cadeia /home/cadeia/cadeia_dominial

# 12. Iniciar serviços
log_info "Iniciando serviços..."
supervisorctl reread
supervisorctl update
supervisorctl start cadeia_dominial || supervisorctl restart cadeia_dominial

systemctl restart nginx
systemctl enable nginx

# 13. Configurar firewall
log_info "Configurando firewall..."
ufw allow ssh
ufw allow 80
ufw allow 443
ufw --force enable

# 14. Verificar status
log_info "Verificando status dos serviços..."
echo ""
echo "=== Status dos Serviços ==="
systemctl status nginx --no-pager -l
echo ""
systemctl status postgresql --no-pager -l
echo ""
supervisorctl status cadeia_dominial
echo ""

# 15. Informações finais
log_info "Deploy concluído com sucesso!"
echo ""
echo "=== Informações de Acesso ==="
echo "URL: http://46.62.152.252"
echo "Logs da aplicação: /var/log/cadeia_dominial/"
echo "Logs do Nginx: /var/log/nginx/"
echo ""
echo "=== Comandos Úteis ==="
echo "Ver logs da aplicação: tail -f /var/log/cadeia_dominial/gunicorn.log"
echo "Reiniciar aplicação: supervisorctl restart cadeia_dominial"
echo "Ver status: supervisorctl status cadeia_dominial"
echo "Atualizar código: cd /home/cadeia/cadeia_dominial && git pull && supervisorctl restart cadeia_dominial"
echo ""

log_info "Lembre-se de criar um superusuário:"
echo "su - cadeia"
echo "cd /home/cadeia/cadeia_dominial"
echo "source venv/bin/activate"
echo "python manage.py createsuperuser --settings=cadeia_dominial.settings_prod" 