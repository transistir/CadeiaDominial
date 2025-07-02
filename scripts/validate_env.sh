#!/bin/bash

# Script de validação de variáveis de ambiente
# Verifica se todas as variáveis obrigatórias estão definidas

set -e

echo "🔍 Validando variáveis de ambiente..."

# Função para verificar se variável está definida
check_var() {
    local var_name=$1
    local var_value=${!var_name}
    
    if [ -z "$var_value" ]; then
        echo "❌ ERRO: Variável $var_name não está definida!"
        return 1
    else
        echo "✅ $var_name: [DEFINIDA]"
        return 0
    fi
}

# Função para validar senha
validate_password() {
    local password=$1
    local min_length=8
    
    if [ ${#password} -lt $min_length ]; then
        echo "❌ ERRO: ADMIN_PASSWORD deve ter pelo menos $min_length caracteres!"
        echo "   Senha atual: ${#password} caracteres"
        return 1
    fi
    
    # Verificar se contém pelo menos um número
    if ! echo "$password" | grep -q '[0-9]'; then
        echo "⚠️  AVISO: ADMIN_PASSWORD deve conter pelo menos um número"
    fi
    
    # Verificar se contém pelo menos uma letra maiúscula
    if ! echo "$password" | grep -q '[A-Z]'; then
        echo "⚠️  AVISO: ADMIN_PASSWORD deve conter pelo menos uma letra maiúscula"
    fi
    
    echo "✅ ADMIN_PASSWORD: [VÁLIDA - ${#password} caracteres]"
    return 0
}

# Variáveis obrigatórias
required_vars=(
    "ADMIN_PASSWORD"
    "SECRET_KEY"
    "DB_PASSWORD"
)

# Verificar variáveis obrigatórias
errors=0
for var in "${required_vars[@]}"; do
    if ! check_var "$var"; then
        errors=$((errors + 1))
    fi
done

# Validar senha especificamente
if ! validate_password "$ADMIN_PASSWORD"; then
    errors=$((errors + 1))
fi

# Verificar variáveis opcionais
optional_vars=(
    "ADMIN_USERNAME"
    "ADMIN_EMAIL"
    "DOMAIN_NAME"
    "CERTBOT_EMAIL"
)

echo ""
echo "📋 Variáveis opcionais:"
for var in "${optional_vars[@]}"; do
    if check_var "$var" > /dev/null 2>&1; then
        echo "✅ $var: [DEFINIDA]"
    else
        echo "⚪ $var: [NÃO DEFINIDA - usando padrão]"
    fi
done

echo ""
if [ $errors -eq 0 ]; then
    echo "🎉 Todas as validações passaram!"
    echo "✅ O sistema está pronto para deploy"
    exit 0
else
    echo "❌ Encontrados $errors erro(s) de validação"
    echo ""
    echo "🔧 Como corrigir:"
    echo "1. Edite o arquivo .env: nano .env"
    echo "2. Defina as variáveis obrigatórias:"
    echo "   ADMIN_PASSWORD=sua_senha_muito_segura_aqui"
    echo "   SECRET_KEY=sua_chave_secreta_aqui"
    echo "   DB_PASSWORD=sua_senha_banco_aqui"
    echo "3. Execute novamente: ./scripts/validate_env.sh"
    exit 1
fi 