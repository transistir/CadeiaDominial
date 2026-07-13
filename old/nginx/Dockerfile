FROM nginx:alpine

# Instalar dependências necessárias
RUN apk add --no-cache \
    certbot \
    curl \
    inotify-tools \
    bash \
    openssl

# Criar diretórios necessários
RUN mkdir -p /var/www/certbot \
    && mkdir -p /etc/letsencrypt/live/localhost

# Gerar certificados dummy iniciais
RUN openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/letsencrypt/live/localhost/privkey.pem \
    -out /etc/letsencrypt/live/localhost/fullchain.pem \
    -subj "/C=BR/ST=SP/L=SP/O=CadeiaDominial/CN=localhost"

# Copiar configurações do Nginx
COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/default.http.conf /etc/nginx/conf.d/default.http.conf
COPY conf.d/default.https.conf /etc/nginx/conf.d/default.https.conf

# Copiar scripts de SSL
COPY ssl-init.sh /usr/local/bin/ssl-init.sh
COPY ssl-renew.sh /usr/local/bin/ssl-renew.sh

# Dar permissão de execução aos scripts
RUN chmod +x /usr/local/bin/ssl-init.sh \
    && chmod +x /usr/local/bin/ssl-renew.sh

# Expor portas
EXPOSE 80 443

# Script de inicialização
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"] 