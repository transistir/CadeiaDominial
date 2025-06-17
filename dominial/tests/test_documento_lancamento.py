from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from dominial.models import (
    TIs, Pessoas, Imovel, Cartorios,
    DocumentoTipo, LancamentoTipo,
    Documento, Lancamento
)

class DocumentoELancamentoTest(TestCase):
    def setUp(self):
        # Criar dados necessários para os testes
        self.tis = TIs.objects.create(
            nome="TI Teste",
            codigo="TEST001",
            etnia="Teste"
        )
        
        self.cartorio = Cartorios.objects.create(
            nome="Cartório Teste",
            cns="123456",
            cidade="Cidade Teste",
            estado="TS"
        )
        
        self.pessoa1 = Pessoas.objects.create(
            nome="Pessoa 1",
            cpf="12345678901"
        )
        
        self.pessoa2 = Pessoas.objects.create(
            nome="Pessoa 2",
            cpf="98765432109"
        )
        
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel Teste",
            proprietario=self.pessoa1,
            matricula="123456",
            sncr="789012"
        )
        
        # Criar tipos de documento e lançamento
        self.tipo_transmissao = DocumentoTipo.objects.create(tipo='transmissao')
        self.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        self.tipo_registro = LancamentoTipo.objects.create(tipo='registro')
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')

    def test_criar_documento_transmissao(self):
        """Testa a criação de um documento do tipo transmissão"""
        documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_transmissao,
            numero="TRANS001",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1"
        )
        self.assertEqual(documento.tipo.tipo, 'transmissao')
        self.assertEqual(str(documento), f"Transmissão - TRANS001")

    def test_criar_documento_matricula(self):
        """Testa a criação de um documento do tipo matrícula"""
        documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="MAT001",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1"
        )
        self.assertEqual(documento.tipo.tipo, 'matricula')
        self.assertEqual(str(documento), f"Matrícula - MAT001")

    def test_criar_lancamento_registro(self):
        """Testa a criação de um lançamento do tipo registro"""
        documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_transmissao,
            numero="TRANS001",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1"
        )
        
        lancamento = Lancamento.objects.create(
            documento=documento,
            tipo=self.tipo_registro,
            data=timezone.now().date(),
            transmitente=self.pessoa1,
            adquirente=self.pessoa2,
            valor_transacao=100000.00
        )
        
        self.assertEqual(lancamento.tipo.tipo, 'registro')
        self.assertEqual(str(lancamento), f"Registro - Transmissão - TRANS001")

    def test_criar_lancamento_averbacao(self):
        """Testa a criação de um lançamento do tipo averbação"""
        documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="MAT001",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1"
        )
        
        lancamento = Lancamento.objects.create(
            documento=documento,
            tipo=self.tipo_averbacao,
            data=timezone.now().date(),
            detalhes="Averbação de testamento"
        )
        
        self.assertEqual(lancamento.tipo.tipo, 'averbacao')
        self.assertEqual(str(lancamento), f"Averbação - Matrícula - MAT001")

    def test_validacao_registro_sem_transmitente(self):
        """Testa a validação de registro sem transmitente"""
        documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_transmissao,
            numero="TRANS001",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1"
        )
        
        lancamento = Lancamento(
            documento=documento,
            tipo=self.tipo_registro,
            data=timezone.now().date(),
            adquirente=self.pessoa2
        )
        
        with self.assertRaises(ValidationError):
            lancamento.full_clean()

    def test_validacao_registro_sem_adquirente(self):
        """Testa a validação de registro sem adquirente"""
        documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_transmissao,
            numero="TRANS001",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1"
        )
        
        lancamento = Lancamento(
            documento=documento,
            tipo=self.tipo_registro,
            data=timezone.now().date(),
            transmitente=self.pessoa1
        )
        
        with self.assertRaises(ValidationError):
            lancamento.full_clean()

    def test_validacao_averbacao_sem_detalhes(self):
        """Testa a validação de averbação sem detalhes"""
        documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="MAT001",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1"
        )
        
        lancamento = Lancamento(
            documento=documento,
            tipo=self.tipo_averbacao,
            data=timezone.now().date()
        )
        
        with self.assertRaises(ValidationError):
            lancamento.full_clean() 