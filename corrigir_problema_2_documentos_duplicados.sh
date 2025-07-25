#!/bin/bash

# Script para corrigir o Problema 2: Documentos Duplicados
# Este script investiga e corrige documentos duplicados no banco

echo "🔧 CORRIGINDO PROBLEMA 2: DOCUMENTOS DUPLICADOS"
echo "=============================================="

# Verificar se estamos no diretório correto
if [ ! -f "manage.py" ]; then
    echo "❌ Erro: Execute este script no diretório raiz do projeto"
    exit 1
fi

echo ""
echo "📋 ANÁLISE DO PROBLEMA:"
echo "----------------------"
echo "• Erro: get() returned more than one Documento -- it returned 2!"
echo "• Causa: Documentos duplicados no banco de dados"
echo "• Solução: Investigar e remover documentos duplicados"
echo ""

echo "🔍 INVESTIGANDO DOCUMENTOS DUPLICADOS..."
echo "--------------------------------------"

# Executar investigação
echo "Executando investigação de documentos duplicados..."
python manage.py investigar_documentos_duplicados

echo ""
echo "🔍 INVESTIGANDO DOCUMENTO M794 ESPECÍFICO..."
echo "------------------------------------------"

# Investigar especificamente o M794
echo "Executando investigação do documento M794..."
python manage.py investigar_documentos_duplicados --numero M794

echo ""
echo "❓ DESEJAS CORRIGIR OS DOCUMENTOS DUPLICADOS?"
echo "-------------------------------------------"
echo "1. 🔍 Apenas investigar (não corrigir)"
echo "2. 🛠️ Corrigir automaticamente (manter o mais antigo)"
echo "3. 🛠️ Corrigir apenas M794"
echo ""

echo "❓ Qual opção você prefere? (1, 2 ou 3)"
read -r opcao

case $opcao in
    1)
        echo ""
        echo "✅ Apenas investigação realizada!"
        echo "📋 Resultados mostrados acima."
        ;;
    2)
        echo ""
        echo "🛠️ CORRIGINDO TODOS OS DOCUMENTOS DUPLICADOS..."
        echo "---------------------------------------------"
        python manage.py investigar_documentos_duplicados --corrigir
        ;;
    3)
        echo ""
        echo "🛠️ CORRIGINDO APENAS DOCUMENTO M794..."
        echo "------------------------------------"
        python manage.py investigar_documentos_duplicados --numero M794 --corrigir
        ;;
    *)
        echo "❌ Opção inválida"
        exit 1
        ;;
esac

echo ""
echo "🔍 VERIFICANDO SE A CORREÇÃO FUNCIONOU..."
echo "---------------------------------------"

# Verificar se ainda há duplicatas
echo "Verificando se ainda há documentos duplicados..."
python manage.py investigar_documentos_duplicados

echo ""
echo "🚀 PRÓXIMOS PASSOS:"
echo "------------------"
echo "1. Testar funcionalidades da aplicação"
echo "2. Verificar se o erro M794 foi resolvido"
echo "3. Monitorar logs para confirmar que não há mais erros"
echo ""

echo "✅ Problema 2 investigado/corrigido!"
echo ""
echo "📝 NOTA: Se documentos foram removidos, verifique se não há"
echo "   lançamentos ou outras referências que possam ter sido afetadas." 