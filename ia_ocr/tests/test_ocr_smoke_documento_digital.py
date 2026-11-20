"""Modo --documento-digital do comando ocr_smoke, migrado verbatim."""

import hashlib
import io
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from pypdf import PdfWriter

from ia_ocr import estados
from ia_ocr.backends import OcrServiceBackend, ResultadoOcr
from ia_ocr.management.commands.ocr_smoke import Command
from ia_ocr.models import OcrJob
from ia_ocr.services import claim_proximo_job, criar_job, finalizar
from ia_ocr.tests.factories import criar_documento_digital
from ia_ocr.tests.stub_servico import StubServicoOcr

from .test_ocr_smoke_base import TEXTO_MARCADOR


class OcrSmokeDocumentoDigitalTestsParte:
    """Modo --documento-digital: recusa sem --confirmar, aplicação com ele."""

    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.addCleanup(self.diretorio.cleanup)
        configuracao = self.settings(
            MEDIA_ROOT=self.diretorio.name,
            OCR_SERVICE_URL='',
            OCR_INTERNAL_TOKEN='token-interno-secreto',
            OCR_ACCESS_CLIENT_ID='access-id-secreto',
            OCR_ACCESS_CLIENT_SECRET='access-secret-secreto',
            OCR_HTTP_TIMEOUT_SECONDS=2,
            OCR_HTTP_MAX_TENTATIVAS=2,
            OCR_HTTP_BACKOFF_BASE_SECONDS=0,
            OCR_BACKOFF_MAX_SECONDS=0,
            OCR_POLL_INTERVAL_SECONDS=0,
            OCR_FOLGA_FILA_SECONDS=1,
            OCR_MARGEM_PERSISTENCIA_SECONDS=1,
            OCR_SEGUNDOS_POR_PAGINA=1,
            OCR_MAX_PAGINAS=25,
            OCR_MAX_BYTES=52_428_800,
            OCR_MAX_REENVIOS_LOST=2,
            OCR_TEXTO_EMBUTIDO_MIN_CHARS_PAGINA=200,
            OCR_DPI=200,
            OCR_JOB_TIMEOUT_SECONDS=120,
        )
        configuracao.enable()
        self.addCleanup(configuracao.disable)

    def _stub(self, respostas, **kwargs):
        stub = StubServicoOcr(respostas, **kwargs).iniciar()
        self.addCleanup(stub.encerrar)
        return stub

    def test_sem_confirmar_recusa_antes_de_tocar_no_banco(self):
        documento = criar_documento_digital()
        saida = io.StringIO()

        with self.assertNumQueries(0):
            with self.assertRaises(CommandError) as contexto:
                call_command(
                    'ocr_smoke', '--documento-digital', str(documento.pk),
                    stdout=saida,
                )

        mensagem = str(contexto.exception)
        self.assertIn('banco', mensagem)
        self.assertIn('TESTES', mensagem)
        self.assertIn('--confirmar', mensagem)
        self.assertEqual(OcrJob.objects.count(), 0)

    def test_job_em_execucao_com_lease_vencido_e_reapado_antes_do_claim(self):
        documento = criar_documento_digital()
        job, _ = criar_job(documento)
        claimado = claim_proximo_job()
        OcrJob.objects.filter(pk=claimado.pk).update(
            lease_expira_em=timezone.now() - timedelta(seconds=1)
        )

        smoke = Command()._garantir_job_claimado(documento)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'WORKER_TIMEOUT')
        self.assertNotEqual(smoke.pk, job.pk)
        self.assertEqual(smoke.status, estados.EM_EXECUCAO)

    def test_com_confirmar_processa_com_backend_real_e_finaliza_o_job(self):
        buffer = io.BytesIO()
        escritor = PdfWriter()
        for _ in range(2):
            escritor.add_blank_page(width=612, height=792)
        escritor.write(buffer)
        pdf = buffer.getvalue()
        documento = criar_documento_digital(nome='documento-smoke.pdf')
        documento.arquivo.save(
            'documento-smoke.pdf', ContentFile(pdf), save=True
        )
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (202, {'job_id': 'job-sintetico', 'status': 'queued'}, {}),
                (200, {'job_id': 'job-sintetico', 'status': 'succeeded'}, {}),
                (
                    200,
                    {
                        'job_id': 'job-sintetico',
                        'model': 'PaddleOCR-VL-1.6',
                        'source': {
                            'sha256': sha256,
                            'byte_size': len(pdf),
                            'page_count': 2,
                        },
                        'markdown': TEXTO_MARCADOR,
                        'pages': [
                            {
                                'page': numero,
                                'text': f'{TEXTO_MARCADOR} pagina {numero}',
                                'width_px': 1700,
                                'height_px': 2200,
                                'blocks': [],
                            }
                            for numero in (1, 2)
                        ],
                        'timings_ms': {'total': 456},
                    },
                    {},
                ),
            ]
        )
        saida = io.StringIO()

        with self.settings(OCR_SERVICE_URL=stub.base_url):
            call_command(
                'ocr_smoke', '--documento-digital', str(documento.pk),
                '--confirmar', stdout=saida,
            )

        job = OcrJob.objects.get(documento_digital=documento)
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertTrue(job.forcar_ocr)
        self.assertEqual(job.page_count, 2)
        self.assertEqual(job.paginas.count(), 2)
        self.assertEqual(
            list(job.paginas.values_list('numero_pagina', flat=True)), [1, 2]
        )
        texto_saida = saida.getvalue()
        self.assertIn('status=concluido', texto_saida)
        self.assertIn('page_count=2', texto_saida)
        self.assertIn('paginas_persistidas=2', texto_saida)
        self.assertNotIn(TEXTO_MARCADOR, texto_saida)
        self.assertNotIn('documento-smoke', texto_saida)

    def test_worker_com_lease_ativo_faz_o_smoke_recusar_e_preserva_o_resultado_do_worker(self):
        documento = criar_documento_digital()
        job, _ = criar_job(documento)
        claimado = claim_proximo_job()
        self.assertEqual(claimado.pk, job.pk)
        tentativa = claimado.tentativa
        lease_antes = claimado.lease_expira_em
        saida = io.StringIO()

        with patch.object(OcrServiceBackend, 'processar') as processar:
            with self.assertRaises(CommandError) as contexto:
                call_command(
                    'ocr_smoke', '--documento-digital', str(documento.pk),
                    '--confirmar', stdout=saida,
                )

        processar.assert_not_called()
        self.assertIn('worker', str(contexto.exception))
        job.refresh_from_db()
        self.assertEqual(job.status, estados.EM_EXECUCAO)
        self.assertEqual(job.tentativa, tentativa)
        self.assertEqual(job.lease_expira_em, lease_antes)

        resultado_worker = ResultadoOcr(
            paginas=[
                {'numero_pagina': 1, 'texto': 'texto do worker', 'blocos': None},
                {'numero_pagina': 2, 'texto': 'texto do worker', 'blocos': None},
            ],
            sha256_pdf='b' * 64,
            page_count=2,
            timings_ms={'total': 10},
            origem='ocr',
        )
        self.assertTrue(finalizar(claimado, resultado_worker, tentativa))
        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.sha256_pdf, 'b' * 64)
