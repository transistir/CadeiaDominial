#!/bin/bash

# Script auxiliar para inicialização de SSL
# Este script é chamado pelo docker-entrypoint.sh

set -e

log_info() {
    echo -e "\033[1;32m[SSL-INIT]\033[0m $1"
}

log_warn() {
    echo -e "\033[1;33m[SSL-INIT]\033[0m $1"
}

log_error() {
    echo -e "\033[1;31m[SSL-INIT]\033[0m $1"
}

# Verificar se os certificados reais existem
check_real_certificates() {
    local domain=$1
    if [ -f "/etc/letsencrypt/live/$domain/fullchain.pem" ] && \
       [ -f "/etc/letsencrypt/live/$domain/privkey.pem" ]; then
        return 0
    else
        return 1
    fi
}

# Obter certificados SSL
obtain_certificates() {
    local domain=$1
    local email=$2
    
    log_info "Solicitando certificados SSL para $domain"
    
    # Tentar obter certificados
    if certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "$email" \
        --agree-tos \
        --no-eff-email \
        --domains "$domain" \
        --non-interactive; then
        
        log_info "Certificados SSL obtidos com sucesso!"
        return 0
    else
        log_warn "Não foi possível obter certificados SSL"
        return 1
    fi
}

# Função principal
main() {
    local domain="${1:-localhost}"
    local email="${2:-admin@localhost}"
    
    log_info "Inicializando SSL para $domain"
    
    if [ "$domain" = "localhost" ] || [ "$domain" = "127.0.0.1" ]; then
        log_warn "Domínio local detectado - SSL não será configurado"
        exit 0
    fi
    
    # Verificar se já existem certificados reais
    if check_real_certificates "$domain"; then
        log_info "Certificados SSL já existem para $domain"
        exit 0
    fi
    
    # Tentar obter certificados
    if obtain_certificates "$domain" "$email"; then
        log_info "SSL inicializado com sucesso para $domain"
    else
        log_warn "SSL não foi inicializado - sistema funcionará via HTTP"
    fi
}

# Executar função principal
main "$@" 