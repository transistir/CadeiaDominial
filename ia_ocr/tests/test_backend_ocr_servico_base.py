"""Infraestrutura dos testes de integração do backend real do serviço OCR
(issue #259) — migração VERBATIM de ``ia_ocr/tests/test_backend_ocr_servico.py``
(Etapa 12 do plano de 400 linhas).

Nenhum teste aqui: ``OcrServiceBackendBase`` (setUp + helpers) é herdada
pela fachada em ``test_backend_ocr_servico_processar.py``.
"""

import hashlib
import io
import tempfile
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ia_ocr import estados
from ia_ocr.backends import OcrServiceBackend
from ia_ocr.models import OcrJob
from ia_ocr.tests.factories import criar_documento_digital
from ia_ocr.tests.stub_servico import StubServicoOcr


class OcrServiceBackendBase:
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
    def _corpo_erro(codigo, mensagem='falha sintética'):
        return {'ok': False, 'error': {'code': codigo, 'message': mensagem}}

    @staticmethod
    def _posts(stub):
        return [r for r in stub.recebidas if r['metodo'] == 'POST']

    @staticmethod
    def _resultado_servico(job_id, sha256, *, texto='texto OCR sensivel', dpi=None):
        bloco = {
            'text': 'bloco reconhecido',
            'type': 'text',
            'bbox': [10, 20, 30, 40],
            'confidence': 0.98,
        }
        resultado = {
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
        if dpi is not None:
            resultado['dpi'] = dpi
        return resultado

    @staticmethod
    def _pdf_criptografado(*, senha_usuario):
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.encrypt(
            user_password=senha_usuario,
            owner_password='senha-do-dono',
            algorithm='RC4-128',
        )
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def _job_pendente(self, pdf, *, forcar_ocr=True):
        job = self._job(pdf, forcar_ocr=forcar_ocr)
        OcrJob.objects.filter(pk=job.pk).update(
            status=estados.PENDENTE,
            lease_expira_em=None,
        )
        job.refresh_from_db()
        return job

    def _processar_no_worker(self, job, stub):
        from ia_ocr.management.commands.process_ocr_queue import Command

        with self.settings(OCR_SERVICE_URL=stub.base_url):
            processado = Command()._processar_um_job(OcrServiceBackend())
        self.assertTrue(processado)
        job.refresh_from_db()

    def _assert_codigo_backend(self, codigo, job, stub):
        from ia_ocr.backends import OcrBackendError

        with self.assertRaises(OcrBackendError) as contexto:
            self._processar(job, stub)
        self.assertEqual(contexto.exception.codigo, codigo)

    def _finalizar_resultado_invalido(self, paginas):
        from ia_ocr import services
        from ia_ocr.backends import ResultadoOcr

        pdf = self._pdf(textos=[None, None])
        job = self._job_pendente(pdf)
        claimado = services.claim_proximo_job()
        self.assertEqual(claimado.pk, job.pk)
        aplicado = services.finalizar(
            claimado,
            ResultadoOcr(
                paginas=paginas,
                sha256_pdf=hashlib.sha256(pdf).hexdigest(),
                page_count=2,
                timings_ms={'total': 10},
                origem='ocr',
            ),
            tentativa=claimado.tentativa,
        )
        self.assertTrue(aplicado)
        job.refresh_from_db()
        return job
