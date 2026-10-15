"""Testes de integração local do backend real do serviço OCR (issue #259)."""

import hashlib
import io
import tempfile
from datetime import timedelta

from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ia_ocr import estados
from ia_ocr.backends import OcrServiceBackend
from ia_ocr.models import OcrJob
from ia_ocr.tests.factories import criar_documento_digital
from ia_ocr.tests.stub_servico import StubServicoOcr


class OcrServiceBackendTests(TestCase):
    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.addCleanup(self.diretorio.cleanup)
        configuracao = self.settings(
            MEDIA_ROOT=self.diretorio.name,
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
    def _pdf(*, textos):
        writer = PdfWriter()
        for texto in textos:
            pagina = writer.add_blank_page(width=612, height=792)
            if texto is not None:
                fonte = DictionaryObject(
                    {
                        NameObject('/Type'): NameObject('/Font'),
                        NameObject('/Subtype'): NameObject('/Type1'),
                        NameObject('/BaseFont'): NameObject('/Helvetica'),
                    }
                )
                pagina[NameObject('/Resources')] = DictionaryObject(
                    {
                        NameObject('/Font'): DictionaryObject(
                            {NameObject('/F1'): fonte}
                        )
                    }
                )
                conteudo = DecodedStreamObject()
                conteudo.set_data(
                    f'BT /F1 12 Tf 72 720 Td ({texto}) Tj ET'.encode('ascii')
                )
                pagina[NameObject('/Contents')] = conteudo
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def _job(self, pdf, *, forcar_ocr=False, lease=True):
        documento = criar_documento_digital(nome='nome-ultrassecreto.pdf')
        documento.arquivo.save(
            'nome-ultrassecreto.pdf', ContentFile(pdf), save=True
        )
        return OcrJob.objects.create(
            documento_digital=documento,
            status=estados.EM_EXECUCAO,
            forcar_ocr=forcar_ocr,
            lease_expira_em=(
                timezone.now() + timedelta(seconds=120) if lease else None
            ),
        )

    def _stub(self, respostas):
        stub = StubServicoOcr(respostas).iniciar()
        self.addCleanup(stub.encerrar)
        return stub

    def _processar(self, job, stub):
        with self.settings(OCR_SERVICE_URL=stub.base_url):
            return OcrServiceBackend().processar(job)

    @staticmethod
    def _resultado_servico(job_id, sha256, *, texto='texto OCR sensivel'):
        bloco = {
            'text': 'bloco reconhecido',
            'type': 'text',
            'bbox': [10, 20, 30, 40],
            'confidence': 0.98,
        }
        return {
            'job_id': str(job_id),
            'model': 'PaddleOCR-VL-1.6',
            'source': {
                'sha256': sha256,
                'byte_size': 123,
                'page_count': 2,
            },
            'markdown': texto,
            'pages': [
                {
                    'page': 1,
                    'text': f'{texto} pagina 1',
                    'width_px': 1700,
                    'height_px': 2200,
                    'blocks': [bloco],
                },
                {
                    'page': 2,
                    'text': f'{texto} pagina 2',
                    'width_px': 1701,
                    'height_px': 2201,
                    'blocks': [],
                },
            ],
            'timings_ms': {'inference': 321, 'total': 456},
        }

    def test_ciclo_completo_retorna_paginas_geometria_metadados_sem_mudar_status(self):
        pdf = self._pdf(textos=[None, None])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
                (
                    200,
                    {
                        'job_id': str(job.job_id),
                        'status': 'processing',
                        'progress': {'pages_total': 2, 'pages_done': 1},
                    },
                    {},
                ),
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (200, self._resultado_servico(job.job_id, sha256), {}),
            ]
        )

        resultado = self._processar(job, stub)

        self.assertEqual(resultado.sha256_pdf, sha256)
        self.assertEqual(resultado.page_count, 2)
        self.assertEqual(resultado.timings_ms, {'inference': 321, 'total': 456})
        self.assertEqual(resultado.origem, 'ocr')
        paginas = list(resultado.paginas)
        self.assertEqual(
            paginas[0]['blocos'],
            {
                'dpi': 200,
                'width_px': 1700,
                'height_px': 2200,
                'blocos': [
                    {
                        'text': 'bloco reconhecido',
                        'type': 'text',
                        'bbox': [10, 20, 30, 40],
                        'confidence': 0.98,
                    }
                ],
            },
        )
        self.assertEqual(paginas[1]['numero_pagina'], 2)
        self.assertIn('pagina 2', paginas[1]['texto'])
        job.refresh_from_db()
        self.assertEqual(job.status, estados.EM_EXECUCAO)
        self.assertEqual(job.paginas.count(), 0)

    def test_progress_e_logado_sem_texto_nome_de_arquivo_ou_credenciais(self):
        pdf = self._pdf(textos=[None, None])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        texto = 'CONTEUDO-OCR-NAO-PODE-VAZAR'
        stub = self._stub(
            [
                (
                    202,
                    {
                        'job_id': str(job.job_id),
                        'status': 'processing',
                        'progress': {'pages_total': 2, 'pages_done': 1},
                    },
                    {},
                ),
                (
                    200,
                    {
                        'job_id': str(job.job_id),
                        'status': 'succeeded',
                        'progress': {'pages_total': 2, 'pages_done': 2},
                    },
                    {},
                ),
                (
                    200,
                    self._resultado_servico(job.job_id, sha256, texto=texto),
                    {},
                ),
            ]
        )

        with self.assertLogs('ia_ocr.backends', level='INFO') as capturados:
            self._processar(job, stub)

        log = '\n'.join(capturados.output)
        self.assertIn('pages_done=1', log)
        self.assertIn('pages_done=2', log)
        self.assertNotIn(texto, log)
        self.assertNotIn('nome-ultrassecreto', log)
        self.assertNotIn('token-interno-secreto', log)
        self.assertNotIn('access-id-secreto', log)
        self.assertNotIn('access-secret-secreto', log)

    def test_texto_embutido_em_todas_as_paginas_nao_faz_requisicao_http(self):
        textos = ['a' * 220, 'b' * 230]
        pdf = self._pdf(textos=textos)
        job = self._job(pdf)
        stub = self._stub([])

        resultado = self._processar(job, stub)

        self.assertEqual(resultado.origem, 'texto_embutido')
        self.assertEqual(resultado.sha256_pdf, hashlib.sha256(pdf).hexdigest())
        self.assertEqual(resultado.page_count, 2)
        self.assertEqual(resultado.timings_ms, {})
        self.assertEqual(
            list(resultado.paginas),
            [
                {'numero_pagina': 1, 'texto': textos[0], 'blocos': []},
                {'numero_pagina': 2, 'texto': textos[1], 'blocos': []},
            ],
        )
        self.assertEqual(stub.recebidas, [])

    def test_forcar_ocr_ignora_atalho_e_envia_uma_vez(self):
        pdf = self._pdf(textos=['a' * 220, 'b' * 230])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (200, self._resultado_servico(job.job_id, sha256), {}),
            ]
        )

        resultado = self._processar(job, stub)

        self.assertEqual(resultado.origem, 'ocr')
        envios = [r for r in stub.recebidas if r['metodo'] == 'POST']
        self.assertEqual(len(envios), 1)

    def test_job_antigo_sem_lease_expira_em_usa_atualizado_em_como_fallback(self):
        pdf = self._pdf(textos=['a' * 220])
        job = self._job(pdf, lease=False)
        OcrJob.objects.filter(pk=job.pk).update(atualizado_em=timezone.now())
        job.refresh_from_db()
        stub = self._stub([])

        resultado = self._processar(job, stub)

        self.assertEqual(resultado.origem, 'texto_embutido')
        self.assertEqual(resultado.page_count, 1)
        self.assertEqual(stub.recebidas, [])
