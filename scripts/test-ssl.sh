#!/bin/bash

# Script para testar a funcionalidade SSL automática
# Uso: ./scripts/test-ssl.sh

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Carregar variáveis de ambiente
if [ -f ".env" ]; then
    source .env
else
    log_error "Arquivo .env não encontrado!"
    exit 1
fi

log_step "=== Testando SSL Automático ==="

# Verificar se containers estão rodando
log_step "Verificando status dos containers..."
if ! docker-compose ps | grep -q "Up"; then
    log_error "Containers não estão rodando. Execute: docker-compose up -d"
    exit 1
fi

# Verificar se Nginx está respondendo
log_step "Testando resposta do Nginx..."
if curl -f http://localhost/health > /dev/null 2>&1; then
    log_info "✅ Nginx está respondendo corretamente"
else
    log_error "❌ Nginx não está respondendo"
    exit 1
fi

# Verificar configuração do domínio
log_step "Verificando configuração do domínio..."
if [ "$DOMAIN_NAME" = "localhost" ] || [ "$DOMAIN_NAME" = "127.0.0.1" ]; then
    log_warn "⚠️  Domínio local detectado - SSL não será testado"
    log_info "Para testar SSL, configure DOMAIN_NAME no arquivo .env"
    exit 0
fi

log_info "Domínio configurado: $DOMAIN_NAME"

# Verificar certificados
log_step "Verificando certificados SSL..."
if docker-compose exec nginx test -f "/etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem"; then
    log_info "✅ Certificados SSL encontrados"
    
    # Verificar validade dos certificados
    cert_info=$(docker-compose exec nginx certbot certificates 2>/dev/null | grep -A 5 "$DOMAIN_NAME" || true)
    if echo "$cert_info" | grep -q "VALID"; then
        log_info "✅ Certificados SSL são válidos"
    else
        log_warn "⚠️  Certificados SSL podem estar inválidos"
    fi
else
    log_warn "⚠️  Certificados SSL não encontrados"
    log_info "Aguardando obtenção automática de certificados..."
fi

# Testar HTTPS (se certificados existirem)
log_step "Testando HTTPS..."
if curl -f -k https://localhost/health > /dev/null 2>&1; then
    log_info "✅ HTTPS está funcionando"
else
    log_warn "⚠️  HTTPS não está respondendo (pode ser normal se certificados ainda não foram obtidos)"
fi

# Verificar logs do SSL
log_step "Verificando logs do SSL..."
ssl_logs=$(docker-compose logs nginx 2>&1 | grep -i "ssl\|cert" | tail -5 || true)
if [ -n "$ssl_logs" ]; then
    log_info "Logs SSL encontrados:"
    echo "$ssl_logs"
else
    log_warn "Nenhum log SSL encontrado"
fi

# Verificar configuração do Nginx
log_step "Verificando configuração do Nginx..."
if docker-compose exec nginx nginx -t > /dev/null 2>&1; then
    log_info "✅ Configuração do Nginx é válida"
else
    log_error "❌ Configuração do Nginx é inválida"
    docker-compose exec nginx nginx -t
fi

# Verificar renovação automática
log_step "Verificando renovação automática..."
if docker-compose exec nginx test -f "/etc/periodic/daily/renew-ssl"; then
    log_info "✅ Script de renovação automática configurado"
else
    log_warn "⚠️  Script de renovação automática não encontrado"
fi

# Testar renovação manual
log_step "Testando renovação manual..."
if docker-compose exec nginx certbot renew --dry-run > /dev/null 2>&1; then
    log_info "✅ Renovação manual funciona corretamente"
else
    log_warn "⚠️  Renovação manual falhou (pode ser normal se não há certificados)"
fi

log_step "=== Resumo do Teste ==="
log_info "Status dos containers: ✅"
log_info "Nginx HTTP: ✅"
log_info "Domínio configurado: $DOMAIN_NAME"

if [ "$DOMAIN_NAME" != "localhost" ] && [ "$DOMAIN_NAME" != "127.0.0.1" ]; then
    if docker-compose exec nginx test -f "/etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem"; then
        log_info "SSL: ✅ Ativo"
        log_info "Acesse: https://$DOMAIN_NAME"
    else
        log_warn "SSL: ⏳ Aguardando certificados"
        log_info "Acesse: http://$DOMAIN_NAME"
        log_info "SSL será ativado automaticamente quando os certificados forem obtidos"
    fi
else
    log_warn "SSL: ❌ Não configurado (domínio local)"
fi

log_info ""
log_info "Comandos úteis:"
log_info "  Ver logs SSL: docker-compose logs nginx | grep -i ssl"
log_info "  Ver certificados: docker-compose exec nginx certbot certificates"
log_info "  Renovar manualmente: docker-compose exec nginx certbot renew" 