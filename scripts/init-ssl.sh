#!/bin/bash

# Script para inicialização e configuração automática do SSL
# Este script configura o SSL automaticamente quando os certificados estão prontos

set -e

echo "🔐 Iniciando configuração SSL..."

# Verificar se as variáveis de ambiente estão definidas
if [ -z "$DOMAIN_NAME" ]; then
    echo "❌ ERRO: DOMAIN_NAME não está definida!"
    exit 1
fi

if [ -z "$CERTBOT_EMAIL" ]; then
    echo "❌ ERRO: CERTBOT_EMAIL não está definida!"
    exit 1
fi

# Função para verificar se os certificados existem
check_certificates() {
    if [ -f "/etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem" ] && \
       [ -f "/etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem" ]; then
        return 0
    else
        return 1
    fi
}

# Função para ativar SSL no Nginx
activate_ssl() {
    echo "✅ Certificados encontrados! Ativando SSL..."
    
    # Descomentar as linhas SSL no arquivo de configuração
    sed -i 's/# ssl_certificate/ssl_certificate/g' /etc/nginx/conf.d/default.conf
    sed -i 's/# ssl_certificate_key/ssl_certificate_key/g' /etc/nginx/conf.d/default.conf
    
    # Adicionar redirecionamento HTTP para HTTPS
    sed -i '/server {/a\    # Redirecionar HTTP para HTTPS\n    return 301 https://$server_name$request_uri;' /etc/nginx/conf.d/default.conf
    
    # Recarregar configuração do Nginx
    nginx -s reload
    
    echo "✅ SSL ativado com sucesso!"
}

# Função para obter certificados SSL
get_certificates() {
    echo "🔍 Verificando certificados SSL..."
    
    if check_certificates; then
        echo "✅ Certificados SSL já existem!"
        activate_ssl
        return 0
    fi
    
    echo "📝 Solicitando certificados SSL..."
    
    # Tentar obter certificados
    certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "$CERTBOT_EMAIL" \
        --agree-tos \
        --no-eff-email \
        --domains "$DOMAIN_NAME" \
        --non-interactive || {
        echo "⚠️  Não foi possível obter certificados SSL agora."
        echo "   O sistema continuará funcionando via HTTP."
        echo "   Os certificados serão solicitados novamente em 24h."
        return 1
    }
    
    if check_certificates; then
        echo "✅ Certificados SSL obtidos com sucesso!"
        activate_ssl
    else
        echo "❌ Falha ao obter certificados SSL."
        return 1
    fi
}

# Função principal
main() {
    echo "🚀 Iniciando configuração SSL para $DOMAIN_NAME..."
    
    # Aguardar um pouco para o Nginx inicializar
    sleep 5
    
    # Tentar obter certificados
    if get_certificates; then
        echo "✅ Configuração SSL concluída com sucesso!"
    else
        echo "⚠️  Configuração SSL não concluída, mas o sistema está funcionando."
    fi
    
    # Configurar renovação automática
    echo "🔄 Configurando renovação automática..."
    
    # Criar script de renovação
    cat > /etc/periodic/daily/renew-ssl << 'EOF'
#!/bin/sh
certbot renew --quiet --webroot --webroot-path=/var/www/certbot
nginx -s reload
EOF
    
    chmod +x /etc/periodic/daily/renew-ssl
    
    echo "✅ Renovação automática configurada!"
}

# Executar função principal
main "$@" 