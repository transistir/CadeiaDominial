#!/bin/bash

# Script para ativar HTTPS no Nginx após a obtenção dos certificados Let's Encrypt
# Uso: ./scripts/enable-https.sh

set -e

CONF="nginx/conf.d/default.conf"
DOMAIN="cadeiadominial.com.br"
CERT_PATH="certbot/conf/live/$DOMAIN/fullchain.pem"
KEY_PATH="certbot/conf/live/$DOMAIN/privkey.pem"

# Função para exibir mensagens coloridas
info() { echo -e "\033[1;32m[INFO]\033[0m $1"; }
warn() { echo -e "\033[1;33m[AVISO]\033[0m $1"; }
err()  { echo -e "\033[1;31m[ERRO]\033[0m $1"; }

# 1. Verifica se os certificados existem
if [[ ! -f "$CERT_PATH" || ! -f "$KEY_PATH" ]]; then
    err "Certificados SSL não encontrados em $CERT_PATH e $KEY_PATH. Gere-os primeiro com o certbot."
    exit 1
fi

info "Certificados SSL encontrados."

# 2. Descomenta o bloco HTTPS se ainda estiver comentado
if grep -q "^# *server { *$" "$CONF"; then
    info "Descomentando bloco HTTPS no $CONF..."
    # Remove o caractere '#' do início das linhas do bloco HTTPS
    sed -i '/^# *server { *$/,/^# *}$/s/^# *//' "$CONF"
else
    warn "Bloco HTTPS já está descomentado."
fi

# 3. Adiciona redirecionamento HTTP->HTTPS se não existir
if ! grep -q "return 301 https://\$server_name\$request_uri;" "$CONF"; then
    info "Adicionando redirecionamento HTTP para HTTPS..."
    sed -i '/server_name cadeiadominial.com.br;/a \\n    # Redirecionar tudo para HTTPS\n    return 301 https://$server_name$request_uri;' "$CONF"
else
    warn "Redirecionamento HTTP->HTTPS já existe."
fi

# 4. Faz reload do Nginx via Docker
info "Recarregando Nginx..."
docker-compose exec nginx nginx -s reload || {
    warn "Não foi possível recarregar o Nginx automaticamente. Faça manualmente se necessário."
}

info "HTTPS ativado com sucesso! Acesse: https://$DOMAIN" 