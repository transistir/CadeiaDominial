#!/bin/bash
# Comando final para commit - SEM arquivos testar_*

echo "📦 Adicionando arquivos para commit..."

git add dominial/models/imovel_models.py
git add dominial/forms/imovel_forms.py
git add dominial/migrations/0042_fix_matricula_unique_constraint.py
git add dominial/views/imovel_views.py
git add templates/dominial/imovel_form.html
git add dominial/management/commands/verificar_matricula_constraint.py
git add docs/ANALISE_MIGRACAO_MATRICULA.md
git add CHECKLIST_PRODUCAO_MATRICULA.md
git add COMMIT_CHECKLIST.md
git add PRONTO_PARA_PRODUCAO.md
git add RESUMO_FINAL_DEPLOY.md
git add docker-compose.dev.yml
git add scripts/create_admin_user.py
git add scripts/create_admin_user.sh
git add scripts/dev.sh

echo "✅ Arquivos adicionados!"
echo ""
echo "📝 Mensagem de commit sugerida:"
echo ""
echo "fix: Corrige constraint de matrícula para ser única por cartório"
echo ""
echo "BREAKING CHANGE: Matrícula agora é única por cartório, não globalmente."
echo ""
echo "- Remove unique=True do campo matricula no modelo Imovel"
echo "- Adiciona UniqueConstraint (matricula, cartorio)"
echo "- Adiciona validação customizada no ImovelForm com mensagens claras"
echo "- Adiciona migração 0042 com verificação automática de duplicatas"
echo "- Adiciona comando verificar_matricula_constraint para validação pré-migração"
echo "- Melhora exibição de erros no formulário de imóvel"
echo "- Corrige erro de indentação no docker-compose.dev.yml"
echo "- Adiciona scripts para criar usuário admin em desenvolvimento"
echo ""
echo "Fixes: Erro 'Imóvel with this Matricula already exists' ao cadastrar"
echo "imóvel com matrícula existente em outro cartório."
echo ""
echo "Documentação completa incluída."
echo ""
echo "🚀 Execute: git commit -m \"[mensagem acima]\""
echo "🚀 Depois: git push origin main"

