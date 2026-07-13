from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
    Pessoas,
    TIs,
)


class LancamentoOrigemModelTest(TestCase):
    def setUp(self):
        self.tis = TIs.objects.create(
            nome='TI Teste',
            codigo='TESTE',
            etnia='Teste',
        )
        self.pessoa = Pessoas.objects.create(
            nome='Pessoa Teste',
            cpf='12345678901',
        )
        self.cartorio_a = Cartorios.objects.create(
            nome='Cartório A',
            cns='111111',
            cidade='Cidade A',
            estado='SP',
        )
        self.cartorio_b = Cartorios.objects.create(
            nome='Cartório B',
            cns='222222',
            cidade='Cidade B',
            estado='MS',
        )
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Imóvel Teste',
            proprietario=self.pessoa,
            matricula='999',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio_a,
        )
        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=DocumentoTipo.objects.create(tipo='matricula'),
            numero='M999',
            data=timezone.now().date(),
            cartorio=self.cartorio_a,
            livro='1',
            folha='2',
        )
        self.tipo_lancamento = LancamentoTipo.objects.create(tipo='inicio_matricula')
        self.lancamento = Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_lancamento,
            data=timezone.now().date(),
            cartorio_origem=self.cartorio_a,
            origem='M123; T456',
        )

    def test_cria_origens_estruturadas_com_cartorios_distintos(self):
        origem_a = LancamentoOrigem(
            lancamento=self.lancamento,
            indice_origem=0,
            tipo_documento='matricula',
            numero='M123',
            cartorio=self.cartorio_a,
            livro=' 10 ',
            folha=' 20 ',
        )
        origem_a.full_clean()
        origem_a.save()

        origem_b = LancamentoOrigem(
            lancamento=self.lancamento,
            indice_origem=1,
            tipo_documento='transcricao',
            numero='T456',
            cartorio=self.cartorio_b,
        )
        origem_b.full_clean()
        origem_b.save()

        self.assertEqual(self.lancamento.origens_estruturadas.count(), 2)
        self.assertEqual(origem_a.numero, '123')
        self.assertEqual(origem_a.livro, '10')
        self.assertEqual(origem_a.folha, '20')
        self.assertEqual(origem_b.numero, '456')
        self.assertEqual(origem_b.cartorio, self.cartorio_b)
        self.assertIn('Matrícula 123', str(origem_a))
        self.assertIn('Transcrição 456', str(origem_b))

    def test_normaliza_numero_da_origem_ao_validar(self):
        origem = LancamentoOrigem(
            lancamento=self.lancamento,
            indice_origem=0,
            tipo_documento='matricula',
            numero='M 00123 ',
            cartorio=self.cartorio_a,
        )

        origem.full_clean()

        self.assertEqual(origem.numero, '00123')
        self.assertEqual(origem.tipo_documento, 'matricula')

    def test_rejeita_prefixo_incompativel_com_tipo(self):
        origem = LancamentoOrigem(
            lancamento=self.lancamento,
            indice_origem=0,
            tipo_documento='matricula',
            numero='T123',
            cartorio=self.cartorio_a,
        )

        with self.assertRaises(ValidationError):
            origem.full_clean()

    def test_rejeita_origem_duplicada_na_mesma_identidade(self):
        LancamentoOrigem.objects.create(
            lancamento=self.lancamento,
            indice_origem=0,
            tipo_documento='matricula',
            numero='123',
            cartorio=self.cartorio_a,
        )

        duplicada = LancamentoOrigem(
            lancamento=self.lancamento,
            indice_origem=1,
            tipo_documento='matricula',
            numero='M123',
            cartorio=self.cartorio_a,
        )

        with self.assertRaises(ValidationError):
            duplicada.full_clean()
