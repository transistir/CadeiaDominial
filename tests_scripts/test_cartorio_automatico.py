#!/usr/bin/env python3
"""
Teste para verificar se o auto-preenchimento está usando o cartório correto da origem
"""

import os
import sys
import django
import time

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
django.setup()

from dominial.models import TIs, Imovel, Documento, Cartorios, DocumentoTipo, Lancamento, LancamentoTipo
from dominial.services.lancamento_form_service import LancamentoFormService
from dominial.services.lancamento_documento_service import LancamentoDocumentoService
from datetime import date

def test_cartorio_automatico():
    """
    Testa se o auto-preenchimento está usando o cartório correto da origem
    """
    print("=== Teste de Cartório Automático ===")
    
    # Criar dados de teste
    try:
        # Gerar código único para TIs
        codigo_tis = f"TST{int(time.time())}"
        # Criar TIs
        tis = TIs.objects.create(
            nome="Teste TIs",
            estado="SP",
            area=1000.0,
            codigo=codigo_tis  # Valor único para evitar conflito
        )
        
        # Gerar CNS únicos para os cartórios
        cns_origem = f"CNS{int(time.time())}1"
        cns_atual = f"CNS{int(time.time())}2"
        # Criar cartórios
        cartorio_origem = Cartorios.objects.create(
            nome="Cartório de Origem",
            tipo="CRI",
            cidade="São Paulo",
            estado="SP",
            cns=cns_origem  # CNS único
        )
        
        cartorio_atual = Cartorios.objects.create(
            nome="Cartório Atual",
            tipo="CRI", 
            cidade="Rio de Janeiro",
            estado="RJ",
            cns=cns_atual  # CNS único
        )
        
        # Criar proprietário de teste
        from dominial.models import Pessoas
        proprietario = Pessoas.objects.create(
            nome="Proprietário Teste",
            cpf="00000000000"
        )
        # Criar imóvel
        imovel = Imovel.objects.create(
            terra_indigena_id=tis,
            matricula="M123",
            cartorio=cartorio_atual,  # Cartório atual do imóvel
            proprietario=proprietario
        )
        
        # Criar tipo de documento
        tipo_doc = DocumentoTipo.objects.get_or_create(tipo='matricula')[0]
        
        # Criar documento de origem (com cartório correto)
        documento_origem = Documento.objects.create(
            imovel=imovel,
            tipo=tipo_doc,
            numero="M456",
            data=date.today(),
            cartorio=cartorio_origem,  # Cartório da origem
            livro="1",
            folha="1",
            origem="Criado automaticamente a partir de origem: M456",
            observacoes="Documento de origem"
        )
        
        # Criar documento atual (com cartório diferente)
        documento_atual = Documento.objects.create(
            imovel=imovel,
            tipo=tipo_doc,
            numero="M123",
            data=date.today(),
            cartorio=cartorio_atual,  # Cartório atual
            livro="2",
            folha="2",
            origem="Matrícula atual do imóvel",
            observacoes="Documento atual"
        )
        
        print(f"Documento de origem: {documento_origem.numero} - Cartório: {documento_origem.cartorio.nome}")
        print(f"Documento atual: {documento_atual.numero} - Cartório: {documento_atual.cartorio.nome}")
        
        # Testar obter_documento_ativo
        documento_ativo = LancamentoDocumentoService.obter_documento_ativo(imovel)
        print(f"Documento ativo selecionado: {documento_ativo.numero} - Cartório: {documento_ativo.cartorio.nome}")
        
        # Testar obter_dados_preenchimento_automatico
        lancamentos_existentes = documento_ativo.lancamentos.count()
        dados_automaticos = LancamentoFormService.obter_dados_preenchimento_automatico(documento_ativo, lancamentos_existentes)
        
        print(f"Dados automáticos:")
        print(f"  Cartório ID: {dados_automaticos['cartorio_id']}")
        print(f"  Cartório Nome: {dados_automaticos['cartorio_nome']}")
        
        # Verificar se está usando o cartório correto
        if dados_automaticos['cartorio_id'] == str(cartorio_origem.id):
            print("✅ SUCESSO: Auto-preenchimento está usando o cartório da origem")
        else:
            print("❌ ERRO: Auto-preenchimento não está usando o cartório da origem")
            print(f"  Esperado: {cartorio_origem.id} ({cartorio_origem.nome})")
            print(f"  Obtido: {dados_automaticos['cartorio_id']} ({dados_automaticos['cartorio_nome']})")
        
        # Limpar dados de teste
        documento_origem.delete()
        documento_atual.delete()
        imovel.delete()
        cartorio_origem.delete()
        cartorio_atual.delete()
        tis.delete()
        
    except Exception as e:
        print(f"❌ Erro durante o teste: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    test_cartorio_automatico() 