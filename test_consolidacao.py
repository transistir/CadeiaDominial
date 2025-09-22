#!/usr/bin/env python
"""
Script de teste para verificar se a consolidação dos services não quebrou funcionalidades
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
django.setup()

def test_services_import():
    """Testa se os services consolidados podem ser importados"""
    print("🧪 Testando imports dos services consolidados...")
    
    try:
        from dominial.services import LancamentoService, HierarquiaService, DocumentoService
        print("✅ LancamentoService importado com sucesso")
        print("✅ HierarquiaService importado com sucesso")
        print("✅ DocumentoService importado com sucesso")
        return True
    except ImportError as e:
        print(f"❌ Erro ao importar services: {e}")
        return False

def test_lancamento_service_methods():
    """Testa se os métodos do LancamentoService estão disponíveis"""
    print("\n🧪 Testando métodos do LancamentoService...")
    
    try:
        from dominial.services import LancamentoService
        
        # Verificar se os métodos consolidados estão disponíveis
        methods = [
            'obter_tipos_lancamento_por_documento',
            'validar_numero_lancamento', 
            'processar_pessoas_lancamento',
            'processar_cartorio_origem',
            'obter_documento_ativo',
            'criar_lancamento_completo'
        ]
        
        for method in methods:
            if hasattr(LancamentoService, method):
                print(f"✅ Método {method} disponível")
            else:
                print(f"❌ Método {method} não encontrado")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Erro ao testar LancamentoService: {e}")
        return False

def test_hierarquia_service_methods():
    """Testa se os métodos do HierarquiaService estão disponíveis"""
    print("\n🧪 Testando métodos do HierarquiaService...")
    
    try:
        from dominial.services import HierarquiaService
        
        # Verificar se os métodos consolidados estão disponíveis
        methods = [
            'obter_tronco_principal',
            'obter_troncos_secundarios',
            'calcular_hierarquia_documentos',
            'validar_hierarquia',
            'construir_arvore_cadeia_dominial',
            'processar_origens_identificadas'
        ]
        
        for method in methods:
            if hasattr(HierarquiaService, method):
                print(f"✅ Método {method} disponível")
            else:
                print(f"❌ Método {method} não encontrado")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Erro ao testar HierarquiaService: {e}")
        return False

def test_documento_service_methods():
    """Testa se os métodos do DocumentoService estão disponíveis"""
    print("\n🧪 Testando métodos do DocumentoService...")
    
    try:
        from dominial.services import DocumentoService
        
        # Verificar se os métodos consolidados estão disponíveis
        methods = [
            'criar_documento',
            'obter_documentos_imovel',
            'validar_documento_unico',
            'is_documento_importado',
            'get_info_importacao',
            'is_documento_compartilhado',
            'obter_documentos_compartilhados'
        ]
        
        for method in methods:
            if hasattr(DocumentoService, method):
                print(f"✅ Método {method} disponível")
            else:
                print(f"❌ Método {method} não encontrado")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Erro ao testar DocumentoService: {e}")
        return False

def test_models_import():
    """Testa se os models ainda podem ser importados"""
    print("\n🧪 Testando imports dos models...")
    
    try:
        from dominial.models import (
            TIs, Imovel, Documento, Lancamento, 
            Pessoas, Cartorios, DocumentoTipo, LancamentoTipo
        )
        print("✅ Todos os models importados com sucesso")
        return True
    except ImportError as e:
        print(f"❌ Erro ao importar models: {e}")
        return False

def test_views_import():
    """Testa se as views ainda podem ser importadas"""
    print("\n🧪 Testando imports das views...")
    
    try:
        from dominial.views import (
            home, tis_form, imovel_form, novo_lancamento,
            cadeia_dominial_d3, documento_lancamentos
        )
        print("✅ Views principais importadas com sucesso")
        return True
    except ImportError as e:
        print(f"❌ Erro ao importar views: {e}")
        return False

def main():
    """Executa todos os testes"""
    print("🚀 Iniciando testes de funcionalidade após consolidação...")
    print("=" * 60)
    
    tests = [
        test_services_import,
        test_lancamento_service_methods,
        test_hierarquia_service_methods,
        test_documento_service_methods,
        test_models_import,
        test_views_import
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"📊 Resultado dos testes: {passed}/{total} passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram! A consolidação foi bem-sucedida.")
        return True
    else:
        print("⚠️  Alguns testes falharam. Verificar problemas.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
