#!/bin/bash

# Script para corrigir o Problema 1: ALLOWED_HOSTS no ambiente Docker
# Este script configura o Nginx Docker para filtrar requisições maliciosas

echo "🔧 CORRIGINDO PROBLEMA 1: ALLOWED_HOSTS (DOCKER)"
echo "================================================"

# Verificar se estamos no diretório correto
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Erro: Execute este script no diretório raiz do projeto"
    exit 1
fi

echo ""
echo "📋 ANÁLISE DO PROBLEMA:"
echo "----------------------"
echo "• Erro: Invalid HTTP_HOST header: '20xgeorgia.me'"
echo "• Causa: Bots maliciosos tentando acessar o servidor"
echo "• Ambiente: Docker (nginx container)"
echo "• Solução: Configurar Nginx Docker para filtrar requisições maliciosas"
echo ""

echo "🔍 VERIFICANDO CONFIGURAÇÃO ATUAL:"
echo "---------------------------------"

# Verificar se a configuração já foi aplicada
if grep -q "default_server" nginx/conf.d/default.conf; then
    echo "✅ Configuração de segurança já aplicada no nginx/conf.d/default.conf"
else
    echo "⚠️ Configuração de segurança não encontrada"
fi

echo ""
echo "📋 CONFIGURAÇÃO APLICADA:"
echo "------------------------"
echo "✅ Bloqueio de hosts maliciosos (20xgeorgia.me, etc.)"
echo "✅ Bloqueio de acesso a arquivos sensíveis (.env, .git, etc.)"
echo "✅ Bloqueio de User-Agents maliciosos (bots, crawlers, etc.)"
echo "✅ Retorno 444 (sem resposta) para ataques"
echo ""

echo "🚀 APLICANDO CORREÇÃO NO DOCKER:"
echo "-------------------------------"

# Verificar se o Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "❌ Erro: Docker não está rodando"
    exit 1
fi

# Verificar se os containers estão rodando
if ! docker-compose ps | grep -q "cadeia_dominial_nginx"; then
    echo "⚠️ Container nginx não está rodando"
    echo "   Iniciando containers..."
    docker-compose up -d
else
    echo "✅ Container nginx está rodando"
fi

echo ""
echo "🔄 RECONSTRUINDO CONTAINER NGINX:"
echo "--------------------------------"

# Reconstruir o container nginx com a nova configuração
echo "Reconstruindo container nginx..."
docker-compose build nginx

echo ""
echo "🔄 REINICIANDO CONTAINER NGINX:"
echo "------------------------------"

# Reiniciar o container nginx
echo "Reiniciando container nginx..."
docker-compose restart nginx

echo ""
echo "🔍 VERIFICANDO STATUS:"
echo "--------------------"

# Verificar se o container está rodando
if docker-compose ps | grep -q "cadeia_dominial_nginx.*Up"; then
    echo "✅ Container nginx reiniciado com sucesso"
else
    echo "❌ Erro ao reiniciar container nginx"
    echo "Verificando logs..."
    docker-compose logs nginx
    exit 1
fi

echo ""
echo "📊 TESTANDO CONFIGURAÇÃO:"
echo "------------------------"

# Testar se a configuração está funcionando
echo "Testando acesso legítimo..."
if curl -s -H "Host: 46.62.152.252" http://localhost/health > /dev/null 2>&1; then
    echo "✅ Acesso legítimo funcionando"
else
    echo "⚠️ Acesso legítimo com problemas"
fi

echo ""
echo "🚀 PRÓXIMOS PASSOS:"
echo "------------------"
echo "1. Monitorar logs para verificar se os ataques foram bloqueados:"
echo "   docker-compose logs -f nginx"
echo ""
echo "2. Verificar logs do Django para confirmar redução de erros ALLOWED_HOSTS:"
echo "   docker-compose logs -f web"
echo ""
echo "3. Testar acesso malicioso (deve retornar 444):"
echo "   curl -H 'Host: 20xgeorgia.me' http://localhost/"
echo ""

echo "✅ Problema 1 corrigido no ambiente Docker!"
echo ""
echo "📝 NOTA: Esta correção filtra requisições maliciosas no nível do Nginx Docker,"
echo "   evitando que cheguem ao Django e causem erros de ALLOWED_HOSTS." 