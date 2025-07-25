#!/usr/bin/env python3
"""
Script para investigar documentos duplicados no banco de dados
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings_prod')
django.setup()

from dominial.models import Documento
from django.db.models import Count

def investigar_duplicatas():
    """Investiga documentos duplicados no banco"""
    print("🔍 INVESTIGANDO DOCUMENTOS DUPLICADOS")
    print("=" * 50)
    
    # Buscar documentos com mesmo número e cartório
    duplicatas = Documento.objects.values('numero', 'cartorio').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count', 'numero')
    
    if not duplicatas.exists():
        print("✅ Nenhum documento duplicado encontrado!")
        return
    
    print(f"⚠️ Encontrados {duplicatas.count()} grupos de documentos duplicados:")
    print()
    
    for duplicata in duplicatas:
        numero = duplicata['numero']
        cartorio_id = duplicata['cartorio']
        count = duplicata['count']
        
        print(f"📄 Número: '{numero}' | Cartório ID: {cartorio_id} | Total: {count}")
        
        # Buscar todos os documentos com este número e cartório
        docs = Documento.objects.filter(
            numero=numero, 
            cartorio_id=cartorio_id
        ).select_related('cartorio', 'imovel', 'tipo').order_by('id')
        
        for i, doc in enumerate(docs, 1):
            print(f"   {i}. ID: {doc.id} | Data: {doc.data} | Tipo: {doc.tipo.tipo}")
            print(f"      Cartório: {doc.cartorio.nome}")
            print(f"      Imóvel: {doc.imovel.matricula} ({doc.imovel.nome})")
            print(f"      Livro: {doc.livro} | Folha: {doc.folha}")
            print()
        
        print("-" * 50)
    
    # Verificar especificamente o M794
    print("\n🔍 VERIFICANDO DOCUMENTO M794:")
    print("-" * 30)
    
    docs_m794 = Documento.objects.filter(numero='M794').select_related(
        'cartorio', 'imovel', 'tipo'
    ).order_by('id')
    
    if docs_m794.exists():
        print(f"📄 Encontrados {docs_m794.count()} documentos com número M794:")
        for i, doc in enumerate(docs_m794, 1):
            print(f"   {i}. ID: {doc.id} | Data: {doc.data} | Tipo: {doc.tipo.tipo}")
            print(f"      Cartório: {doc.cartorio.nome}")
            print(f"      Imóvel: {doc.imovel.matricula} ({doc.imovel.nome})")
            print(f"      Livro: {doc.livro} | Folha: {doc.folha}")
            print()
    else:
        print("❌ Nenhum documento M794 encontrado")

def verificar_constraints():
    """Verifica se as constraints estão funcionando"""
    print("\n🔍 VERIFICANDO CONSTRAINTS:")
    print("-" * 30)
    
    # Verificar constraint unique_together
    print("📋 Constraint unique_together: ('numero', 'cartorio')")
    
    # Buscar violações da constraint
    violacoes = Documento.objects.values('numero', 'cartorio').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    if violacoes.exists():
        print(f"⚠️ {violacoes.count()} violações da constraint encontradas")
        for violacao in violacoes:
            print(f"   - Número: '{violacao['numero']}' | Cartório: {violacao['cartorio']} | Count: {violacao['count']}")
    else:
        print("✅ Nenhuma violação da constraint encontrada")

def main():
    """Função principal"""
    try:
        investigar_duplicatas()
        verificar_constraints()
        
        print("\n" + "=" * 50)
        print("✅ Investigação concluída!")
        print("\n📋 Próximos passos:")
        print("1. Analisar os documentos duplicados encontrados")
        print("2. Decidir qual documento manter")
        print("3. Remover documentos duplicados")
        
    except Exception as e:
        print(f"❌ Erro durante a investigação: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 