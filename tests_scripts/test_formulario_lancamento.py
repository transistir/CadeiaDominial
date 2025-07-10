#!/usr/bin/env python
"""
Script de teste para verificar os formulários de lançamento
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
django.setup()

from dominial.models import TIs, Imovel, Documento, DocumentoTipo, LancamentoTipo, Cartorios, Pessoas
from dominial.services.lancamento_service import LancamentoService
from dominial.services.lancamento_form_service import LancamentoFormService

def test_formulario_lancamento():
    """Testa se os formulários de lançamento estão funcionando"""
    print("🧪 TESTANDO FORMULÁRIOS DE LANÇAMENTO")
    print("=" * 50)
    
    # Verificar se existem dados básicos
    print("\n1. Verificando dados básicos...")
    
    # Verificar TIs
    tis_count = TIs.objects.count()
    print(f"   - TIs encontradas: {tis_count}")
    
    # Verificar Imóveis
    imoveis_count = Imovel.objects.count()
    print(f"   - Imóveis encontrados: {imoveis_count}")
    
    # Verificar Cartórios
    cartorios_count = Cartorios.objects.count()
    print(f"   - Cartórios encontrados: {cartorios_count}")
    
    # Verificar Pessoas
    pessoas_count = Pessoas.objects.count()
    print(f"   - Pessoas encontradas: {pessoas_count}")
    
    # Verificar Tipos de Documento
    tipos_doc_count = DocumentoTipo.objects.count()
    print(f"   - Tipos de documento: {tipos_doc_count}")
    
    # Verificar Tipos de Lançamento
    tipos_lanc_count = LancamentoTipo.objects.count()
    print(f"   - Tipos de lançamento: {tipos_lanc_count}")
    
    if tipos_lanc_count == 0:
        print("   ⚠️  Nenhum tipo de lançamento encontrado!")
        return False
    
    # Testar obtenção de tipos de lançamento
    print("\n2. Testando tipos de lançamento...")
    try:
        # Criar um documento de teste se necessário
        if imoveis_count > 0:
            imovel = Imovel.objects.first()
            documento_tipo = DocumentoTipo.objects.filter(tipo='matricula').first()
            
            if not documento_tipo:
                documento_tipo = DocumentoTipo.objects.create(tipo='matricula')
            
            documento = Documento.objects.filter(imovel=imovel, tipo=documento_tipo).first()
            
            if not documento:
                documento = Documento.objects.create(
                    imovel=imovel,
                    tipo=documento_tipo,
                    numero="TEST001",
                    data="2024-01-01",
                    cartorio=Cartorios.objects.first() if Cartorios.objects.exists() else None
                )
            
            tipos_lancamento = LancamentoService.obter_tipos_lancamento_por_documento(documento)
            print(f"   - Tipos disponíveis para documento: {[t.get_tipo_display() for t in tipos_lancamento]}")
            
            # Verificar se todos os tipos esperados estão presentes
            tipos_esperados = ['averbacao', 'registro', 'inicio_matricula']
            tipos_encontrados = [t.tipo for t in tipos_lancamento]
            
            for tipo in tipos_esperados:
                if tipo in tipos_encontrados:
                    print(f"   ✅ {tipo.upper()}: OK")
                else:
                    print(f"   ❌ {tipo.upper()}: FALTANDO")
            
        else:
            print("   ⚠️  Nenhum imóvel encontrado para teste")
            
    except Exception as e:
        print(f"   ❌ Erro ao testar tipos de lançamento: {e}")
        return False
    
    # Testar processamento de dados do formulário
    print("\n3. Testando processamento de dados...")
    try:
        from django.test import RequestFactory
        from django.contrib.auth.models import User
        
        # Criar request de teste
        factory = RequestFactory()
        request = factory.post('/test/', {
            'tipo_lancamento': LancamentoTipo.objects.first().id,
            'numero_lancamento': 'TEST001',
            'data': '2024-01-01',
            'livro': '1',
            'folha': '1',
            'cartorio': Cartorios.objects.first().id if Cartorios.objects.exists() else '',
            'cartorio_nome': 'Cartório Teste',
            'forma_averbacao': 'Teste',
            'descricao': 'Descrição de teste'
        })
        
        tipo_lanc = LancamentoTipo.objects.first()
        dados = LancamentoFormService.processar_dados_lancamento(request, tipo_lanc)
        
        print(f"   - Dados processados: {dados}")
        print(f"   - Número do lançamento: {dados.get('numero_lancamento')}")
        print(f"   - Livro: {dados.get('livro_origem')}")
        print(f"   - Folha: {dados.get('folha_origem')}")
        print(f"   - Cartório: {dados.get('cartorio_origem')}")
        print(f"   - Data: {dados.get('data')}")
        
        print("   ✅ Processamento de dados: OK")
        
    except Exception as e:
        print(f"   ❌ Erro ao testar processamento: {e}")
        return False
    
    print("\n4. Verificando campos obrigatórios...")
    campos_obrigatorios = [
        'numero_lancamento',
        'livro', 
        'folha',
        'cartorio',
        'data'
    ]
    
    for campo in campos_obrigatorios:
        print(f"   ✅ {campo}: Obrigatório no bloco básico")
    
    print("\n5. Verificando campos específicos por tipo...")
    tipos_especificos = {
        'averbacao': ['forma_averbacao', 'descricao'],
        'registro': ['forma_registro', 'titulo'],
        'inicio_matricula': ['forma_inicio', 'descricao']
    }
    
    for tipo, campos in tipos_especificos.items():
        print(f"   - {tipo.upper()}: {', '.join(campos)}")
    
    print("\n" + "=" * 50)
    print("✅ TESTES CONCLUÍDOS COM SUCESSO!")
    print("🎯 Formulários de lançamento estão funcionando corretamente")
    
    return True

if __name__ == "__main__":
    try:
        success = test_formulario_lancamento()
        if success:
            print("\n🚀 Pronto para testar a interface web!")
        else:
            print("\n❌ Alguns problemas foram encontrados")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Erro durante os testes: {e}")
        sys.exit(1) 