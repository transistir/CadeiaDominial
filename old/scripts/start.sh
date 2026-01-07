#!/bin/bash

# Script principal de inicialização do Cadeia Dominial com Docker
# Este script configura e inicia todo o ambiente com SSL automático

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

# Verificar se Docker está instalado
if ! command -v docker &> /dev/null; then
    log_error "Docker não está instalado. Instale o Docker primeiro."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose não está instalado. Instale o Docker Compose primeiro."
    exit 1
fi

# Verificar se arquivo .env existe
if [ ! -f ".env" ]; then
    log_warn "Arquivo .env não encontrado. Copiando de env.example..."
    cp env.example .env
    log_info "Por favor, edite o arquivo .env com suas configurações antes de continuar."
    exit 1
fi

# Carregar variáveis de ambiente
source .env

log_step "=== Inicializando Cadeia Dominial com SSL Automático ==="
log_info "Domínio: $DOMAIN_NAME"
log_info "Email SSL: $CERTBOT_EMAIL"

# Parar containers existentes
log_step "Parando containers existentes..."
docker-compose down

# Construir e iniciar containers
log_step "Construindo e iniciando containers..."
docker-compose up -d --build

# Aguardar serviços estarem prontos
log_step "Aguardando serviços estarem prontos..."
sleep 20

# Verificar se os containers estão rodando
log_step "Verificando status dos containers..."
docker-compose ps

# Verificar se o banco está saudável
log_step "Verificando saúde do banco de dados..."
if ! docker-compose exec -T db pg_isready -U ${DB_USER:-cadeia_user} -d ${DB_NAME:-cadeia_dominial}; then
    log_error "Banco de dados não está respondendo. Verifique os logs:"
    docker-compose logs db
    exit 1
fi

# Executar migrações
log_step "Executando migrações do banco de dados..."
docker-compose exec web python manage.py migrate

# Coletar arquivos estáticos
log_step "Coletando arquivos estáticos..."
docker-compose exec web python manage.py collectstatic --noinput

# Verificar se o usuário admin existe
log_step "Verificando usuário administrador..."
docker-compose exec web python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='${ADMIN_USERNAME:-admin}').exists():
    User.objects.create_superuser(
        '${ADMIN_USERNAME:-admin}', 
        '${ADMIN_EMAIL:-admin@cadeiadominial.com.br}', 
        '${ADMIN_PASSWORD}'
    )
    print('✅ Usuário admin criado com sucesso!')
else:
    print('✅ Usuário admin já existe')
"

# Verificar status do SSL
log_step "Verificando status do SSL..."
if [ "$DOMAIN_NAME" != "localhost" ] && [ "$DOMAIN_NAME" != "127.0.0.1" ]; then
    log_info "Domínio real configurado: $DOMAIN_NAME"
    log_info "SSL será configurado automaticamente pelo container Nginx"
    log_info "Aguarde alguns minutos para os certificados serem obtidos..."
else
    log_warn "Domínio local detectado - SSL não será configurado"
fi

# Verificar se a aplicação está respondendo
log_step "Verificando se a aplicação está respondendo..."
sleep 10

if curl -f http://localhost/health > /dev/null 2>&1; then
    log_info "✅ Aplicação está respondendo corretamente!"
else
    log_warn "⚠️  Aplicação ainda não está respondendo. Verifique os logs:"
    docker-compose logs nginx
    docker-compose logs web
fi

log_step "=== Inicialização Concluída ==="
log_info "Aplicação disponível em:"
if [ "$DOMAIN_NAME" != "localhost" ] && [ "$DOMAIN_NAME" != "127.0.0.1" ]; then
    log_info "  HTTP:  http://$DOMAIN_NAME"
    log_info "  HTTPS: https://$DOMAIN_NAME (será ativado automaticamente)"
else
    log_info "  HTTP:  http://localhost"
fi
log_info ""
log_info "Comandos úteis:"
log_info "  Ver logs: docker-compose logs -f"
log_info "  Ver logs Nginx: docker-compose logs -f nginx"
log_info "  Ver logs Django: docker-compose logs -f web"
log_info "  Parar: docker-compose down"
log_info "  Reiniciar: docker-compose restart"
log_info "  Backup DB: docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup.sql"
log_info ""
log_info "Status SSL:"
log_info "  Ver certificados: docker-compose exec nginx certbot certificates"
log_info "  Renovar manualmente: docker-compose exec nginx certbot renew" 