"""Sanitização do backend OCR, migrada verbatim."""

import io
import logging
from contextlib import redirect_stderr, redirect_stdout

from django.core.management import call_command
from django.test import override_settings

from ia_ocr.services import criar_job

from .factories import criar_documento_digital
from .test_pii_base import (
    _CapturadorDeLogs,
    MARCADOR_CHAVE_TIMING,
    MARCADOR_CODIGO,
    MARCADOR_PII,
)


class SanitizacaoDePiiDoBackendTestParte:
    def setUp(self):
        self.documento = criar_documento_digital()

    def _executar_backend(self, backend):
        job, _ = criar_job(self.documento)
        capturador = _CapturadorDeLogs()
        logger_ia_ocr = logging.getLogger('ia_ocr')
        nivel_anterior = logger_ia_ocr.level
        logger_ia_ocr.setLevel(logging.DEBUG)
        logger_ia_ocr.addHandler(capturador)
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with override_settings(OCR_BACKEND=backend):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    call_command('process_ocr_queue', '--once', verbosity=3)
        finally:
            logger_ia_ocr.removeHandler(capturador)
            logger_ia_ocr.setLevel(nivel_anterior)

        job.refresh_from_db()
        formatador = logging.Formatter()
        superficies = {
            'erro_codigo': job.erro_codigo,
            'erro_mensagem': job.erro_mensagem,
            'timings_ms': repr(job.timings_ms),
            'auditoria': repr(list(job.transicoes.values_list('motivo', flat=True))),
            'caplog': '\n'.join(
                formatador.format(record) for record in capturador.records
            ),
            'caplog_warning': '\n'.join(
                formatador.format(record)
                for record in capturador.records
                if record.levelno == logging.WARNING
            ),
            'stdout': stdout.getvalue(),
            'stderr': stderr.getvalue(),
        }
        return job, superficies

    def _assert_marcadores_ausentes(self, superficies, *marcadores):
        for nome, conteudo in superficies.items():
            for marcador in marcadores:
                with self.subTest(superficie=nome, marcador=marcador):
                    self.assertNotIn(marcador, conteudo)

    def test_chave_de_timing_com_pii_e_descartada_de_banco_e_logs(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendTimingComChavePii'
        )

        self.assertEqual(job.timings_ms, {'total': 10})
        self.assertIn(
            f'job_id={job.job_id} status=concluido page_count=1 total_ms=10',
            superficies['caplog'],
        )
        self._assert_marcadores_ausentes(superficies, MARCADOR_CHAVE_TIMING)

    def test_chave_de_timing_desconhecida_e_descartada(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendTimingComChaveDesconhecida'
        )

        self.assertEqual(job.timings_ms, {})
        self._assert_marcadores_ausentes(superficies, 'stage_ms')

    def test_chaves_de_timing_do_contrato_sao_preservadas(self):
        job, _superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendTimingsContratuais'
        )

        self.assertEqual(job.timings_ms, {
            'download_and_validation': 10,
            'inference': 20,
            'total': 30,
        })

    def test_valor_textual_em_chave_de_timing_valida_e_descartado(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendTimingComValorTextual'
        )

        self.assertEqual(job.timings_ms, {})
        self._assert_marcadores_ausentes(superficies, MARCADOR_PII)

    def test_mensagem_externa_com_pii_nunca_e_persistida_ou_logada(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendMensagemComPii'
        )

        self.assertEqual(job.erro_codigo, 'SERVICE_UNAVAILABLE')
        self.assertEqual(job.erro_mensagem, 'serviço OCR indisponível')
        self.assertEqual(
            job.transicoes.filter(para_status='falhou').get().motivo,
            'SERVICE_UNAVAILABLE',
        )
        self._assert_marcadores_ausentes(superficies, MARCADOR_PII)

    def test_codigo_forjado_com_pii_vira_erro_interno_sem_vazamento(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendCodigoForjadoComPii'
        )

        self.assertEqual(job.erro_codigo, 'ERRO_INTERNO')
        self.assertEqual(
            job.erro_mensagem, 'falha interna no processamento do job'
        )
        self.assertEqual(
            job.transicoes.filter(para_status='falhou').get().motivo,
            'ERRO_INTERNO',
        )
        self._assert_marcadores_ausentes(
            superficies, MARCADOR_CODIGO, MARCADOR_PII
        )

    def test_excecao_inesperada_loga_apenas_job_id_e_tipo_em_warning(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendExcecaoInesperada'
        )

        self.assertEqual(job.erro_codigo, 'ERRO_INTERNO')
        self.assertIn(
            f'job_id={job.job_id} excecao_inesperada=RuntimeError',
            superficies['caplog_warning'].splitlines(),
        )
        self._assert_marcadores_ausentes(superficies, MARCADOR_PII)

    def test_codigo_valido_persiste_com_mensagem_local(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendCodigoContratual'
        )

        self.assertEqual(job.erro_codigo, 'TOO_MANY_PAGES')
        self.assertEqual(
            job.erro_mensagem,
            'documento excede o limite de páginas do serviço',
        )
        self.assertEqual(
            job.transicoes.filter(para_status='falhou').get().motivo,
            'TOO_MANY_PAGES',
        )
        self.assertNotIn('excecao_inesperada', superficies['caplog_warning'])
        self._assert_marcadores_ausentes(superficies, MARCADOR_PII)
