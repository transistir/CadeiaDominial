#!/bin/bash

set -e

# Função para log colorido
log_info() {
    echo -e "\033[1;32m[INFO]\033[0m $1"
}

log_warn() {
    echo -e "\033[1;33m[WARN]\033[0m $1"
}

log_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

# Função para verificar se os certificados reais existem
check_real_certificates() {
    local domain=$1
    if [ -f "/etc/letsencrypt/live/$domain/fullchain.pem" ] && \
       [ -f "/etc/letsencrypt/live/$domain/privkey.pem" ]; then
        return 0
    else
        return 1
    fi
}

# Função para configurar Nginx com certificados
configure_nginx() {
    local domain=$1
    local use_ssl=$2
    
    log_info "Configurando Nginx para domínio: $domain (SSL: $use_ssl)"
    
    if [ "$use_ssl" = "true" ]; then
        cp /etc/nginx/conf.d/default.https.conf /etc/nginx/conf.d/default.conf
        sed -i "s/cadeiadominial.com.br/$domain/g" /etc/nginx/conf.d/default.conf
        log_info "SSL ativado para $domain"
    else
        cp /etc/nginx/conf.d/default.http.conf /etc/nginx/conf.d/default.conf
        sed -i "s/localhost/$domain/g" /etc/nginx/conf.d/default.conf
        log_info "Configuração HTTP ativada para $domain"
    fi
}

# Função para obter certificados SSL
obtain_ssl_certificates() {
    local domain=$1
    local email=$2
    
    log_info "Tentando obter certificados SSL para $domain"
    
    # Aguardar um pouco para garantir que o Nginx está rodando
    sleep 5
    
    # Tentar obter certificados
    if certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "$email" \
        --agree-tos \
        --no-eff-email \
        --domains "$domain" \
        --non-interactive; then
        
        log_info "Certificados SSL obtidos com sucesso para $domain"
        return 0
    else
        log_warn "Não foi possível obter certificados SSL para $domain"
        return 1
    fi
}

# Função para configurar renovação automática
setup_auto_renewal() {
    log_info "Configurando renovação automática de certificados"
    
    # Criar script de renovação
    cat > /etc/periodic/daily/renew-ssl << 'EOF'
#!/bin/sh
certbot renew --quiet --webroot --webroot-path=/var/www/certbot
nginx -s reload
EOF
    
    chmod +x /etc/periodic/daily/renew-ssl
    
    # Iniciar cron em background
    crond -f -d 8 &
    
    log_info "Renovação automática configurada"
}

# Função principal
main() {
    local domain="${DOMAIN_NAME:-localhost}"
    local email="${CERTBOT_EMAIL:-admin@localhost}"
    
    log_info "Iniciando Nginx com SSL automático"
    log_info "Domínio: $domain"
    log_info "Email: $email"
    
    # Verificar se é um domínio real (não localhost)
    if [ "$domain" = "localhost" ] || [ "$domain" = "127.0.0.1" ]; then
        log_warn "Usando domínio local - SSL não será configurado"
        configure_nginx "$domain" "false"
    else
        log_info "Domínio real detectado - verificando certificados SSL"
        
        # Verificar se existem certificados reais
        if check_real_certificates "$domain"; then
            log_info "Certificados SSL encontrados - configurando HTTPS"
            configure_nginx "$domain" "true"
        else
            log_warn "Certificados SSL não encontrados - configurando HTTP"
            configure_nginx "$domain" "false"
            log_info "Para obter certificados, execute: docker-compose exec nginx /usr/local/bin/ssl-init.sh $domain $email"
        fi
        
        # Configurar renovação automática
        setup_auto_renewal
    fi
    
    # Iniciar Nginx
    log_info "Iniciando Nginx..."
    exec nginx -g "daemon off;"
}

# Executar função principal
main "$@" 