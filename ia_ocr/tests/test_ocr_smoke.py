"""Testes do comando de evidência ocr_smoke (#259, etapa 15)."""

import hashlib
import io
import os
import tempfile
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from pypdf import PdfWriter

from ia_ocr import estados
from ia_ocr.backends import OcrServiceBackend, ResultadoOcr
from ia_ocr.models import OcrJob
from ia_ocr.services import claim_proximo_job, criar_job, finalizar
from ia_ocr.tests.factories import criar_documento_digital
from ia_ocr.tests.stub_servico import StubServicoOcr

TEXTO_MARCADOR = 'TEXTO-OCR-NAO-PODE-VAZAR'


class OcrSmokePdfTests(TestCase):
    """Modo --pdf: cliente direto, zero banco, zero vazamento."""

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

    @staticmethod
    def _pdf(paginas=2):
        writer = PdfWriter()
        for _ in range(paginas):
            writer.add_blank_page(width=612, height=792)
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def _caminho(self, conteudo, nome='nome-ultrassecreto.pdf'):
        caminho = os.path.join(self.diretorio.name, nome)
        with open(caminho, 'wb') as arquivo:
            arquivo.write(conteudo)
        return caminho

    def _stub(self, respostas, **kwargs):
        stub = StubServicoOcr(respostas, **kwargs).iniciar()
        self.addCleanup(stub.encerrar)
        return stub

    @staticmethod
    def _resultado(sha256, *, paginas=2):
        return {
            'job_id': 'job-sintetico',
            'model': 'PaddleOCR-VL-1.6',
            'source': {
                'sha256': sha256,
                'byte_size': 123,
                'page_count': paginas,
            },
            'markdown': TEXTO_MARCADOR,
            'pages': [
                {
                    'page': numero,
                    'text': f'{TEXTO_MARCADOR} pagina {numero}',
                    'width_px': 1700 + numero,
                    'height_px': 2200 + numero,
                    'blocks': (
                        [
                            {
                                'text': 'bloco reconhecido',
                                'type': 'text',
                                'bbox': [10, 20, 30, 40],
                                'confidence': 0.98,
                            }
                        ]
                        if numero == 1
                        else []
                    ),
                }
                for numero in range(1, paginas + 1)
            ],
            'timings_ms': {'inference': 321, 'total': 456},
        }

    def _script_sucesso(self, sha256):
        return [
            (202, {'job_id': 'job-sintetico', 'status': 'queued'}, {}),
            (200, {'job_id': 'job-sintetico', 'status': 'succeeded'}, {}),
            (200, self._resultado(sha256), {}),
        ]

    def test_pdf_contra_stub_sem_escrita_no_banco_e_sem_vazamento_na_saida(self):
        pdf = self._pdf()
        caminho = self._caminho(pdf)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(self._script_sucesso(sha256))
        saida = io.StringIO()

        with self.assertNumQueries(0):
            with self.settings(OCR_SERVICE_URL=stub.base_url):
                call_command('ocr_smoke', '--pdf', caminho, stdout=saida)

        texto_saida = saida.getvalue()
        self.assertIn('job_id=', texto_saida)
        self.assertIn('status=succeeded', texto_saida)
        self.assertIn('page_count=2', texto_saida)
        self.assertIn('chars=', texto_saida)
        self.assertIn('bbox=', texto_saida)
        self.assertIn('geometria=width_px,height_px', texto_saida)
        self.assertIn('timings_ms', texto_saida)
        self.assertIn('inference=321', texto_saida)
        self.assertIn('total=456', texto_saida)
        # Nada de conteúdo do documento, nome de arquivo ou credenciais.
        self.assertNotIn(TEXTO_MARCADOR, texto_saida)
        self.assertNotIn('nome-ultrassecreto', texto_saida)
        self.assertNotIn('token-interno-secreto', texto_saida)
        self.assertNotIn('access-id-secreto', texto_saida)
        self.assertNotIn('access-secret-secreto', texto_saida)

        envios = [r for r in stub.recebidas if r['metodo'] == 'POST']
        self.assertEqual(len(envios), 1)
        self.assertEqual(envios[0]['campos']['dpi'], '200')
        self.assertRegex(envios[0]['campos']['timeout_seconds'], r'^\d+$')
        self.assertEqual(envios[0]['campos']['max_pages'], '25')

    def test_sem_diagnostico_local_com_arquivo_invalido_devolve_invalid_pdf_do_servico(self):
        caminho = self._caminho(
            b'isto definitivamente nao e um pdf', nome='lixo-nao-pdf.bin'
        )
        stub = self._stub(
            [
                (
                    400,
                    {
                        'ok': False,
                        'error': {
                            'code': 'INVALID_PDF',
                            'message': 'mensagem remota do serviço',
                        },
                    },
                    {},
                )
            ]
        )
        saida = io.StringIO()

        with self.settings(OCR_SERVICE_URL=stub.base_url):
            with self.assertRaises(CommandError) as contexto:
                call_command(
                    'ocr_smoke', '--pdf', caminho, '--sem-diagnostico-local',
                    stdout=saida,
                )

        self.assertIn('INVALID_PDF', str(contexto.exception))
        envios = [r for r in stub.recebidas if r['metodo'] == 'POST']
        self.assertEqual(len(envios), 1)  # o arquivo chegou ao serviço
        # A mensagem remota não vaza na saída — só o código estável.
        self.assertNotIn('mensagem remota', saida.getvalue())
        self.assertNotIn('mensagem remota', str(contexto.exception))

    def test_token_errado_mapeado_para_unauthorized(self):
        caminho = self._caminho(self._pdf(paginas=1))
        stub = self._stub([], token_esperado='token-correto-do-servico')
        saida = io.StringIO()

        with self.settings(
            OCR_SERVICE_URL=stub.base_url,
            OCR_INTERNAL_TOKEN='token-errado-do-cliente',
        ):
            with self.assertRaises(CommandError) as contexto:
                call_command('ocr_smoke', '--pdf', caminho, stdout=saida)

        self.assertIn('UNAUTHORIZED', str(contexto.exception))
        # O valor do token nunca aparece — nem na saída nem no erro.
        self.assertNotIn('token-errado-do-cliente', str(contexto.exception))
        self.assertNotIn('token-errado-do-cliente', saida.getvalue())

    def test_page_count_desconhecido_manda_max_pages_default_e_conclui(self):
        caminho = self._caminho(self._pdf())
        sha256 = hashlib.sha256(self._pdf()).hexdigest()
        stub = self._stub(self._script_sucesso(sha256))
        saida = io.StringIO()

        with self.settings(OCR_SERVICE_URL=stub.base_url):
            call_command(
                'ocr_smoke', '--pdf', caminho, '--sem-diagnostico-local',
                stdout=saida,
            )

        envios = [r for r in stub.recebidas if r['metodo'] == 'POST']
        self.assertEqual(envios[0]['campos']['max_pages'], '25')
        self.assertIn('status=succeeded', saida.getvalue())

    def test_page_count_conhecido_do_diagnostico_define_max_pages(self):
        caminho = self._caminho(self._pdf(paginas=30))
        sha256 = hashlib.sha256(
            self._pdf(paginas=30)
        ).hexdigest()
        stub = self._stub(self._script_sucesso(sha256))
        saida = io.StringIO()

        with self.settings(OCR_SERVICE_URL=stub.base_url, OCR_MAX_PAGINAS=40):
            call_command('ocr_smoke', '--pdf', caminho, stdout=saida)

        envios = [r for r in stub.recebidas if r['metodo'] == 'POST']
        self.assertEqual(envios[0]['campos']['max_pages'], '30')


class OcrSmokeDocumentoDigitalTests(TestCase):
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
