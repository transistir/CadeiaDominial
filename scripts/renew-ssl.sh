#!/bin/bash

# Script para renovação automática de certificados SSL
# Este script pode ser executado via cron para renovação automática

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar se as variáveis de ambiente estão definidas
if [ -z "$DOMAIN_NAME" ]; then
    log_error "DOMAIN_NAME deve estar definido no arquivo .env"
    exit 1
fi

log_info "Verificando renovação de certificados SSL para $DOMAIN_NAME"

# Tentar renovar certificados
if docker-compose run --rm certbot renew --quiet; then
    log_info "Certificados renovados com sucesso!"
    
    # Recarregar Nginx se houve renovação
    log_info "Recarregando Nginx..."
    docker-compose exec nginx nginx -s reload
    
    log_info "Renovação SSL concluída!"
else
    log_warn "Nenhum certificado precisava ser renovado ou houve erro na renovação"
fi 