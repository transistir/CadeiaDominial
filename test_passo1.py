#!/usr/bin/env python
"""
Script de teste para o Passo 1 - DocumentoImportadoService
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings_dev')
django.setup()

from django.contrib.auth.models import User
from dominial.models import TIs, Imovel, Documento, DocumentoTipo, Cartorios, DocumentoImportado
from dominial.services.documento_importado_service import DocumentoImportadoService


def test_documento_importado_service():
    """Testa o DocumentoImportadoService"""
    print("🧪 TESTANDO PASSO 1 - DocumentoImportadoService")
    print("=" * 60)
    
    # Criar dados de teste
    print("📝 Criando dados de teste...")
    
    # Criar usuário
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@example.com'}
    )
    if created:
        user.set_password('testpass123')
        user.save()
    print(f"✅ Usuário: {user.username}")
    
    # Criar cartório
    cartorio, created = Cartorios.objects.get_or_create(
        nome='Cartório Teste',
        defaults={'cidade': 'Cidade Teste', 'estado': 'TS'}
    )
    print(f"✅ Cartório: {cartorio.nome}")
    
    # Criar tipo de documento
    tipo_doc, created = DocumentoTipo.objects.get_or_create(
        tipo='matricula',
        defaults={'descricao': 'Matrícula'}
    )
    print(f"✅ Tipo documento: {tipo_doc.descricao}")
    
    # Criar TI
    tis, created = TIs.objects.get_or_create(
        nome='TI Teste',
        defaults={'etnia': 'Teste', 'estado': 'TS'}
    )
    print(f"✅ TI: {tis.nome}")
    
    # Criar imóveis
    imovel1, created = Imovel.objects.get_or_create(
        matricula='123',
        defaults={
            'nome': 'Imóvel 1',
            'cartorio': cartorio,
            'terra_indigena': tis
        }
    )
    print(f"✅ Imóvel 1: {imovel1.matricula}")
    
    imovel2, created = Imovel.objects.get_or_create(
        matricula='456',
        defaults={
            'nome': 'Imóvel 2',
            'cartorio': cartorio,
            'terra_indigena': tis
        }
    )
    print(f"✅ Imóvel 2: {imovel2.matricula}")
    
    # Criar documentos
    documento1, created = Documento.objects.get_or_create(
        numero='DOC001',
        imovel=imovel1,
        defaults={
            'tipo': tipo_doc,
            'data': '2024-01-01',
            'cartorio': cartorio,
            'livro': '1',
            'folha': '1'
        }
    )
    print(f"✅ Documento 1: {documento1.numero}")
    
    documento2, created = Documento.objects.get_or_create(
        numero='DOC002',
        imovel=imovel2,
        defaults={
            'tipo': tipo_doc,
            'data': '2024-01-02',
            'cartorio': cartorio,
            'livro': '2',
            'folha': '2'
        }
    )
    print(f"✅ Documento 2: {documento2.numero}")
    
    print("\n🔍 TESTANDO FUNCIONALIDADES:")
    print("-" * 40)
    
    # Teste 1: Verificar documento não importado
    print("\n1️⃣ Teste: Documento não importado")
    resultado = DocumentoImportadoService.is_documento_importado(documento1)
    print(f"   is_documento_importado: {resultado}")
    assert not resultado, "Documento não deveria ser importado"
    print("   ✅ PASSOU")
    
    # Teste 2: Verificar info importação de documento não importado
    print("\n2️⃣ Teste: Info importação de documento não importado")
    info = DocumentoImportadoService.get_info_importacao(documento1)
    print(f"   info_importacao: {info}")
    assert info is None, "Info deveria ser None"
    print("   ✅ PASSOU")
    
    # Teste 3: Verificar tooltip de documento não importado
    print("\n3️⃣ Teste: Tooltip de documento não importado")
    tooltip = DocumentoImportadoService.get_tooltip_importacao(documento1)
    print(f"   tooltip: {tooltip}")
    assert tooltip is None, "Tooltip deveria ser None"
    print("   ✅ PASSOU")
    
    # Criar registro de importação
    print("\n📥 Criando registro de importação...")
    doc_importado, created = DocumentoImportado.objects.get_or_create(
        documento=documento1,
        imovel_origem=imovel2,
        defaults={'importado_por': user}
    )
    print(f"✅ Documento importado: {documento1.numero} de {imovel2.matricula}")
    
    # Teste 4: Verificar documento importado
    print("\n4️⃣ Teste: Documento importado")
    resultado = DocumentoImportadoService.is_documento_importado(documento1)
    print(f"   is_documento_importado: {resultado}")
    assert resultado, "Documento deveria ser importado"
    print("   ✅ PASSOU")
    
    # Teste 5: Verificar info importação de documento importado
    print("\n5️⃣ Teste: Info importação de documento importado")
    info = DocumentoImportadoService.get_info_importacao(documento1)
    print(f"   info_importacao: {info}")
    assert info is not None, "Info não deveria ser None"
    assert info['imovel_origem'] == imovel2, "Imóvel de origem incorreto"
    assert info['importado_por'] == user, "Importador incorreto"
    print("   ✅ PASSOU")
    
    # Teste 6: Verificar tooltip de documento importado
    print("\n6️⃣ Teste: Tooltip de documento importado")
    tooltip = DocumentoImportadoService.get_tooltip_importacao(documento1)
    print(f"   tooltip: {tooltip}")
    assert tooltip is not None, "Tooltip não deveria ser None"
    assert '456' in tooltip, "Tooltip deveria conter matrícula de origem"
    assert 'testuser' in tooltip, "Tooltip deveria conter username"
    print("   ✅ PASSOU")
    
    # Teste 7: Verificar documentos importados do imóvel
    print("\n7️⃣ Teste: Documentos importados do imóvel")
    docs_importados = DocumentoImportadoService.get_documentos_importados_imovel(imovel1)
    print(f"   documentos_importados: {docs_importados.count()}")
    assert docs_importados.count() == 1, "Deveria ter 1 documento importado"
    print("   ✅ PASSOU")
    
    # Teste 8: Verificar IDs de documentos importados
    print("\n8️⃣ Teste: IDs de documentos importados")
    ids_importados = DocumentoImportadoService.get_documentos_importados_ids(imovel1)
    print(f"   ids_importados: {ids_importados}")
    assert documento1.id in ids_importados, "ID do documento deveria estar na lista"
    assert documento2.id not in ids_importados, "ID do documento 2 não deveria estar na lista"
    print("   ✅ PASSOU")
    
    print("\n🎉 TODOS OS TESTES PASSARAM!")
    print("=" * 60)
    print("✅ PASSO 1 - DocumentoImportadoService está funcionando corretamente!")
    
    # Limpar dados de teste
    print("\n🧹 Limpando dados de teste...")
    DocumentoImportado.objects.filter(documento=documento1).delete()
    print("✅ Dados de teste removidos")


if __name__ == '__main__':
    test_documento_importado_service() 