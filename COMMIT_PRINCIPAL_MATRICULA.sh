#!/bin/bash
# Commit PRINCIPAL: Correção da constraint de matrícula
# Apenas arquivos relacionados à mudança de constraint

echo "📦 Commit PRINCIPAL: Correção da constraint de matrícula"
echo "=================================================="
echo ""

# Adicionar APENAS arquivos relacionados à correção da constraint
# ✅ MIGRATION DEVE ser commitada - é essencial para deploy em produção
git add dominial/models/imovel_models.py
git add dominial/forms/imovel_forms.py
git add dominial/migrations/0042_fix_matricula_unique_constraint.py  # ✅ ESSENCIAL
git add dominial/views/imovel_views.py
git add templates/dominial/imovel_form.html
git add dominial/management/commands/verificar_matricula_constraint.py
git add docs/ANALISE_MIGRACAO_MATRICULA.md
git add CHECKLIST_PRODUCAO_MATRICULA.md

echo "✅ Arquivos adicionados para commit principal"
echo ""
echo "📝 Mensagem de commit está em: .commit_msg_matricula.txt"
echo ""
echo "🚀 Executando commit..."
git commit -F .commit_msg_matricula.txt
echo ""
echo "✅ Commit realizado com sucesso!"
echo ""
echo "📋 Para ver o commit: git log -1"
echo "📋 Para fazer push: git push origin main"
echo ""

