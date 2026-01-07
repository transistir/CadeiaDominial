#!/bin/bash

# Script para renovação automática de certificados SSL
# Este script é executado periodicamente pelo cron

set -e

log_info() {
    echo -e "\033[1;32m[SSL-RENEW]\033[0m $1"
}

log_warn() {
    echo -e "\033[1;33m[SSL-RENEW]\033[0m $1"
}

log_error() {
    echo -e "\033[1;31m[SSL-RENEW]\033[0m $1"
}

# Verificar se há certificados para renovar
check_certificates() {
    local domain=$1
    if [ -f "/etc/letsencrypt/live/$domain/fullchain.pem" ] && \
       [ -f "/etc/letsencrypt/live/$domain/privkey.pem" ]; then
        return 0
    else
        return 1
    fi
}

# Renovar certificados
renew_certificates() {
    log_info "Verificando renovação de certificados SSL"
    
    # Tentar renovar certificados
    if certbot renew --quiet --webroot --webroot-path=/var/www/certbot; then
        log_info "Certificados SSL renovados com sucesso!"
        
        # Recarregar Nginx se houve renovação
        log_info "Recarregando Nginx..."
        nginx -s reload
        
        log_info "Renovação SSL concluída!"
        return 0
    else
        log_warn "Nenhum certificado precisava ser renovado"
        return 1
    fi
}

# Função principal
main() {
    local domain="${DOMAIN_NAME:-localhost}"
    
    log_info "Iniciando verificação de renovação SSL para $domain"
    
    if [ "$domain" = "localhost" ] || [ "$domain" = "127.0.0.1" ]; then
        log_warn "Domínio local detectado - renovação SSL não aplicável"
        exit 0
    fi
    
    # Verificar se existem certificados
    if ! check_certificates "$domain"; then
        log_warn "Nenhum certificado SSL encontrado para $domain"
        exit 0
    fi
    
    # Tentar renovar certificados
    renew_certificates
}

# Executar função principal
main "$@" 