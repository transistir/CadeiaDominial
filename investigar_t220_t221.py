#!/usr/bin/env python3
"""
Script para investigar os documentos T220 e T221
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
django.setup()

from dominial.models import Documento, Lancamento, Imovel, DocumentoImportado

def investigar_documentos_t220_t221():
    """Investiga os documentos T220 e T221"""
    
    print("🔍 INVESTIGANDO DOCUMENTOS T220 E T221")
    print("=" * 60)
    
    # 1. Verificar se os documentos T220 e T221 existem
    print("\n1. VERIFICANDO EXISTÊNCIA DOS DOCUMENTOS")
    print("-" * 40)
    
    t220 = Documento.objects.filter(numero='T220').first()
    t221 = Documento.objects.filter(numero='T221').first()
    
    if t220:
        print(f"✅ T220 encontrado:")
        print(f"   ID: {t220.id}")
        print(f"   Imóvel: {t220.imovel.matricula} ({t220.imovel.nome})")
        print(f"   Cartório: {t220.cartorio.nome if t220.cartorio else 'N/A'}")
        print(f"   Tipo: {t220.tipo.tipo}")
    else:
        print("❌ T220 não encontrado")
    
    if t221:
        print(f"✅ T221 encontrado:")
        print(f"   ID: {t221.id}")
        print(f"   Imóvel: {t221.imovel.matricula} ({t221.imovel.nome})")
        print(f"   Cartório: {t221.cartorio.nome if t221.cartorio else 'N/A'}")
        print(f"   Tipo: {t221.tipo.tipo}")
    else:
        print("❌ T221 não encontrado")
    
    # 2. Verificar lançamentos do M197
    print("\n2. VERIFICANDO LANÇAMENTOS DO M197")
    print("-" * 40)
    
    m197 = Documento.objects.filter(numero='M197').first()
    if m197:
        print(f"✅ M197 encontrado no imóvel {m197.imovel.matricula}")
        
        lancamentos = m197.lancamentos.all()
        print(f"   Total de lançamentos: {lancamentos.count()}")
        
        for i, lanc in enumerate(lancamentos, 1):
            print(f"   Lançamento {i}:")
            print(f"     ID: {lanc.id}")
            print(f"     Número: {lanc.numero_lancamento}")
            print(f"     Tipo: {lanc.tipo.tipo}")
            print(f"     Origem: '{lanc.origem}'")
            print(f"     Cartório Origem: {lanc.cartorio_origem}")
    else:
        print("❌ M197 não encontrado")
    
    # 3. Verificar se T220 e T221 são referenciados por algum lançamento
    print("\n3. VERIFICANDO REFERÊNCIAS A T220 E T221")
    print("-" * 40)
    
    # Buscar lançamentos que referenciam T220
    lancamentos_t220 = Lancamento.objects.filter(origem__icontains='T220')
    print(f"Lançamentos que referenciam T220: {lancamentos_t220.count()}")
    for lanc in lancamentos_t220:
        print(f"   Lançamento {lanc.id} (Doc {lanc.documento.numero}): '{lanc.origem}'")
    
    # Buscar lançamentos que referenciam T221
    lancamentos_t221 = Lancamento.objects.filter(origem__icontains='T221')
    print(f"Lançamentos que referenciam T221: {lancamentos_t221.count()}")
    for lanc in lancamentos_t221:
        print(f"   Lançamento {lanc.id} (Doc {lanc.documento.numero}): '{lanc.origem}'")
    
    # 4. Verificar importações existentes
    print("\n4. VERIFICANDO IMPORTAÇÕES EXISTENTES")
    print("-" * 40)
    
    if t220:
        importacoes_t220 = DocumentoImportado.objects.filter(documento=t220)
        print(f"Importações do T220: {importacoes_t220.count()}")
        for imp in importacoes_t220:
            print(f"   Importado para {imp.imovel_origem.matricula} em {imp.data_importacao}")
    
    if t221:
        importacoes_t221 = DocumentoImportado.objects.filter(documento=t221)
        print(f"Importações do T221: {importacoes_t221.count()}")
        for imp in importacoes_t221:
            print(f"   Importado para {imp.imovel_origem.matricula} em {imp.data_importacao}")
    
    # 5. Verificar imóveis M9537 e M9538
    print("\n5. VERIFICANDO IMÓVEIS M9537 E M9538")
    print("-" * 40)
    
    m9537 = Imovel.objects.filter(matricula='M9537').first()
    m9538 = Imovel.objects.filter(matricula='M9538').first()
    
    if m9537:
        print(f"✅ M9537 encontrado (ID: {m9537.id})")
        docs_m9537 = m9537.documentos.all()
        print(f"   Documentos: {[d.numero for d in docs_m9537]}")
    else:
        print("❌ M9537 não encontrado")
    
    if m9538:
        print(f"✅ M9538 encontrado (ID: {m9538.id})")
        docs_m9538 = m9538.documentos.all()
        print(f"   Documentos: {[d.numero for d in docs_m9538]}")
    else:
        print("❌ M9538 não encontrado")
    
    # 6. Simular busca da cadeia dominial
    print("\n6. SIMULANDO BUSCA DA CADEIA DOMINIAL")
    print("-" * 40)
    
    if m197:
        print(f"Simulando busca de cadeia dominial para M197...")
        
        # Buscar lançamentos com origens
        lancamentos_com_origem = m197.lancamentos.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        print(f"Lançamentos com origem: {lancamentos_com_origem.count()}")
        
        for lanc in lancamentos_com_origem:
            print(f"   Lançamento {lanc.id}: '{lanc.origem}'")
            
            if lanc.origem:
                origens = [o.strip() for o in lanc.origem.split(';') if o.strip()]
                print(f"   Origens separadas: {origens}")
                
                for origem_numero in origens:
                    doc_origem = Documento.objects.filter(numero=origem_numero).first()
                    if doc_origem:
                        print(f"     ✅ {origem_numero} encontrado: {doc_origem.imovel.matricula}")
                    else:
                        print(f"     ❌ {origem_numero} NÃO encontrado")

if __name__ == '__main__':
    investigar_documentos_t220_t221()
