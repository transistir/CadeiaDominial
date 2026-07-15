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
from dominial.services.cadeia_completa_service import CadeiaCompletaService
from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.services.hierarquia_origem_service import HierarquiaOrigemService
from dominial.services.lancamento_origem_leitura_service import (
    LancamentoOrigemLeituraService,
)
from dominial.utils.hierarquia_utils import identificar_tronco_principal


class LancamentoOrigemLeituraServiceTest(TestCase):
    def setUp(self):
        tis = TIs.objects.create(nome='TI T24', codigo='T24', etnia='Teste')
        pessoa = Pessoas.objects.create(nome='Pessoa T24', cpf='11122233344')
        self.cartorio_a = Cartorios.objects.create(
            nome='Cartório A T24', cns='444444', cidade='A', estado='SP'
        )
        self.cartorio_b = Cartorios.objects.create(
            nome='Cartório B T24', cns='555555', cidade='B', estado='MS'
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        self.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')

        self.imovel_atual = self._criar_imovel(
            tis, pessoa, '900', self.cartorio_a, 'Atual'
        )
        self.imovel_a = self._criar_imovel(
            tis, pessoa, '901', self.cartorio_a, 'Legado A'
        )
        self.imovel_b = self._criar_imovel(
            tis, pessoa, '902', self.cartorio_b, 'Estruturado B'
        )
        self.documento_atual = self._criar_documento(
            self.imovel_atual, self.tipo_matricula, 'M900', self.cartorio_a
        )
        self.documento_a = self._criar_documento(
            self.imovel_a, self.tipo_matricula, 'M111', self.cartorio_a
        )
        self.documento_b = self._criar_documento(
            self.imovel_b, self.tipo_transcricao, 'T222', self.cartorio_b
        )

    @staticmethod
    def _criar_imovel(tis, pessoa, matricula, cartorio, nome):
        return Imovel.objects.create(
            terra_indigena_id=tis,
            nome=nome,
            proprietario=pessoa,
            matricula=matricula,
            tipo_documento_principal='matricula',
            cartorio=cartorio,
        )

    @staticmethod
    def _criar_documento(imovel, tipo, numero, cartorio):
        return Documento.objects.create(
            imovel=imovel,
            tipo=tipo,
            numero=numero,
            data=timezone.now().date(),
            cartorio=cartorio,
        )

    def _criar_lancamento_historico(self, origem='M111'):
        lancamento = Lancamento(
            documento=self.documento_atual,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            origem=origem,
            cartorio_origem=self.cartorio_a,
            livro_origem=' 10 ',
            folha_origem=' 20 ',
        )
        Lancamento.objects.bulk_create([lancamento])
        return lancamento

    def test_fallback_textual_quando_nao_existe_estrutura(self):
        lancamento = self._criar_lancamento_historico()

        origens = LancamentoOrigemLeituraService.obter_origens(lancamento)

        self.assertEqual(len(origens), 1)
        self.assertEqual(origens[0].fonte, 'legada')
        self.assertEqual(origens[0].codigo, 'M111')
        self.assertEqual(origens[0].cartorio_id, self.cartorio_a.pk)
        self.assertEqual((origens[0].livro, origens[0].folha), ('10', '20'))

    def test_fallback_textual_sem_cartorio_origem_usa_cartorio_do_documento(self):
        """Achado da revisão automatizada do PR (Qodo, 2026-07-14): lançamento
        legado com origem textual mas sem `cartorio_origem` explícito não
        pode ficar sem cartório na leitura - mesmo fallback já usado na
        escrita (LancamentoOrigemService._buscar_dados_origem): assume o
        cartório do próprio documento do lançamento."""
        lancamento = Lancamento(
            documento=self.documento_atual,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            origem='M111',
            cartorio_origem=None,
        )
        Lancamento.objects.bulk_create([lancamento])

        origens = LancamentoOrigemLeituraService.obter_origens(lancamento)

        self.assertEqual(len(origens), 1)
        self.assertEqual(origens[0].cartorio_id, self.documento_atual.cartorio_id)

    def test_estrutura_substitui_texto_contraditorio_em_todos_consumidores(self):
        lancamento = self._criar_lancamento_historico()
        LancamentoOrigem.objects.create(
            lancamento=lancamento,
            indice_origem=0,
            tipo_documento='transcricao',
            numero='T222',
            cartorio=self.cartorio_b,
            livro='30',
            folha='40',
        )

        origens = LancamentoOrigemLeituraService.obter_origens(lancamento)
        importaveis = DuplicataVerificacaoService.calcular_documentos_importaveis(
            self.documento_atual
        )
        cadeia = DuplicataVerificacaoService.obter_cadeia_dominial_origem(
            self.documento_atual
        )
        pais = HierarquiaArvoreService._buscar_documentos_pais(
            self.documento_atual, self.imovel_atual, False
        )
        completa = CadeiaCompletaService()._expandir_todas_origens_documento(
            self.documento_atual
        )
        tronco = identificar_tronco_principal(self.imovel_atual)
        tabela = CadeiaDominialTabelaService()
        origem_mais_alta = tabela._obter_documento_origem_mais_alto(
            self.documento_atual
        )
        origens_tabela = tabela._obter_origens_documento(
            self.documento_atual, [lancamento]
        )
        origens_hierarquia = HierarquiaOrigemService.processar_origens_identificadas(
            self.imovel_atual
        )

        self.assertEqual([(origem.codigo, origem.fonte) for origem in origens], [('T222', 'estruturada')])
        for documentos in (
            importaveis,
            [item['documento'] for item in cadeia],
            pais,
            completa,
            tronco,
        ):
            self.assertIn(self.documento_b, documentos)
            self.assertNotIn(self.documento_a, documentos)
        self.assertEqual(origem_mais_alta, self.documento_b)
        self.assertEqual(origens_tabela, ['T222'])
        self.assertEqual(
            [origem['documento_id'] for origem in origens_hierarquia],
            [self.documento_b.pk],
        )
