#!/usr/bin/env python3
"""
Script para investigar a árvore da cadeia dominial
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
django.setup()

from dominial.models import Documento, Lancamento, Imovel, DocumentoImportado
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService

def investigar_arvore_cadeia():
    """Investiga a árvore da cadeia dominial"""
    
    print("🔍 INVESTIGANDO ÁRVORE DA CADEIA DOMINIAL")
    print("=" * 60)
    
    # 1. Verificar imóvel M9537
    print("\n1. VERIFICANDO IMÓVEL M9537")
    print("-" * 40)
    
    m9537 = Imovel.objects.filter(matricula='M9537').first()
    if not m9537:
        print("❌ Imóvel M9537 não encontrado")
        return
    
    print(f"✅ M9537 encontrado (ID: {m9537.id})")
    print(f"   Nome: {m9537.nome}")
    
    # 2. Verificar documentos do M9537
    print("\n2. DOCUMENTOS DO IMÓVEL M9537")
    print("-" * 40)
    
    documentos_m9537 = m9537.documentos.all()
    print(f"Total de documentos: {documentos_m9537.count()}")
    
    for doc in documentos_m9537:
        print(f"   Documento: {doc.numero} (ID: {doc.id}) - {doc.tipo.tipo}")
        
        # Verificar lançamentos com origens
        lancamentos_com_origem = doc.lancamentos.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        if lancamentos_com_origem.exists():
            print(f"     Lançamentos com origem:")
            for lanc in lancamentos_com_origem:
                print(f"       - {lanc.numero_lancamento}: '{lanc.origem}'")
    
    # 3. Verificar documentos importados para M9537
    print("\n3. DOCUMENTOS IMPORTADOS PARA M9537")
    print("-" * 40)
    
    importacoes_m9537 = DocumentoImportado.objects.filter(
        documento__imovel=m9537
    ).select_related('documento', 'imovel_origem')
    
    print(f"Total de importações: {importacoes_m9537.count()}")
    
    for imp in importacoes_m9537:
        print(f"   Documento {imp.documento.numero} importado de {imp.imovel_origem.matricula}")
        print(f"     Data: {imp.data_importacao}")
        print(f"     Por: {imp.importado_por.username if imp.importado_por else 'Sistema'}")
    
    # 4. Simular busca de documentos importados
    print("\n4. SIMULANDO BUSCA DE DOCUMENTOS IMPORTADOS")
    print("-" * 40)
    
    try:
        documentos_importados = HierarquiaArvoreService._buscar_documentos_importados(m9537)
        print(f"✅ Documentos importados encontrados: {len(documentos_importados)}")
        
        for i, doc in enumerate(documentos_importados, 1):
            print(f"   {i}. {doc.numero} ({doc.tipo.tipo}) - Imóvel: {doc.imovel.matricula}")
            print(f"      Cartório: {doc.cartorio.nome if doc.cartorio else 'N/A'}")
            
            # Verificar se tem lançamentos com origens
            lancamentos = doc.lancamentos.filter(
                origem__isnull=False
            ).exclude(origem='')
            
            if lancamentos.exists():
                print(f"      Lançamentos com origem:")
                for lanc in lancamentos:
                    print(f"        - {lanc.numero_lancamento}: '{lanc.origem}'")
        
    except Exception as e:
        print(f"❌ Erro ao buscar documentos importados: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
    
    # 5. Simular construção da árvore
    print("\n5. SIMULANDO CONSTRUÇÃO DA ÁRVORE")
    print("-" * 40)
    
    try:
        print("Chamando HierarquiaArvoreService.construir_arvore_cadeia_dominial...")
        
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(m9537)
        
        print(f"✅ Árvore construída com sucesso!")
        print(f"Total de documentos na árvore: {len(arvore['documentos'])}")
        
        # Listar documentos da árvore
        print("\nDocumentos na árvore:")
        for i, doc_node in enumerate(arvore['documentos'], 1):
            numero = doc_node['numero']
            tipo = doc_node['tipo']
            is_importado = doc_node.get('is_importado', False)
            print(f"   {i}. {numero} ({tipo})")
            if is_importado:
                print(f"      📥 IMPORTADO")
            
            # Verificar conexões
            if doc_node.get('conexoes'):
                print(f"      Conexões: {[c['destino'] for c in doc_node['conexoes']]}")
        
        # Verificar se T220 e T221 estão na árvore
        print("\n6. VERIFICANDO SE T220 E T221 ESTÃO NA ÁRVORE")
        print("-" * 40)
        
        t220_encontrado = False
        t221_encontrado = False
        
        for doc_node in arvore['documentos']:
            numero = doc_node['numero']
            if numero == 'T220':
                t220_encontrado = True
                print(f"✅ T220 encontrado na posição {arvore['documentos'].index(doc_node) + 1}")
                print(f"   Importado: {doc_node.get('is_importado', False)}")
            
            if numero == 'T221':
                t221_encontrado = True
                print(f"✅ T221 encontrado na posição {arvore['documentos'].index(doc_node) + 1}")
                print(f"   Importado: {doc_node.get('is_importado', False)}")
        
        if not t220_encontrado:
            print("❌ T220 NÃO encontrado na árvore")
        
        if not t221_encontrado:
            print("❌ T221 NÃO encontrado na árvore")
        
        # 7. Verificar conexões da árvore
        print("\n7. VERIFICANDO CONEXÕES DA ÁRVORE")
        print("-" * 40)
        
        print(f"Total de conexões: {len(arvore['conexoes'])}")
        for i, conexao in enumerate(arvore['conexoes'], 1):
            print(f"   {i}. {conexao['origem']} → {conexao['destino']}")
        
    except Exception as e:
        print(f"❌ Erro ao construir árvore: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
    
    # 8. Verificar se M197 está sendo referenciado
    print("\n8. VERIFICANDO REFERÊNCIAS AO M197")
    print("-" * 40)
    
    # Buscar lançamentos que referenciam M197
    lancamentos_m197 = Lancamento.objects.filter(origem__icontains='M197')
    print(f"Lançamentos que referenciam M197: {lancamentos_m197.count()}")
    
    for lanc in lancamentos_m197:
        print(f"   Lançamento {lanc.id} (Doc {lanc.documento.numero}): '{lanc.origem}'")
        print(f"     Imóvel: {lanc.documento.imovel.matricula}")

if __name__ == '__main__':
    investigar_arvore_cadeia()
