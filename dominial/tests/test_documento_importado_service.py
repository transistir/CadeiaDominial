"""
Testes unitários para DocumentoService
"""
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from ..models import TIs, Imovel, Documento, DocumentoTipo, Cartorios, DocumentoImportado
from ..services.documento_service import DocumentoService


class DocumentoServiceTest(TestCase):
    """
    Testes para DocumentoService
    """
    
    def setUp(self):
        """Configuração inicial para os testes"""
        # Criar usuário
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Criar cartório
        self.cartorio = Cartorios.objects.create(
            nome='Cartório Teste',
            cidade='Cidade Teste',
            estado='TS'
        )
        
        # Criar tipo de documento
        self.tipo_doc = DocumentoTipo.objects.create(
            tipo='matricula'
        )
        
        # Criar TI
        self.tis = TIs.objects.create(
            nome='TI Teste',
            etnia='Teste',
            estado='TS'
        )
        
        # Criar pessoa para proprietário
        from ..models import Pessoas
        self.pessoa = Pessoas.objects.create(
            nome='Proprietário Teste'
        )

        # Criar imóveis
        self.imovel1 = Imovel.objects.create(
            matricula='123',
            nome='Imóvel 1',
            cartorio=self.cartorio,
            terra_indigena_id=self.tis,
            proprietario=self.pessoa
        )

        self.imovel2 = Imovel.objects.create(
            matricula='456',
            nome='Imóvel 2',
            cartorio=self.cartorio,
            terra_indigena_id=self.tis,
            proprietario=self.pessoa
        )
        
        # Criar documentos
        self.documento1 = Documento.objects.create(
            imovel=self.imovel1,
            tipo=self.tipo_doc,
            numero='DOC001',
            data='2024-01-01',
            cartorio=self.cartorio,
            livro='1',
            folha='1'
        )
        
        self.documento2 = Documento.objects.create(
            imovel=self.imovel2,
            tipo=self.tipo_doc,
            numero='DOC002',
            data='2024-01-02',
            cartorio=self.cartorio,
            livro='2',
            folha='2'
        )
    
    def test_is_documento_importado_false(self):
        """Testa verificação de documento não importado"""
        resultado = DocumentoService.is_documento_importado(self.documento1)
        self.assertFalse(resultado)
    
    def test_is_documento_importado_true(self):
        """Testa verificação de documento importado"""
        # Criar registro de importação
        DocumentoImportado.objects.create(
            documento=self.documento1,
            imovel_origem=self.imovel2,
            importado_por=self.user
        )
        
        resultado = DocumentoService.is_documento_importado(self.documento1)
        self.assertTrue(resultado)
    
    def test_get_info_importacao_none(self):
        """Testa obtenção de informações de documento não importado"""
        resultado = DocumentoService.get_info_importacao(self.documento1)
        self.assertIsNone(resultado)
    
    def test_get_info_importacao_success(self):
        """Testa obtenção de informações de documento importado"""
        # Criar registro de importação
        doc_importado = DocumentoImportado.objects.create(
            documento=self.documento1,
            imovel_origem=self.imovel2,
            importado_por=self.user
        )

        resultado = DocumentoService.get_info_importacao(self.documento1)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['imovel_origem']['id'], self.imovel2.id)
        self.assertEqual(resultado['importado_por']['id'], self.user.id)
        self.assertEqual(resultado['data_importacao'], doc_importado.data_importacao)
    
    @pytest.mark.skip(reason="Method get_documentos_importados_imovel not implemented in DocumentoService")
    def test_get_documentos_importados_imovel(self):
        """Testa obtenção de documentos importados de um imóvel"""
        pass

    @pytest.mark.skip(reason="Method get_documentos_importados_ids not implemented in DocumentoService")
    def test_get_documentos_importados_ids(self):
        """Testa obtenção de IDs de documentos importados"""
        pass

    @pytest.mark.skip(reason="Method get_tooltip_importacao not implemented in DocumentoService")
    def test_get_tooltip_importacao_none(self):
        """Testa geração de tooltip para documento não importado"""
        pass

    @pytest.mark.skip(reason="Method get_tooltip_importacao not implemented in DocumentoService")
    def test_get_tooltip_importacao_success(self):
        """Testa geração de tooltip para documento importado"""
        pass 