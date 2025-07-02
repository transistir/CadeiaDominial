#!/bin/bash

# Script para ativar SSL no Nginx após certificados serem gerados
# Este script é executado após o certbot gerar os certificados

set -e

echo "🔐 Ativando SSL no Nginx..."

# Verificar se os certificados existem
if [ -f "/etc/letsencrypt/live/cadeiadominial.com.br/fullchain.pem" ] && \
   [ -f "/etc/letsencrypt/live/cadeiadominial.com.br/privkey.pem" ]; then
    
    echo "✅ Certificados SSL encontrados!"
    
    # Adicionar redirecionamento HTTP para HTTPS
    sed -i '/server {/a\    # Redirecionar HTTP para HTTPS\n    return 301 https://$server_name$request_uri;' /etc/nginx/conf.d/default.conf
    
    # Recarregar configuração do Nginx
    nginx -s reload
    
    echo "✅ SSL ativado com sucesso!"
    echo "🌐 Acesse https://cadeiadominial.com.br"
else
    echo "⚠️  Certificados SSL não encontrados."
    echo "   O sistema continuará funcionando via HTTP."
    echo "   Execute: docker-compose run --rm certbot"
fi 