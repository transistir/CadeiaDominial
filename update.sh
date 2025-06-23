#!/bin/bash

# Script de Atualização para Cadeia Dominial
# Servidor Debian 12

set -e

echo "=== Atualização Cadeia Dominial ==="
echo "Servidor: 46.62.152.252"
echo "Data: $(date)"
echo ""

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then
    echo "Este script deve ser executado como root"
    exit 1
fi

# 1. Parar aplicação
log_info "Parando aplicação..."
supervisorctl stop cadeia_dominial

# 2. Fazer backup do banco (opcional)
log_info "Fazendo backup do banco de dados..."
BACKUP_FILE="/home/cadeia/backup_$(date +%Y%m%d_%H%M%S).sql"
sudo -u postgres pg_dump cadeia_dominial > "$BACKUP_FILE"
log_info "Backup salvo em: $BACKUP_FILE"

# 3. Atualizar código
log_info "Atualizando código..."
su - cadeia -c "cd /home/cadeia/cadeia_dominial && git pull origin main"

# 4. Atualizar dependências
log_info "Atualizando dependências Python..."
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && pip install -r requirements.txt"

# 5. Executar migrações
log_info "Executando migrações..."
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && python manage.py migrate --settings=cadeia_dominial.settings_prod"

# 6. Coletar arquivos estáticos
log_info "Coletando arquivos estáticos..."
su - cadeia -c "cd /home/cadeia/cadeia_dominial && source venv/bin/activate && python manage.py collectstatic --settings=cadeia_dominial.settings_prod --noinput"

# 7. Configurar permissões
log_info "Configurando permissões..."
chown -R cadeia:cadeia /home/cadeia/cadeia_dominial

# 8. Reiniciar aplicação
log_info "Reiniciando aplicação..."
supervisorctl start cadeia_dominial

# 9. Verificar status
log_info "Verificando status..."
sleep 3
supervisorctl status cadeia_dominial

# 10. Verificar logs
log_info "Últimas linhas do log da aplicação:"
tail -n 10 /var/log/cadeia_dominial/gunicorn.log

echo ""
log_info "Atualização concluída com sucesso!"
echo "URL: http://46.62.152.252"
echo ""
echo "Para verificar logs em tempo real:"
echo "tail -f /var/log/cadeia_dominial/gunicorn.log" 