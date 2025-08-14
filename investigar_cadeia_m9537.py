#!/usr/bin/env python3
"""
Script para investigar a cadeia dominial do imóvel M9537
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
django.setup()

from dominial.models import Documento, Lancamento, Imovel, DocumentoImportado
from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService

def investigar_cadeia_m9537():
    """Investiga a cadeia dominial do imóvel M9537"""
    
    print("🔍 INVESTIGANDO CADEIA DOMINIAL DO IMÓVEL M9537")
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
    
    # 4. Simular construção da cadeia dominial
    print("\n4. SIMULANDO CONSTRUÇÃO DA CADEIA DOMINIAL")
    print("-" * 40)
    
    service = CadeiaDominialTabelaService()
    
    try:
        # Simular chamada do service
        print("Chamando CadeiaDominialTabelaService.get_cadeia_dominial_tabela...")
        
        # Precisamos do TIs ID - vamos buscar
        tis = m9537.terra_indigena
        print(f"TIs ID: {tis.id}")
        
        resultado = service.get_cadeia_dominial_tabela(tis.id, m9537.id, {})
        
        print(f"✅ Cadeia construída com sucesso!")
        print(f"Total de documentos na cadeia: {len(resultado['cadeia'])}")
        
        # Listar documentos da cadeia
        print("\nDocumentos na cadeia:")
        for i, item in enumerate(resultado['cadeia'], 1):
            doc = item['documento']
            is_importado = item['is_importado']
            print(f"   {i}. {doc.numero} ({doc.tipo.tipo}) - Imóvel: {doc.imovel.matricula}")
            if is_importado:
                print(f"      📥 IMPORTADO")
            
            # Verificar origens disponíveis
            if item['origens_disponiveis']:
                origens = [o['numero'] for o in item['origens_disponiveis']]
                print(f"      Origens: {origens}")
        
        # Verificar se T220 e T221 estão na cadeia
        print("\n5. VERIFICANDO SE T220 E T221 ESTÃO NA CADEIA")
        print("-" * 40)
        
        t220_encontrado = False
        t221_encontrado = False
        
        for item in resultado['cadeia']:
            doc = item['documento']
            if doc.numero == 'T220':
                t220_encontrado = True
                print(f"✅ T220 encontrado na posição {resultado['cadeia'].index(item) + 1}")
                print(f"   Imóvel: {doc.imovel.matricula}")
                print(f"   Importado: {item['is_importado']}")
            
            if doc.numero == 'T221':
                t221_encontrado = True
                print(f"✅ T221 encontrado na posição {resultado['cadeia'].index(item) + 1}")
                print(f"   Imóvel: {doc.imovel.matricula}")
                print(f"   Importado: {item['is_importado']}")
        
        if not t220_encontrado:
            print("❌ T220 NÃO encontrado na cadeia")
        
        if not t221_encontrado:
            print("❌ T221 NÃO encontrado na cadeia")
        
        # 6. Verificar expansão de documentos importados
        print("\n6. VERIFICANDO EXPANSÃO DE DOCUMENTOS IMPORTADOS")
        print("-" * 40)
        
        for item in resultado['cadeia']:
            doc = item['documento']
            if item['is_importado']:
                print(f"Documento importado: {doc.numero}")
                
                # Verificar se tem origens
                lancamentos = doc.lancamentos.filter(
                    origem__isnull=False
                ).exclude(origem='')
                
                if lancamentos.exists():
                    print(f"   Lançamentos com origem:")
                    for lanc in lancamentos:
                        print(f"     - {lanc.numero_lancamento}: '{lanc.origem}'")
                        
                        if lanc.origem:
                            origens = [o.strip() for o in lanc.origem.split(';') if o.strip()]
                            print(f"       Origens separadas: {origens}")
                            
                            for origem_numero in origens:
                                doc_origem = Documento.objects.filter(numero=origem_numero).first()
                                if doc_origem:
                                    print(f"         ✅ {origem_numero} encontrado: {doc_origem.imovel.matricula}")
                                else:
                                    print(f"         ❌ {origem_numero} NÃO encontrado")
                else:
                    print(f"   Nenhum lançamento com origem")
        
    except Exception as e:
        print(f"❌ Erro ao construir cadeia dominial: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == '__main__':
    investigar_cadeia_m9537()
