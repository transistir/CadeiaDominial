#!/bin/bash

# Script para inicializar certificados SSL com Let's Encrypt
# Este script deve ser executado após a primeira inicialização dos containers

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
if [ -z "$DOMAIN_NAME" ] || [ -z "$CERTBOT_EMAIL" ]; then
    log_error "DOMAIN_NAME e CERTBOT_EMAIL devem estar definidos no arquivo .env"
    exit 1
fi

log_info "Iniciando configuração SSL para $DOMAIN_NAME"

# Aguardar o Nginx estar pronto
log_info "Aguardando Nginx estar pronto..."
sleep 10

# Criar certificado inicial
log_info "Solicitando certificado SSL..."
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$CERTBOT_EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN_NAME"

if [ $? -eq 0 ]; then
    log_info "Certificado SSL criado com sucesso!"
    
    # Recarregar Nginx
    log_info "Recarregando Nginx..."
    docker-compose exec nginx nginx -s reload
    
    log_info "SSL configurado com sucesso!"
    log_info "Acesse https://$DOMAIN_NAME"
else
    log_error "Falha ao criar certificado SSL"
    exit 1
fi 