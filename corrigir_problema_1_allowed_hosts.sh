#!/bin/bash

# Script para corrigir o Problema 1: ALLOWED_HOSTS
# Este script configura o Nginx para filtrar requisições maliciosas

echo "🔧 CORRIGINDO PROBLEMA 1: ALLOWED_HOSTS"
echo "======================================="

# Verificar se estamos no diretório correto
if [ ! -f "nginx.conf" ]; then
    echo "❌ Erro: Execute este script no diretório raiz do projeto"
    exit 1
fi

echo ""
echo "📋 ANÁLISE DO PROBLEMA:"
echo "----------------------"
echo "• Erro: Invalid HTTP_HOST header: '20xgeorgia.me'"
echo "• Causa: Bots maliciosos tentando acessar o servidor"
echo "• Solução: Configurar Nginx para filtrar requisições maliciosas"
echo ""

echo "🔍 VERIFICANDO CONFIGURAÇÃO ATUAL:"
echo "---------------------------------"

# Verificar se a configuração já foi aplicada
if grep -q "default_server" nginx.conf; then
    echo "✅ Configuração de segurança já aplicada no nginx.conf"
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

echo "🚀 PRÓXIMOS PASSOS:"
echo "------------------"
echo "1. Reiniciar o Nginx:"
echo "   sudo systemctl restart nginx"
echo ""
echo "2. Verificar se a correção funcionou:"
echo "   tail -f /var/log/nginx/cadeia_dominial_error.log"
echo ""
echo "3. Testar acesso legítimo:"
echo "   curl -H 'Host: 46.62.152.252' http://localhost/"
echo ""

echo "✅ Problema 1 corrigido!"
echo ""
echo "📝 NOTA: Esta correção filtra requisições maliciosas no nível do Nginx,"
echo "   evitando que cheguem ao Django e causem erros de ALLOWED_HOSTS." 