#!/bin/bash

# Script para desenvolvimento local sem SSL
# Uso: ./scripts/dev.sh

set -e

# Cores para output
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

log_step "=== Iniciando Cadeia Dominial - Desenvolvimento Local ==="

# Parar containers de desenvolvimento se existirem
log_step "Parando containers de desenvolvimento..."
docker-compose -f docker-compose.dev.yml down

# Construir e iniciar containers de desenvolvimento
log_step "Construindo e iniciando containers de desenvolvimento..."
docker-compose -f docker-compose.dev.yml up -d --build

# Aguardar serviços estarem prontos
log_step "Aguardando serviços estarem prontos..."
sleep 10

# Verificar se os containers estão rodando
log_step "Verificando status dos containers..."
docker-compose -f docker-compose.dev.yml ps

log_step "=== Desenvolvimento Local Iniciado ==="
log_info "🌐 Aplicação disponível em: http://localhost:8000"
log_info "📊 Admin Django: http://localhost:8000/admin/"
log_info ""
log_info "Comandos úteis:"
log_info "  Ver logs: docker-compose -f docker-compose.dev.yml logs -f"
log_info "  Parar: docker-compose -f docker-compose.dev.yml down"
log_info "  Reiniciar: docker-compose -f docker-compose.dev.yml restart"
log_info "  Shell Django: docker-compose -f docker-compose.dev.yml exec web python manage.py shell" 