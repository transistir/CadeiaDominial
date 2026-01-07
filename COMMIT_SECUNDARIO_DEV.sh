#!/bin/bash
# Commit SECUNDÁRIO: Correções de desenvolvimento
# Arquivos relacionados a melhorias no ambiente de desenvolvimento

echo "📦 Commit SECUNDÁRIO: Correções de desenvolvimento"
echo "=================================================="
echo ""

# Verificar se há mudanças nos arquivos de dev
if git diff --quiet docker-compose.dev.yml scripts/dev.sh scripts/create_admin_user.py scripts/create_admin_user.sh; then
    echo "ℹ️  Nenhuma mudança nos arquivos de desenvolvimento"
    echo "   Este commit não é necessário"
    exit 0
fi

# Adicionar arquivos de desenvolvimento
git add docker-compose.dev.yml
git add scripts/dev.sh
git add scripts/create_admin_user.py
git add scripts/create_admin_user.sh

echo "✅ Arquivos adicionados para commit secundário"
echo ""
echo "📝 Mensagem de commit sugerida:"
echo ""
cat << 'EOF'
fix(dev): Corrige erro de indentação e melhora criação de usuário admin

- Corrige erro de indentação no docker-compose.dev.yml
- Adiciona script create_admin_user.sh para criar usuário admin em dev
- Adiciona script create_admin_user.py como alternativa
- Melhora mensagens no script dev.sh
EOF
echo ""
echo "🚀 Execute: git commit -m \"fix(dev): Corrige erro de indentação e melhora criação de usuário admin\""
echo ""

