#!/bin/bash

# Script de Deploy em Produção - Migração de Matrícula
# Usa Docker Compose

set -e

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

echo "🚀 Deploy - Migração de Constraint de Matrícula"
echo "================================================"
echo ""

# 1. Backup
log_info "1. Criando backup do banco..."
BACKUP_FILE="backup_antes_migracao_matricula_$(date +%Y%m%d_%H%M%S).sql"
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > "$BACKUP_FILE"
if [ $? -eq 0 ]; then
    log_info "✅ Backup criado: $BACKUP_FILE"
    ls -lh "$BACKUP_FILE"
else
    log_error "❌ Falha ao criar backup! Abortando..."
    exit 1
fi

# 2. Atualizar código
log_info "2. Atualizando código..."
git pull origin main
if [ $? -ne 0 ]; then
    log_error "❌ Falha ao atualizar código! Abortando..."
    exit 1
fi
log_info "✅ Código atualizado"

# 3. Reconstruir container web
log_info "3. Reconstruindo container web..."
docker-compose up -d --build web
if [ $? -ne 0 ]; then
    log_error "❌ Falha ao reconstruir container! Abortando..."
    exit 1
fi
log_info "✅ Container reconstruído"

# 4. Aguardar web ficar healthy
log_info "4. Aguardando web ficar healthy (pode levar até 60 segundos)..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' cadeia_dominial_web 2>/dev/null || echo "starting")
    if [ "$HEALTH" = "healthy" ]; then
        log_info "✅ Web está healthy!"
        break
    fi
    echo -n "."
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ "$HEALTH" != "healthy" ]; then
    log_warn "⚠️  Web ainda não está healthy, mas continuando..."
    log_warn "   Verifique os logs: docker-compose logs web"
fi

# 5. Verificar dados
log_info "5. Verificando dados antes da migração..."
VERIFICATION_OUTPUT=$(docker-compose exec web python manage.py verificar_matricula_constraint 2>&1)
echo "$VERIFICATION_OUTPUT"

if echo "$VERIFICATION_OUTPUT" | grep -q "PROBLEMAS ENCONTRADOS"; then
    log_error "❌ Problemas encontrados na verificação! Abortando migração."
    log_warn "Resolva os problemas antes de continuar."
    log_warn "Backup salvo em: $BACKUP_FILE"
    exit 1
fi

if echo "$VERIFICATION_OUTPUT" | grep -q "NENHUM PROBLEMA ENCONTRADO"; then
    log_info "✅ Verificação passou! Prosseguindo com migração..."
else
    log_warn "⚠️  Verificação não retornou resultado esperado. Continuando com cuidado..."
fi

# 6. Aplicar migração
log_info "6. Aplicando migração..."
docker-compose exec web python manage.py migrate
if [ $? -ne 0 ]; then
    log_error "❌ Falha ao aplicar migração!"
    log_warn "Backup disponível em: $BACKUP_FILE"
    exit 1
fi
log_info "✅ Migração aplicada"

# 7. Verificar migração
log_info "7. Verificando se migração foi aplicada..."
MIGRATION_CHECK=$(docker-compose exec web python manage.py showmigrations dominial | grep 0042)
if echo "$MIGRATION_CHECK" | grep -q "\[X\]"; then
    log_info "✅ Migração 0042 aplicada com sucesso!"
else
    log_warn "⚠️  Migração 0042 não encontrada ou não aplicada"
fi

# 8. Subir nginx (agora que web está healthy)
log_info "8. Subindo nginx..."
docker-compose up -d nginx
if [ $? -ne 0 ]; then
    log_warn "⚠️  Nginx teve problemas ao subir. Verificando..."
    docker-compose logs nginx --tail=20
fi

# 9. Verificar status final
log_info "9. Verificando status final..."
sleep 5
docker-compose ps

# 10. Verificar logs
log_info "10. Últimas linhas dos logs..."
docker-compose logs web --tail=10

echo ""
log_info "✅ Deploy concluído!"
echo ""
echo "📋 Próximos passos:"
echo "   1. Testar cadastro de imóvel com matrícula existente em outro cartório"
echo "   2. Verificar se erro aparece ao tentar cadastrar no mesmo cartório"
echo "   3. Monitorar logs: docker-compose logs -f web"
echo ""
echo "💾 Backup salvo em: $BACKUP_FILE"



