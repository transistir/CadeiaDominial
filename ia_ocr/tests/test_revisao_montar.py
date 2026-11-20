"""``_montar_dados`` (montagem a partir de job extraído) — migração
VERBATIM de ``ia_ocr/tests/test_revisao.py`` (Etapa 5, grupo 3 do
plano de 400 linhas). Corpos verbatim; só imports e a linha de
classe mudam.
"""

from datetime import date
from decimal import Decimal
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from dominial.models import Cartorios
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr

from ia_ocr.revisao import (
    DadosRevisados, RevisaoInvalidada, _montar_dados, dados_revisados,
    desnormalizar, pendencias,
)
from .factories import criar_documento_digital
from .payloads_extracao import SCHEMA_VERSION, TEXTO_PAGINA_1, payload_registro


class MontarDadosTest(TestCase):
    """``_montar_dados``: o miolo de ``dados_revisados`` sem a guarda (#341).

    O formulário de lançamento lê o estado ATUAL da revisão antes de ela
    terminar; a guarda (job revisado, extração finalizada, zero pendências)
    continua só em ``dados_revisados``.
    """

    def setUp(self):
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(), status='extraido',
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )
        payload = payload_registro(self.job.job_id)
        self.extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
        )
        CampoSugerido.objects.bulk_create(
            desnormalizar(self.extracao, payload, [self.pagina]),
        )

    def test_dados_revisados_continua_barrando_job_em_extraido(self):
        with self.assertRaises(RevisaoInvalidada):
            dados_revisados(self.extracao)

    def test_monta_a_partir_de_job_extraido_e_nao_finalizado(self):
        self.assertEqual(self.job.status, 'extraido')
        self.assertIsNone(self.extracao.finalizada_em)
        # O ato ainda tem pendências (nada foi conferido) — a montagem não
        # as exige resolvidas.
        self.assertTrue(pendencias(self.extracao))

        dados = _montar_dados(self.extracao)

        self.assertIsInstance(dados, DadosRevisados)
        (ato,) = dados.atos
        self.assertEqual(ato.chave, '/acts/0')
        self.assertEqual(ato.tipo, 'registro')
        self.assertEqual(ato.data, date(2020, 2, 15))
        self.assertEqual(ato.area, Decimal('12.50'))
        self.assertEqual(
            [(parte.papel, parte.nome) for parte in ato.partes],
            [
                ('transmitente', 'JOÃO DA SILVA'),
                ('transmitente', 'MARIA DA SILVA'),
                ('adquirente', 'PEDRO SANTOS'),
            ],
        )
        self.assertEqual(dados.documento.numero, '42.718')

    def test_le_o_valor_editado_do_estado_atual(self):
        self.extracao.campos.filter(chave='/acts/0/data').update(
            valor_final='2020-03-01', status_revisao='editado',
        )
        self.extracao.campos.filter(chave='/acts/0/partes/2').update(
            status_revisao='descartado',
        )

        (ato,) = _montar_dados(self.extracao).atos

        self.assertEqual(ato.data, date(2020, 3, 1))
        self.assertEqual(len(ato.partes), 2)

    def test_nao_escreve_nada(self):
        with CaptureQueriesContext(connection) as capturadas:
            _montar_dados(self.extracao)

        self.assertTrue(capturadas.captured_queries)
        escritas = [
            consulta['sql'] for consulta in capturadas.captured_queries
            if consulta['sql'].lstrip().upper().startswith(
                ('INSERT', 'UPDATE', 'DELETE'),
            )
        ]
        self.assertEqual(escritas, [])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')

    def test_com_a_revisao_fechada_devolve_o_mesmo_que_dados_revisados(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório sintético montar', cns='CNS-montar', estado='SP',
        )
        campos = self.extracao.campos
        campos.update(status_revisao='aceito')
        campos.filter(tipo_valor='cartorio').update(cartorio_escolhido=cartorio)
        campos.filter(tipo_valor='parte').update(criar_novo=True)
        self.job.status = 'revisado'
        self.job.save(update_fields=['status'])
        self.extracao.finalizada_em = timezone.now()
        self.extracao.save(update_fields=['finalizada_em'])
        self.assertEqual(pendencias(self.extracao), [])

        self.assertEqual(
            dados_revisados(self.extracao), _montar_dados(self.extracao),
        )
