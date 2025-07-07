#!/bin/bash

# Script para importar todos os cartórios do Brasil
# Executa no servidor via Docker

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Função para log colorido
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

log_stats() {
    echo -e "${CYAN}[STATS]${NC} $1"
}

# Verificar se estamos no diretório correto
if [ ! -f "docker-compose.yml" ]; then
    log_error "Este script deve ser executado no diretório raiz do projeto"
    exit 1
fi

# Verificar se os containers estão rodando
log_step "Verificando status dos containers..."
if ! docker-compose ps | grep -q "Up"; then
    log_error "Containers não estão rodando. Execute 'docker-compose up -d' primeiro."
    exit 1
fi

# Verificar se o container web está saudável
if ! docker-compose ps web | grep -q "healthy"; then
    log_error "Container web não está saudável. Aguarde um pouco e tente novamente."
    exit 1
fi

log_success "Containers estão funcionando corretamente!"

# Verificar cartórios existentes
log_step "Verificando cartórios existentes..."
CARTORIOS_EXISTENTES=$(docker exec cadeia_dominial_web python manage.py shell -c "from dominial.models import Cartorios; print(Cartorios.objects.count())" 2>/dev/null || echo "0")
log_stats "Cartórios existentes no banco: $CARTORIOS_EXISTENTES"

# Verificar cartórios por estado
log_step "Verificando cartórios por estado..."
docker exec cadeia_dominial_web python manage.py shell -c "
from dominial.models import Cartorios
from collections import Counter
estados = Cartorios.objects.values_list('estado', flat=True)
contador = Counter(estados)
print('Estados com cartórios:')
for estado, count in sorted(contador.items()):
    print(f'  {estado}: {count} cartórios')
" 2>/dev/null || log_warning "Não foi possível verificar cartórios por estado"

# Perguntar se quer continuar
if [ "$CARTORIOS_EXISTENTES" -gt 0 ]; then
    log_warning "Já existem $CARTORIOS_EXISTENTES cartórios no banco."
    read -p "Deseja continuar com a importação? (s/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        log_info "Importação cancelada pelo usuário."
        exit 0
    fi
fi

# Criar backup do banco antes da importação
log_step "Criando backup do banco de dados..."
BACKUP_FILE="backup_cartorios_$(date +%Y%m%d_%H%M%S).sql"
if docker exec cadeia_dominial_db pg_dump -U cadeia_user cadeia_dominial > "$BACKUP_FILE" 2>/dev/null; then
    log_success "Backup criado: $BACKUP_FILE"
else
    log_warning "Não foi possível criar backup do banco. Continuando mesmo assim..."
fi

# Executar o script de importação
log_step "Iniciando importação de todos os cartórios..."
log_info "Este processo pode levar várias horas."
log_info "O log será salvo em importacao_cartorios.log"
log_info "Você pode acompanhar o progresso com: tail -f importacao_cartorios.log"

# Perguntar se quer executar em background
read -p "Deseja executar em background? (s/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    log_info "Executando importação em background..."
    nohup docker exec cadeia_dominial_web python /app/scripts/importar_todos_cartorios.py > importacao_cartorios.log 2>&1 &
    PID=$!
    log_success "Importação iniciada em background (PID: $PID)"
    log_info "Para acompanhar o progresso: tail -f importacao_cartorios.log"
    log_info "Para verificar se ainda está rodando: ps aux | grep $PID"
    exit 0
fi

# Executar o script Python dentro do container
log_info "Executando importação..."
docker exec cadeia_dominial_web python /app/scripts/importar_todos_cartorios.py

# Verificar resultado
if [ $? -eq 0 ]; then
    log_success "Importação concluída com sucesso!"
    
    # Verificar cartórios finais
    CARTORIOS_FINAIS=$(docker exec cadeia_dominial_web python manage.py shell -c "from dominial.models import Cartorios; print(Cartorios.objects.count())" 2>/dev/null || echo "0")
    NOVOS_CARTORIOS=$((CARTORIOS_FINAIS - CARTORIOS_EXISTENTES))
    
    log_success "📊 Relatório Final:"
    log_success "  - Cartórios antes: $CARTORIOS_EXISTENTES"
    log_success "  - Cartórios depois: $CARTORIOS_FINAIS"
    log_success "  - Novos cartórios: $NOVOS_CARTORIOS"
    
    # Mostrar estatísticas por estado
    log_step "Estatísticas finais por estado:"
    docker exec cadeia_dominial_web python manage.py shell -c "
from dominial.models import Cartorios
from collections import Counter
estados = Cartorios.objects.values_list('estado', flat=True)
contador = Counter(estados)
for estado, count in sorted(contador.items()):
    print(f'  {estado}: {count} cartórios')
" 2>/dev/null || log_warning "Não foi possível obter estatísticas por estado"
    
    log_success "✅ Importação de cartórios finalizada com sucesso!"
    log_info "📄 Log completo disponível em: importacao_cartorios.log"
    
else
    log_error "❌ Erro durante a importação!"
    log_info "📄 Verifique o log em: importacao_cartorios.log"
    exit 1
fi 