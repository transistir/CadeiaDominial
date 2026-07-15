from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import IntegrityError, transaction
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
            origem=None,
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
        origem_a.refresh_from_db()

        origem_b = LancamentoOrigem(
            lancamento=self.lancamento,
            indice_origem=1,
            tipo_documento='transcricao',
            numero='T456',
            cartorio=self.cartorio_b,
        )
        origem_b.full_clean()
        origem_b.save()
        origem_b.refresh_from_db()

        self.assertEqual(self.lancamento.origens_estruturadas.count(), 2)
        self.assertEqual(origem_a.numero, 'M123')
        self.assertEqual(origem_a.numero_normalizado, '123')
        self.assertEqual(origem_a.livro, '10')
        self.assertEqual(origem_a.folha, '20')
        self.assertEqual(origem_b.numero, 'T456')
        self.assertEqual(origem_b.numero_normalizado, '456')
        self.assertEqual(origem_b.cartorio, self.cartorio_b)
        self.assertIn('Matrícula M123', str(origem_a))
        self.assertIn('Transcrição T456', str(origem_b))

    def test_normaliza_numero_da_origem_ao_validar(self):
        origem = LancamentoOrigem(
            lancamento=self.lancamento,
            indice_origem=0,
            tipo_documento='matricula',
            numero='M 00123 ',
            cartorio=self.cartorio_a,
        )

        origem.full_clean()
        origem.save()
        origem.refresh_from_db()

        self.assertEqual(origem.numero, 'M 00123 ')
        self.assertEqual(origem.numero_normalizado, '00123')
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

    def test_cr09_gravacao_direta_preserva_legado_e_recusa_equivalente(self):
        origem = LancamentoOrigem.objects.create(
            lancamento=self.lancamento,
            indice_origem=0,
            tipo_documento='matricula',
            numero=' M 00123 ',
            cartorio=self.cartorio_a,
        )
        origem.refresh_from_db()

        self.assertEqual(origem.numero, ' M 00123 ')
        self.assertEqual(origem.numero_normalizado, '00123')

        with self.assertRaises(IntegrityError), transaction.atomic():
            LancamentoOrigem.objects.create(
                lancamento=self.lancamento,
                indice_origem=1,
                tipo_documento='matricula',
                numero='00123',
                cartorio=self.cartorio_a,
            )

    def test_t22_fluxo_funcional_grava_origens_sem_alterar_texto_legado(self):
        cache_key = f'mapeamento_origens_lancamento_{self.lancamento.pk}'
        cache.set(
            cache_key,
            [
                {
                    'origem': 'M123',
                    'cartorio_id': self.cartorio_a.pk,
                    'cartorio_nome': self.cartorio_a.nome,
                    'livro': ' 10 ',
                    'folha': ' 20 ',
                },
                {
                    'origem': 'T456',
                    'cartorio_id': self.cartorio_b.pk,
                    'cartorio_nome': self.cartorio_b.nome,
                    'livro': '30',
                    'folha': '40',
                },
            ],
            timeout=3600,
        )
        self.addCleanup(cache.delete, cache_key)

        self.lancamento.origem = 'M123; T456'
        self.lancamento.save(update_fields=['origem'])

        self.lancamento.refresh_from_db()
        self.assertEqual(self.lancamento.origem, 'M123; T456')
        self.assertEqual(
            list(
                self.lancamento.origens_estruturadas.values_list(
                    'indice_origem',
                    'tipo_documento',
                    'numero',
                    'numero_normalizado',
                    'cartorio_id',
                    'livro',
                    'folha',
                )
            ),
            [
                (0, 'matricula', 'M123', '123', self.cartorio_a.pk, '10', '20'),
                (1, 'transcricao', 'T456', '456', self.cartorio_b.pk, '30', '40'),
            ],
        )

    def test_t22_reprocessamento_reconcilia_sem_duplicar(self):
        cache_key = f'mapeamento_origens_lancamento_{self.lancamento.pk}'
        self.addCleanup(cache.delete, cache_key)

        def definir_mapeamento(origens):
            cache.set(
                cache_key,
                [
                    {
                        'origem': numero,
                        'cartorio_id': cartorio.pk,
                        'cartorio_nome': cartorio.nome,
                        'livro': livro,
                        'folha': folha,
                    }
                    for numero, cartorio, livro, folha in origens
                ],
                timeout=3600,
            )

        definir_mapeamento([
            ('M123', self.cartorio_a, '10', '20'),
            ('T456', self.cartorio_b, '30', '40'),
        ])
        self.lancamento.origem = 'M123; T456'
        self.lancamento.save(update_fields=['origem'])
        ids_por_numero = dict(
            self.lancamento.origens_estruturadas.values_list('numero', 'id')
        )

        definir_mapeamento([
            ('T456', self.cartorio_b, '31', '41'),
            ('M123', self.cartorio_a, '11', '21'),
        ])
        self.lancamento.origem = 'T456; M123'
        self.lancamento.save(update_fields=['origem'])

        origens = list(self.lancamento.origens_estruturadas.all())
        self.assertEqual(len(origens), 2)
        self.assertEqual([origem.numero for origem in origens], ['T456', 'M123'])
        self.assertEqual(
            {origem.numero: origem.id for origem in origens},
            ids_por_numero,
        )
        self.assertEqual(
            {(origem.numero, origem.livro, origem.folha) for origem in origens},
            {('T456', '31', '41'), ('M123', '11', '21')},
        )

        definir_mapeamento([('M123', self.cartorio_a, '12', '22')])
        self.lancamento.origem = 'M123'
        self.lancamento.save(update_fields=['origem'])
        self.assertEqual(self.lancamento.origens_estruturadas.count(), 1)
        origem_restante = self.lancamento.origens_estruturadas.get()
        self.assertEqual(origem_restante.id, ids_por_numero['M123'])
        self.assertEqual((origem_restante.livro, origem_restante.folha), ('12', '22'))

        self.lancamento.origem = ''
        self.lancamento.save(update_fields=['origem'])
        self.assertFalse(self.lancamento.origens_estruturadas.exists())
