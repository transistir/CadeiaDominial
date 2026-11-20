"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.
"""

from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import (
    RequestFactory, skipUnlessDBFeature,
)
from django.test.utils import CaptureQueriesContext
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, Lancamento,
    LancamentoOrigem, LancamentoPessoa, Pessoas,
)
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.tests.test_issue_263_concorrencia_importacao import (
    travas_executadas,
)
from ia_ocr.estados import TransicaoConcorrente
from ia_ocr.importacao import ImportacaoInvalida
from ia_ocr.models import ExtracaoSugerida, ImportacaoIA, OcrJob
from .payloads_extracao import (
    payload_registro,
)
from .test_importacao_base import ImportacaoBase, _post_cadastro_manual


class RollbackTardioTest(ImportacaoBase):
    """Cenário 6: falha na transição final desfaz tudo que foi gravado."""

    def test_transicao_concorrente_desfaz_a_importacao(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        antes = (
            Lancamento.objects.count(),
            LancamentoPessoa.objects.count(),
            Pessoas.objects.count(),
            Cartorios.objects.count(),
            ImportacaoIA.objects.count(),
        )

        with patch.object(
            OcrJob, 'transicionar',
            side_effect=TransicaoConcorrente('CAS perdido'),
        ):
            with self.assertRaises(TransicaoConcorrente):
                self._importar(extracao)

        self.assertEqual(
            (
                Lancamento.objects.count(),
                LancamentoPessoa.objects.count(),
                Pessoas.objects.count(),
                Cartorios.objects.count(),
                ImportacaoIA.objects.count(),
            ),
            antes,
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')
        self.assertFalse(
            extracao.campos.filter(status_revisao='importado').exists()
        )


class RedeDeSegurancaOrigemTest(ImportacaoBase):
    """``ValidationError`` do serviço da origem vira erro da linha, não 500."""

    def test_recusa_do_servico_da_origem_e_erro_com_mensagem_fixa(self):
        extracao = self._extracao(self._payload_origem())
        processar = LancamentoOrigemService.processar_origens_automaticas

        def recusa_na_chamada_explicita(*args, **kwargs):
            # O sinal post_save chama sem queryset e engole exceções; a
            # chamada explícita da importação (com queryset) é a que conta.
            if 'documentos_queryset' in kwargs:
                raise ValidationError('Origem T366 duplicada no cartório.')
            return processar(*args, **kwargs)

        with patch.object(
            LancamentoOrigemService, 'processar_origens_automaticas',
            side_effect=recusa_na_chamada_explicita,
        ):
            with self.assertRaises(ImportacaoInvalida) as contexto:
                self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['chave'], '/acts/0/origem/numero')
        self.assertEqual(erro['codigo'], 'valor_incompativel_destino')
        # Mensagem fixa: o texto da exceção (com o número) não vaza.
        self.assertEqual(
            erro['mensagem'],
            'O número da origem não pôde ser gravado no lançamento.',
        )
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(LancamentoOrigem.objects.count(), 0)


class TravaDocumentoTest(ImportacaoBase):
    """P1-1 (#263 rodadas 2 e 3): importação e cadastro manual disputam o Documento.

    Os dois fluxos gravam lançamento no mesmo documento: ambos EXECUTAM a
    trava do ``Documento`` dentro da transação — a importação por último na
    ordem da exclusão do PDF (``DocumentoDigital`` → job → extração →
    ``Documento``); o cadastro manual só ela, antes de gravar. A trava da
    importação é só do Documento (``of=('self',)``): o JOIN do
    ``select_related('imovel')`` travaria também o Imovel (rodada 3).
    """

    ORDEM = (DocumentoDigital, OcrJob, ExtracaoSugerida, Documento)

    def test_importacao_trava_por_ultimo_so_o_documento(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        with travas_executadas() as travas:
            self._importar(extracao)

        self.assertEqual(
            [trava for trava in travas if trava[0] in self.ORDEM],
            [
                (DocumentoDigital, ()),
                (OcrJob, ()),
                (ExtracaoSugerida, ()),
                (Documento, ('self',)),
            ],
        )

    def test_criacao_manual_trava_o_documento_na_mesma_ordem(self):
        request = RequestFactory().post(
            '/lancamento/criar/', _post_cadastro_manual(self.tipo_registro),
        )
        request.user = self.usuario
        gravados_na_trava = []

        def contar(modelo):
            if modelo is Documento:
                gravados_na_trava.append(
                    Lancamento.objects.filter(documento=self.documento).count()
                )

        with travas_executadas(contar) as travas:
            lancamento, _ = LancamentoCriacaoService.criar_lancamento_completo(
                request, self.imovel.terra_indigena_id, self.imovel,
                self.documento,
            )

        # Só a última trava da ordem, executada antes do INSERT.
        self.assertEqual(
            [trava for trava in travas if trava[0] in self.ORDEM],
            [(Documento, ())],
        )
        self.assertEqual(gravados_na_trava, [0])
        self.assertIsNotNone(lancamento)


@skipUnlessDBFeature('has_select_for_update_of')
class TravaDocumentoSqlTest(ImportacaoBase):
    """SQL real da trava (PostgreSQL; o sqlite não emite ``FOR UPDATE``)."""

    def test_sql_da_trava_cobre_so_a_tabela_do_documento(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        with CaptureQueriesContext(connection) as capturadas:
            self._importar(extracao)

        (sql,) = [
            consulta['sql'] for consulta in capturadas.captured_queries
            if 'FOR UPDATE' in consulta['sql']
            and 'FROM "dominial_documento"' in consulta['sql']
        ]
        # O select_related continua (JOIN no imóvel); a trava, não.
        self.assertIn('JOIN "dominial_imovel"', sql)
        self.assertTrue(
            sql.endswith('FOR UPDATE OF "dominial_documento"'), sql,
        )
