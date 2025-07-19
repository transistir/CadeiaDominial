#!/bin/bash

# Script para corrigir problemas identificados no servidor de produção
# 1. Pessoas duplicadas que causam erro MultipleObjectsReturned
# 2. Problemas de CSRF que impedem login/logout

echo "🔧 CORRIGINDO PROBLEMAS DE PRODUÇÃO"
echo "=================================="

# Verificar se estamos no diretório correto
if [ ! -f "manage.py" ]; then
    echo "❌ Erro: Execute este script no diretório raiz do projeto"
    exit 1
fi

echo ""
echo "📋 1. INVESTIGANDO PESSOAS DUPLICADAS"
echo "------------------------------------"

# Executar investigação de pessoas duplicadas
echo "Executando investigação de pessoas duplicadas..."
python manage.py investigar_pessoas_duplicadas --dry-run

echo ""
echo "❓ Deseja executar a correção automática das pessoas duplicadas? (s/n)"
read -r resposta

if [[ $resposta =~ ^[Ss]$ ]]; then
    echo ""
    echo "🛠️ EXECUTANDO CORREÇÃO DE PESSOAS DUPLICADAS"
    echo "---------------------------------------------"
    python manage.py investigar_pessoas_duplicadas --corrigir
else
    echo "⚠️ Correção de pessoas duplicadas pulada."
fi

echo ""
echo "📋 2. VERIFICANDO CONFIGURAÇÕES DE CSRF"
echo "---------------------------------------"

# Verificar se as configurações de CSRF estão corretas
echo "Verificando configurações de CSRF..."

# Verificar se o domínio leiadominial.com.br está nas configurações
if grep -q "leiadominial.com.br" cadeia_dominial/settings_prod.py; then
    echo "✅ Domínio leiadominial.com.br encontrado nas configurações CSRF"
else
    echo "❌ Domínio leiadominial.com.br NÃO encontrado nas configurações CSRF"
    echo "   Adicione manualmente nas configurações de CSRF_TRUSTED_ORIGINS"
fi

echo ""
echo "📋 3. VERIFICANDO CONFIGURAÇÕES DE SESSÃO"
echo "----------------------------------------"

# Verificar configurações de sessão
echo "Verificando configurações de sessão..."

if grep -q "CSRF_USE_SESSIONS = True" cadeia_dominial/settings_prod.py; then
    echo "✅ CSRF_USE_SESSIONS está configurado corretamente"
else
    echo "❌ CSRF_USE_SESSIONS não está configurado"
fi

if grep -q "CSRF_COOKIE_SAMESITE = 'Lax'" cadeia_dominial/settings_prod.py; then
    echo "✅ CSRF_COOKIE_SAMESITE está configurado corretamente"
else
    echo "❌ CSRF_COOKIE_SAMESITE não está configurado"
fi

echo ""
echo "📋 4. VERIFICANDO LOGS DE ERRO"
echo "------------------------------"

# Verificar se há erros recentes nos logs
echo "Verificando logs de erro recentes..."
if command -v docker-compose &> /dev/null; then
    echo "Últimos logs do container web:"
    docker-compose logs --tail=20 cadeia_dominial_web | grep -i error
else
    echo "⚠️ Docker Compose não encontrado. Verifique os logs manualmente."
fi

echo ""
echo "📋 5. TESTANDO CONEXÃO COM BANCO DE DADOS"
echo "----------------------------------------"

# Testar conexão com banco de dados
echo "Testando conexão com banco de dados..."
python manage.py check --database default

echo ""
echo "📋 6. VERIFICANDO MIGRAÇÕES"
echo "---------------------------"

# Verificar se há migrações pendentes
echo "Verificando migrações pendentes..."
python manage.py showmigrations --list

echo ""
echo "📋 7. COLETANDO ARQUIVOS ESTÁTICOS"
echo "----------------------------------"

# Coletar arquivos estáticos
echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo ""
echo "✅ CORREÇÕES CONCLUÍDAS!"
echo "========================"
echo ""
echo "💡 PRÓXIMOS PASSOS:"
echo "1. Reinicie o servidor web: docker-compose restart cadeia_dominial_web"
echo "2. Teste o login/logout no navegador"
echo "3. Teste o cadastro de imóveis"
echo "4. Monitore os logs para verificar se os erros foram resolvidos"
echo ""
echo "🔍 PARA INVESTIGAÇÃO ADICIONAL:"
echo "- Use: python manage.py investigar_pessoas_duplicadas --nome 'Nome Específico'"
echo "- Verifique logs: docker-compose logs -f cadeia_dominial_web"
echo "- Teste CSRF: curl -X POST http://seu-dominio/accounts/login/ -H 'Content-Type: application/x-www-form-urlencoded'" 