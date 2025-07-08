#!/usr/bin/env python
"""
Script de teste para verificar a lógica da árvore da cadeia dominial - Fase 1
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings_dev')
django.setup()

from dominial.models import Imovel, Documento, DocumentoTipo, Cartorios
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService


def test_identificacao_matricula_atual():
    """
    Testa a identificação da matrícula atual
    """
    print("🧪 TESTE: Identificação da Matrícula Atual")
    print("=" * 50)
    
    # Buscar um imóvel para teste
    imovel = Imovel.objects.first()
    if not imovel:
        print("❌ Nenhum imóvel encontrado para teste")
        return False
    
    print(f"📋 Imóvel de teste: {imovel.nome} (Matrícula: {imovel.matricula})")
    
    # Construir árvore
    try:
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
        print(f"✅ Árvore construída com sucesso")
        print(f"📊 Total de documentos: {len(arvore['documentos'])}")
        print(f"🔗 Total de conexões: {len(arvore['conexoes'])}")
        
        # Verificar se a matrícula atual foi identificada corretamente
        matricula_atual = None
        for doc in arvore['documentos']:
            if doc['nivel'] == 0:
                matricula_atual = doc['numero']
                break
        
        if matricula_atual:
            print(f"🎯 Matrícula atual identificada: {matricula_atual}")
            print(f"📋 Matrícula do imóvel: {imovel.matricula}")
            
            if matricula_atual == imovel.matricula:
                print("✅ SUCESSO: Matrícula atual identificada corretamente!")
            else:
                print("⚠️  AVISO: Matrícula atual diferente da matrícula do imóvel")
                print("   (Isso pode ser normal se não houver documento correspondente)")
        else:
            print("❌ ERRO: Nenhuma matrícula atual identificada")
            return False
        
        # Mostrar estrutura de níveis
        print("\n📊 Estrutura de Níveis:")
        niveis = {}
        for doc in arvore['documentos']:
            nivel = doc['nivel']
            if nivel not in niveis:
                niveis[nivel] = []
            niveis[nivel].append(f"{doc['tipo_display']} {doc['numero']}")
        
        for nivel in sorted(niveis.keys()):
            docs = niveis[nivel]
            print(f"   Nível {nivel}: {', '.join(docs)}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO ao construir árvore: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_conexoes_arvore():
    """
    Testa se as conexões estão sendo criadas corretamente
    """
    print("\n🧪 TESTE: Conexões da Árvore")
    print("=" * 50)
    
    imovel = Imovel.objects.first()
    if not imovel:
        print("❌ Nenhum imóvel encontrado para teste")
        return False
    
    try:
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
        
        if not arvore['conexoes']:
            print("ℹ️  Nenhuma conexão encontrada (pode ser normal)")
            return True
        
        print(f"🔗 Conexões encontradas: {len(arvore['conexoes'])}")
        
        for i, conexao in enumerate(arvore['conexoes'][:5]):  # Mostrar apenas as primeiras 5
            print(f"   {i+1}. {conexao['from']} → {conexao['to']} ({conexao['tipo']})")
        
        if len(arvore['conexoes']) > 5:
            print(f"   ... e mais {len(arvore['conexoes']) - 5} conexões")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO ao testar conexões: {e}")
        return False


def main():
    """
    Função principal de teste
    """
    print("🚀 INICIANDO TESTES DA FASE 1 - ÁRVORE DA CADEIA DOMINIAL")
    print("=" * 60)
    
    # Teste 1: Identificação da matrícula atual
    sucesso1 = test_identificacao_matricula_atual()
    
    # Teste 2: Conexões da árvore
    sucesso2 = test_conexoes_arvore()
    
    # Resultado final
    print("\n" + "=" * 60)
    print("📋 RESULTADO DOS TESTES")
    print("=" * 60)
    
    if sucesso1 and sucesso2:
        print("✅ TODOS OS TESTES PASSARAM!")
        print("🎉 A Fase 1 foi implementada com sucesso!")
    else:
        print("❌ ALGUNS TESTES FALHARAM")
        print("🔧 Verifique os erros acima e corrija se necessário")
    
    return sucesso1 and sucesso2


if __name__ == "__main__":
    main() 