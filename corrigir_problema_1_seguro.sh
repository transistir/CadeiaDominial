#!/bin/bash

# Script SEGURO para corrigir o Problema 1: ALLOWED_HOSTS
# Este script aplica a correção sem rebuild do container

echo "🔧 CORRIGINDO PROBLEMA 1: ALLOWED_HOSTS (MÉTODO SEGURO)"
echo "====================================================="

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
echo "• Método: Aplicação segura sem rebuild"
echo ""

echo "🔍 VERIFICANDO STATUS ATUAL:"
echo "---------------------------"

# Verificar se o Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "❌ Erro: Docker não está rodando"
    exit 1
fi

# Verificar se os containers estão rodando
if ! docker-compose ps | grep -q "cadeia_dominial_nginx"; then
    echo "❌ Container nginx não está rodando"
    echo "   Iniciando containers..."
    docker-compose up -d
    sleep 5
fi

echo "✅ Container nginx está rodando"

echo ""
echo "📋 OPÇÕES DE CORREÇÃO:"
echo "--------------------"

echo "1. 🔒 MÉTODO SEGURO (Recomendado):"
echo "   • Copiar arquivo de configuração para dentro do container"
echo "   • Recarregar configuração do Nginx"
echo "   • Sem rebuild, sem downtime"
echo ""

echo "2. ⚠️ MÉTODO COMPLETO:"
echo "   • Rebuild do container nginx"
echo "   • Pode causar downtime"
echo ""

echo "❓ Qual método você prefere? (1 ou 2)"
read -r metodo

if [ "$metodo" = "1" ]; then
    echo ""
    echo "🚀 APLICANDO MÉTODO SEGURO..."
    echo "----------------------------"
    
    # Verificar se o arquivo de configuração existe
    if [ ! -f "nginx/conf.d/default.conf" ]; then
        echo "❌ Arquivo nginx/conf.d/default.conf não encontrado"
        exit 1
    fi
    
    # Fazer backup da configuração atual
    echo "📋 Fazendo backup da configuração atual..."
    docker-compose exec nginx cp /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.backup
    
    # Copiar nova configuração para o container
    echo "📋 Copiando nova configuração..."
    docker cp nginx/conf.d/default.conf cadeia_dominial_nginx:/etc/nginx/conf.d/default.conf
    
    # Testar configuração do Nginx
    echo "🔍 Testando configuração do Nginx..."
    if docker-compose exec nginx nginx -t; then
        echo "✅ Configuração do Nginx válida"
        
        # Recarregar configuração do Nginx
        echo "🔄 Recarregando configuração do Nginx..."
        docker-compose exec nginx nginx -s reload
        
        echo "✅ Configuração aplicada com sucesso!"
    else
        echo "❌ Configuração do Nginx inválida"
        echo "🔄 Restaurando backup..."
        docker-compose exec nginx cp /etc/nginx/conf.d/default.conf.backup /etc/nginx/conf.d/default.conf
        docker-compose exec nginx nginx -s reload
        echo "✅ Backup restaurado"
        exit 1
    fi
    
elif [ "$metodo" = "2" ]; then
    echo ""
    echo "⚠️ APLICANDO MÉTODO COMPLETO..."
    echo "-----------------------------"
    
    echo "🔄 Reconstruindo container nginx..."
    docker-compose build nginx
    
    echo "🔄 Reiniciando container nginx..."
    docker-compose restart nginx
    
    # Verificar se o container está rodando
    sleep 5
    if docker-compose ps | grep -q "cadeia_dominial_nginx.*Up"; then
        echo "✅ Container nginx reiniciado com sucesso"
    else
        echo "❌ Erro ao reiniciar container nginx"
        echo "Verificando logs..."
        docker-compose logs nginx
        exit 1
    fi
    
else
    echo "❌ Opção inválida"
    exit 1
fi

echo ""
echo "🔍 VERIFICANDO STATUS:"
echo "--------------------"

# Verificar se o container está rodando
if docker-compose ps | grep -q "cadeia_dominial_nginx.*Up"; then
    echo "✅ Container nginx funcionando"
else
    echo "❌ Container nginx com problemas"
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

echo "✅ Problema 1 corrigido com método seguro!"
echo ""
echo "📝 NOTA: Se algo der errado, o backup foi salvo em:"
echo "   /etc/nginx/conf.d/default.conf.backup (dentro do container)" 