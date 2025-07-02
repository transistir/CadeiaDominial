#!/bin/bash

# Script principal de inicialização do Cadeia Dominial com Docker
# Este script configura e inicia todo o ambiente

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

log_step "=== Inicializando Cadeia Dominial ==="
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
sleep 15

# Verificar se os containers estão rodando
log_step "Verificando status dos containers..."
docker-compose ps

# Executar migrações
log_step "Executando migrações do banco de dados..."
docker-compose exec web python manage.py migrate

# Coletar arquivos estáticos
log_step "Coletando arquivos estáticos..."
docker-compose exec web python manage.py collectstatic --noinput

# Criar superusuário se não existir
log_step "Verificando superusuário..."
docker-compose exec web python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superusuário criado: admin/admin123')
else:
    print('Superusuário já existe')
"

# Configurar SSL se DOMAIN_NAME estiver configurado
if [ "$DOMAIN_NAME" != "localhost" ] && [ "$DOMAIN_NAME" != "127.0.0.1" ]; then
    log_step "Configurando SSL..."
    chmod +x scripts/init-ssl.sh
    ./scripts/init-ssl.sh
else
    log_warn "DOMAIN_NAME não configurado. SSL não será configurado."
fi

log_step "=== Inicialização Concluída ==="
log_info "Aplicação disponível em:"
if [ "$DOMAIN_NAME" != "localhost" ] && [ "$DOMAIN_NAME" != "127.0.0.1" ]; then
    log_info "  HTTPS: https://$DOMAIN_NAME"
else
    log_info "  HTTP: http://localhost"
fi
log_info ""
log_info "Comandos úteis:"
log_info "  Ver logs: docker-compose logs -f"
log_info "  Parar: docker-compose down"
log_info "  Reiniciar: docker-compose restart"
log_info "  Backup DB: docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup.sql" 