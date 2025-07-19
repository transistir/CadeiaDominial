#!/bin/bash

# Script de inicialização do Cadeia Dominial
# Este script automatiza o processo de setup inicial do sistema

set -e  # Para o script se houver erro

echo "🚀 Iniciando setup do Cadeia Dominial..."

# Função para criar superusuário padrão
create_default_user() {
    echo "👤 Criando usuário padrão..."
    
    # Verifica se já existe um superusuário
    if python manage.py shell -c "from django.contrib.auth.models import User; print('Superusuário existe:', User.objects.filter(is_superuser=True).exists())" | grep -q "True"; then
        echo "✅ Superusuário já existe, pulando criação..."
        return
    fi
    
    # Obter credenciais das variáveis de ambiente
    ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
    ADMIN_EMAIL=${ADMIN_EMAIL:-admin@cadeiadominial.com.br}
    ADMIN_PASSWORD=${ADMIN_PASSWORD}
    
    # Verificar se a senha foi fornecida
    if [ -z "$ADMIN_PASSWORD" ]; then
        echo "❌ ERRO: Variável ADMIN_PASSWORD não foi definida!"
        echo ""
        echo "🔧 Para definir a senha do usuário admin, use uma das opções:"
        echo ""
        echo "Opção 1 - Variável de ambiente:"
        echo "   export ADMIN_PASSWORD='sua_senha_segura'"
        echo "   docker-compose up -d"
        echo ""
        echo "Opção 2 - Arquivo .env:"
        echo "   echo 'ADMIN_PASSWORD=sua_senha_segura' >> .env"
        echo "   docker-compose up -d"
        echo ""
        echo "Opção 3 - Linha de comando:"
        echo "   ADMIN_PASSWORD='sua_senha_segura' docker-compose up -d"
        echo ""
        echo "⚠️  IMPORTANTE: Use uma senha forte com pelo menos 8 caracteres!"
        exit 1
    fi
    
    # Validar senha (mínimo 8 caracteres)
    if [ ${#ADMIN_PASSWORD} -lt 8 ]; then
        echo "❌ ERRO: A senha deve ter pelo menos 8 caracteres!"
        echo "   Senha atual: ${#ADMIN_PASSWORD} caracteres"
        exit 1
    fi
    
    # Cria superusuário com credenciais das variáveis de ambiente
    echo "from django.contrib.auth.models import User; User.objects.create_superuser('$ADMIN_USERNAME', '$ADMIN_EMAIL', '$ADMIN_PASSWORD') if not User.objects.filter(username='$ADMIN_USERNAME').exists() else None" | python manage.py shell
    
    echo "✅ Usuário padrão criado:"
    echo "   Usuário: $ADMIN_USERNAME"
    echo "   Email: $ADMIN_EMAIL"
    echo "   Senha: [DEFINIDA VIA VARIÁVEL DE AMBIENTE]"
    echo ""
    echo "🔑 ACESSO AO SISTEMA:"
    echo "   URL: https://cadeiadominial.com.br"
    echo "   Usuário: $ADMIN_USERNAME"
    echo "   Senha: [A senha que você definiu]"
}

# Função para importar terras indígenas
import_terras_indigenas() {
    echo "🏞️ Importando terras indígenas da FUNAI..."
    
    # Verifica se já existem terras indígenas importadas
    if python manage.py shell -c "from dominial.models import TerraIndigenaReferencia; print('TIs importadas:', TerraIndigenaReferencia.objects.count())" | grep -q "0"; then
        echo "📥 Importando terras indígenas..."
        python manage.py importar_terras_indigenas --apenas-referencia
        python manage.py criar_tis_da_referencia
        echo "✅ Terras indígenas importadas com sucesso!"
    else
        echo "✅ Terras indígenas já foram importadas anteriormente."
    fi
}

# Função para criar tipos de documento e lançamento
create_default_types() {
    echo "📋 Criando tipos padrão de documento e lançamento..."
    
    # Verifica se já existem tipos criados
    if python manage.py shell -c "from dominial.models import DocumentoTipo; print('Tipos de documento:', DocumentoTipo.objects.count())" | grep -q "0"; then
        echo "📄 Criando tipos de documento..."
        python manage.py criar_tipos_documento
        echo "✅ Tipos de documento criados!"
    else
        echo "✅ Tipos de documento já existem."
    fi
    
    # Verifica se já existem tipos de lançamento
    if python manage.py shell -c "from dominial.models import LancamentoTipo; print('Tipos de lançamento:', LancamentoTipo.objects.count())" | grep -q "0"; then
        echo "📝 Criando tipos de lançamento..."
        python manage.py criar_tipos_lancamento
        echo "✅ Tipos de lançamento criados!"
    else
        echo "✅ Tipos de lançamento já existem."
    fi
    
    # Verifica se já existem tipos de documento-lançamento
    if python manage.py shell -c "from dominial.models import DocumentoTipo, LancamentoTipo; print('Tipos documento:', DocumentoTipo.objects.count(), 'Tipos lançamento:', LancamentoTipo.objects.count())" | grep -q "0"; then
        echo "🔗 Criando tipos de documento-lançamento..."
        python manage.py criar_tipos_documento_lancamento
        echo "✅ Tipos de documento-lançamento criados!"
    else
        echo "✅ Tipos de documento-lançamento já existem."
    fi
}

# Função para executar migrações
run_migrations() {
    echo "🔄 Executando migrações..."
    python manage.py migrate
    echo "✅ Migrações concluídas!"
}

# Função para coletar arquivos estáticos
collect_static() {
    echo "📦 Verificando arquivos estáticos..."
    # Os arquivos estáticos já foram coletados durante o build
    # Apenas verifica se o diretório existe
    if [ -d "/app/staticfiles" ]; then
        echo "✅ Arquivos estáticos já coletados durante o build."
    else
        echo "⚠️ Diretório staticfiles não encontrado, coletando..."
        python manage.py collectstatic --noinput
        echo "✅ Arquivos estáticos coletados!"
    fi
}

# Função principal
main() {
    echo "=========================================="
    echo "   CADEIA DOMINIAL - SETUP AUTOMÁTICO"
    echo "=========================================="
    
    # Executa as funções na ordem correta
    run_migrations
    create_default_types
    create_default_user
    import_terras_indigenas
    collect_static
    
    echo ""
    echo "🎉 Setup concluído com sucesso!"
    echo ""
    echo "📋 RESUMO:"
    echo "   ✅ Migrações executadas"
    echo "   ✅ Tipos padrão criados"
    echo "   ✅ Usuário admin criado"
    echo "   ✅ Terras indígenas importadas"
    echo "   ✅ Arquivos estáticos coletados"
    echo ""
    echo "🔑 ACESSO AO SISTEMA:"
    echo "   URL: https://cadeiadominial.com.br"
    echo "   Usuário: admin"
    echo "   Senha: admin123"
    echo ""
    echo "⚠️  IMPORTANTE: Altere a senha do usuário admin após o primeiro login!"
    echo "=========================================="
    
    echo ""
    echo "🚀 Iniciando servidor Gunicorn..."
    echo "=========================================="
    
    # Inicia o Gunicorn
    exec gunicorn --bind 0.0.0.0:8000 --workers 3 cadeia_dominial.wsgi:application
}

# Executa a função principal
main "$@" 