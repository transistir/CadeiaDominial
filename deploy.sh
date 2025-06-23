#!/bin/bash

# Script de Deploy para Cadeia Dominial
echo "🚀 Iniciando deploy da Cadeia Dominial..."

# Verificar se há mudanças não commitadas
if [[ -n $(git status --porcelain) ]]; then
    echo "❌ Há mudanças não commitadas. Faça commit antes de continuar."
    git status
    exit 1
fi

# Atualizar dependências
echo "📦 Atualizando dependências..."
pip install -r requirements.txt

# Coletar arquivos estáticos
echo "📁 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# Fazer commit das mudanças
echo "💾 Fazendo commit das mudanças..."
git add .
git commit -m "feat: preparar para deploy - $(date)"

# Push para o repositório
echo "📤 Enviando para o repositório..."
git push origin develop

echo "✅ Deploy iniciado! Verifique o Railway/Render para acompanhar o progresso."
echo "🔗 URL: https://seu-app.railway.app (ou similar)" 