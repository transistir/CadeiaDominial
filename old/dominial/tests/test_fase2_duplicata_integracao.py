"""
Testes para Fase 2 - Integração da verificação de duplicatas com formulário de lançamento
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from ..models import (
    TIs, Imovel, Documento, DocumentoTipo, Cartorios, 
    Lancamento, LancamentoTipo, Pessoas
)
from ..services.lancamento_duplicata_service import LancamentoDuplicataService


class Fase2DuplicataIntegracaoTest(TestCase):
    """
    Testes para integração da verificação de duplicatas com o formulário de lançamento
    """
    
    def setUp(self):
        """Configurar dados de teste"""
        # Criar usuário
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Criar TIs
        self.tis = TIs.objects.create(
            nome='TIs Teste',
            etnia='Teste',
            estado='SP'
        )
        
        # Criar cartório
        self.cartorio = Cartorios.objects.create(
            nome='Cartório Teste',
            cns='CNS123456',
            cidade='São Paulo'
        )
        
        # Criar tipos de documento
        self.tipo_matricula = DocumentoTipo.objects.create(
            tipo='matricula',
            descricao='Matrícula'
        )
        self.tipo_transcricao = DocumentoTipo.objects.create(
            tipo='transcricao',
            descricao='Transcrição'
        )
        
        # Criar tipos de lançamento
        self.tipo_registro = LancamentoTipo.objects.create(
            tipo='registro',
            descricao='Registro'
        )
        
        # Criar imóveis
        self.imovel_origem = Imovel.objects.create(
            nome='Imóvel Origem',
            matricula='12345',
            terra_indigena=self.tis,
            cartorio=self.cartorio
        )
        
        self.imovel_destino = Imovel.objects.create(
            nome='Imóvel Destino',
            matricula='67890',
            terra_indigena=self.tis,
            cartorio=self.cartorio
        )
        
        # Criar documentos
        self.documento_origem = Documento.objects.create(
            numero='12345',
            tipo=self.tipo_matricula,
            imovel=self.imovel_origem,
            cartorio=self.cartorio,
            livro='1',
            folha='1'
        )
        
        self.documento_destino = Documento.objects.create(
            numero='67890',
            tipo=self.tipo_matricula,
            imovel=self.imovel_destino,
            cartorio=self.cartorio,
            livro='2',
            folha='2'
        )
        
        # Criar lançamentos no documento de origem
        self.lancamento_origem = Lancamento.objects.create(
            documento=self.documento_origem,
            tipo=self.tipo_registro,
            numero_lancamento='R112345',
            data='2023-01-01',
            observacoes='Lançamento de origem'
        )
        
        # Configurar cliente
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_verificar_duplicata_antes_criacao_sem_duplicata(self):
        """Testar verificação quando não há duplicata"""
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        factory = RequestFactory()
        request = factory.post('/fake-url/', {
            'origem_completa': 'Origem diferente',
            'cartorio': str(self.cartorio.id)
        })
        
        # Configurar messages
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
            request, self.documento_destino
        )
        
        self.assertFalse(resultado['tem_duplicata'])
        self.assertIn('Nenhuma duplicata encontrada', resultado['mensagem'])
    
    def test_verificar_duplicata_antes_criacao_com_duplicata(self):
        """Testar verificação quando há duplicata"""
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        factory = RequestFactory()
        request = factory.post('/fake-url/', {
            'origem_completa': str(self.documento_origem.numero),
            'cartorio': str(self.cartorio.id)
        })
        
        # Configurar messages
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
            request, self.documento_destino
        )
        
        self.assertTrue(resultado['tem_duplicata'])
        self.assertIn('Encontrada duplicata', resultado['mensagem'])
        self.assertEqual(resultado['documento_origem'], self.documento_origem)
    
    def test_verificar_duplicata_sem_origem(self):
        """Testar verificação sem origem fornecida"""
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        factory = RequestFactory()
        request = factory.post('/fake-url/', {
            'cartorio': str(self.cartorio.id)
        })
        
        # Configurar messages
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
            request, self.documento_destino
        )
        
        self.assertFalse(resultado['tem_duplicata'])
        self.assertIn('Origem ou cartório não fornecidos', resultado['mensagem'])
    
    def test_verificar_duplicata_cartorio_inexistente(self):
        """Testar verificação com cartório inexistente"""
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        factory = RequestFactory()
        request = factory.post('/fake-url/', {
            'origem_completa': 'Origem teste',
            'cartorio': '99999'  # ID inexistente
        })
        
        # Configurar messages
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
            request, self.documento_destino
        )
        
        self.assertFalse(resultado['tem_duplicata'])
        self.assertIn('Cartório não encontrado', resultado['mensagem'])
    
    def test_obter_dados_duplicata_para_template(self):
        """Testar formatação de dados para template"""
        # Criar dados de duplicata simulados
        duplicata_info = {
            'tem_duplicata': True,
            'documento_origem': self.documento_origem,
            'documentos_importaveis': [self.documento_origem],
            'cadeia_dominial': [{
                'documento': self.documento_origem,
                'lancamentos': [self.lancamento_origem]
            }]
        }
        
        dados_template = LancamentoDuplicataService.obter_dados_duplicata_para_template(
            duplicata_info
        )
        
        self.assertIsNotNone(dados_template)
        self.assertEqual(dados_template['documento_origem']['numero'], '12345')
        self.assertEqual(dados_template['documento_origem']['tipo'], 'Matrícula')
        self.assertEqual(len(dados_template['documentos_importaveis']), 1)
        self.assertEqual(len(dados_template['cadeia_dominial']), 1)
    
    def test_obter_dados_duplicata_sem_duplicata(self):
        """Testar formatação quando não há duplicata"""
        duplicata_info = {
            'tem_duplicata': False
        }
        
        dados_template = LancamentoDuplicataService.obter_dados_duplicata_para_template(
            duplicata_info
        )
        
        self.assertIsNone(dados_template)
    
    def test_processar_importacao_duplicata_sucesso(self):
        """Testar processamento de importação com sucesso"""
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        factory = RequestFactory()
        request = factory.post('/fake-url/', {
            'documento_origem_id': str(self.documento_origem.id),
            'documentos_importaveis[]': [str(self.documento_origem.id)]
        })
        
        # Configurar messages
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        resultado = LancamentoDuplicataService.processar_importacao_duplicata(
            request, self.documento_destino, self.user
        )
        
        self.assertTrue(resultado['sucesso'])
        self.assertIn('Importação realizada com sucesso', resultado['mensagem'])
    
    def test_processar_importacao_duplicata_sem_documento_origem(self):
        """Testar importação sem documento de origem"""
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        factory = RequestFactory()
        request = factory.post('/fake-url/', {
            'documentos_importaveis[]': [str(self.documento_origem.id)]
        })
        
        # Configurar messages
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        resultado = LancamentoDuplicataService.processar_importacao_duplicata(
            request, self.documento_destino, self.user
        )
        
        self.assertFalse(resultado['sucesso'])
        self.assertIn('Documento de origem não especificado', resultado['mensagem'])
    
    def test_processar_importacao_duplicata_documento_inexistente(self):
        """Testar importação com documento inexistente"""
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        factory = RequestFactory()
        request = factory.post('/fake-url/', {
            'documento_origem_id': '99999',  # ID inexistente
            'documentos_importaveis[]': [str(self.documento_origem.id)]
        })
        
        # Configurar messages
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        resultado = LancamentoDuplicataService.processar_importacao_duplicata(
            request, self.documento_destino, self.user
        )
        
        self.assertFalse(resultado['sucesso'])
        self.assertIn('Documento de origem não encontrado', resultado['mensagem'])
    
    def test_url_verificar_duplicata_ajax(self):
        """Testar URL de verificação AJAX"""
        url = reverse('verificar_duplicata_ajax', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel_destino.id,
            'documento_id': self.documento_destino.id
        })
        
        response = self.client.post(url, {
            'origem_completa': str(self.documento_origem.numero),
            'cartorio': str(self.cartorio.id)
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['tem_duplicata'])
    
    def test_url_importar_duplicata(self):
        """Testar URL de importação de duplicata"""
        url = reverse('importar_duplicata', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel_destino.id,
            'documento_id': self.documento_destino.id
        })
        
        response = self.client.post(url, {
            'documento_origem_id': str(self.documento_origem.id),
            'documentos_importaveis[]': [str(self.documento_origem.id)]
        })
        
        # Deve redirecionar após importação
        self.assertIn(response.status_code, [200, 302])
    
    def test_url_cancelar_importacao(self):
        """Testar URL de cancelamento de importação"""
        url = reverse('cancelar_importacao_duplicata', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel_destino.id,
            'documento_id': self.documento_destino.id
        })
        
        response = self.client.get(url)
        
        # Deve redirecionar após cancelamento
        self.assertEqual(response.status_code, 302) 