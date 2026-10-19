"""Testes de integração local do backend real do serviço OCR (issue #259)."""

import hashlib
import io
import tempfile
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ia_ocr import estados
from ia_ocr.backends import OcrServiceBackend
from ia_ocr.models import OcrJob
from ia_ocr.tests.factories import criar_documento_digital
from ia_ocr.tests.pdf_cifrado import gerar_pdf_aes, sem_provider_aes
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
    def _corpo_erro(codigo, mensagem='falha sintética'):
        return {'ok': False, 'error': {'code': codigo, 'message': mensagem}}

    @staticmethod
    def _posts(stub):
        return [r for r in stub.recebidas if r['metodo'] == 'POST']

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
                {
                    'numero_pagina': 1,
                    'texto': textos[0],
                    'blocos': {
                        'dpi': None,
                        'width_px': None,
                        'height_px': None,
                        'blocos': [],
                    },
                },
                {
                    'numero_pagina': 2,
                    'texto': textos[1],
                    'blocos': {
                        'dpi': None,
                        'width_px': None,
                        'height_px': None,
                        'blocos': [],
                    },
                },
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

    def test_servico_failed_inference_failed_preserva_codigo_e_worker_registra_falha(self):
        pdf = self._pdf(textos=[None])
        job_direto = self._job(pdf, forcar_ocr=True)
        stub_direto = self._stub(
            [
                (
                    200,
                    {
                        'job_id': str(job_direto.job_id),
                        'status': 'failed',
                        'error': {
                            'code': 'INFERENCE_FAILED',
                            'message': 'detalhe remoto não confiável',
                        },
                    },
                    {},
                )
            ]
        )

        self._assert_codigo_backend('INFERENCE_FAILED', job_direto, stub_direto)

        job_worker = self._job_pendente(pdf)
        stub_worker = self._stub(
            [
                (
                    200,
                    {
                        'job_id': str(job_worker.job_id),
                        'status': 'failed',
                        'error': {
                            'code': 'INFERENCE_FAILED',
                            'message': 'detalhe remoto não confiável',
                        },
                    },
                    {},
                )
            ]
        )

        self._processar_no_worker(job_worker, stub_worker)

        self.assertEqual(job_worker.status, estados.FALHOU)
        self.assertEqual(job_worker.erro_codigo, 'INFERENCE_FAILED')
        self.assertEqual(
            list(
                job_worker.transicoes.values_list(
                    'de_status', 'para_status', 'motivo'
                )
            ),
            [
                (estados.PENDENTE, estados.EM_EXECUCAO, 'claim do worker'),
                (
                    estados.EM_EXECUCAO,
                    estados.FALHOU,
                    'INFERENCE_FAILED',
                ),
            ],
        )

    def test_servico_failed_com_codigo_fora_da_allowlist_vira_erro_interno(self):
        pdf = self._pdf(textos=[None])
        job = self._job(pdf, forcar_ocr=True)
        stub = self._stub(
            [
                (
                    200,
                    {
                        'job_id': str(job.job_id),
                        'status': 'failed',
                        'error': {
                            'code': 'CODIGO_REMOTO_NOVO',
                            'message': 'não deve atravessar a allowlist',
                        },
                    },
                    {},
                )
            ]
        )

        self._assert_codigo_backend('ERRO_INTERNO', job, stub)

    def test_lease_expirado_retorna_worker_timeout_sem_requisicao(self):
        pdf = self._pdf(textos=[None])
        job = self._job(pdf, forcar_ocr=True)
        OcrJob.objects.filter(pk=job.pk).update(
            lease_expira_em=timezone.now() - timedelta(seconds=1)
        )
        job.refresh_from_db()
        stub = self._stub([])

        self._assert_codigo_backend('WORKER_TIMEOUT', job, stub)

        self.assertEqual(stub.recebidas, [])

    def test_diagnostico_arquivo_vazio_retorna_empty_file_sem_requisicao(self):
        job = self._job(b'', forcar_ocr=True)
        stub = self._stub([])

        self._assert_codigo_backend('EMPTY_FILE', job, stub)

        self.assertEqual(stub.recebidas, [])

    def test_diagnostico_pdf_com_senha_retorna_encrypted_pdf_sem_requisicao(self):
        pdf = self._pdf_criptografado(senha_usuario='senha-real-do-usuario')
        job = self._job(pdf, forcar_ocr=True)
        stub = self._stub([])

        self._assert_codigo_backend('ENCRYPTED_PDF', job, stub)

        self.assertEqual(stub.recebidas, [])

    def test_diagnostico_excesso_de_paginas_retorna_too_many_pages_sem_requisicao(self):
        pdf = self._pdf(textos=[None, None, None])
        job = self._job(pdf, forcar_ocr=True)
        stub = self._stub([])

        with self.settings(OCR_MAX_PAGINAS=2):
            self._assert_codigo_backend('TOO_MANY_PAGES', job, stub)

        self.assertEqual(stub.recebidas, [])

    def test_diagnostico_excesso_de_bytes_retorna_file_too_large_sem_requisicao(self):
        pdf = self._pdf(textos=[None])
        job = self._job(pdf, forcar_ocr=True)
        stub = self._stub([])

        with self.settings(OCR_MAX_BYTES=len(pdf) - 1):
            self._assert_codigo_backend('FILE_TOO_LARGE', job, stub)

        self.assertEqual(stub.recebidas, [])

    def test_porta_fechada_retorna_service_unavailable_apos_max_tentativas(self):
        import socket
        from unittest import mock

        import requests

        pdf = self._pdf(textos=[None])
        job = self._job(pdf, forcar_ocr=True)
        reservador = socket.socket()
        reservador.bind(('127.0.0.1', 0))
        porta = reservador.getsockname()[1]
        reservador.close()
        chamadas = []
        requisicao_original = requests.Session.request

        def contar_requisicao(sessao, *args, **kwargs):
            chamadas.append((args, kwargs))
            return requisicao_original(sessao, *args, **kwargs)

        with self.settings(OCR_SERVICE_URL=f'http://127.0.0.1:{porta}'):
            with mock.patch.object(
                requests.Session, 'request', new=contar_requisicao
            ):
                from ia_ocr.backends import OcrBackendError

                with self.assertRaises(OcrBackendError) as contexto:
                    OcrServiceBackend().processar(job)

        self.assertEqual(contexto.exception.codigo, 'SERVICE_UNAVAILABLE')
        self.assertEqual(len(chamadas), 2)

    def test_retry_de_transporte_na_mesma_tentativa_preserva_job_id(self):
        pdf = self._pdf(textos=[None, None])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (None, b'', {}),
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (200, self._resultado_servico(job.job_id, sha256), {}),
            ]
        )

        self._processar(job, stub)

        envios = [r for r in stub.recebidas if r['metodo'] == 'POST']
        self.assertEqual(len(envios), 2)
        self.assertEqual(
            [envio['campos']['job_id'] for envio in envios],
            [str(job.job_id), str(job.job_id)],
        )

    def test_404_na_consulta_reenvia_com_o_mesmo_job_id_e_conclui(self):
        pdf = self._pdf(textos=[None, None])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
                (404, self._corpo_erro('JOB_NOT_FOUND'), {}),
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
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
        envios = self._posts(stub)
        self.assertEqual(len(envios), 2)
        self.assertEqual(
            [envio['campos']['job_id'] for envio in envios],
            [str(job.job_id), str(job.job_id)],
        )

    def test_404_repetido_alem_do_limite_de_reenvios_termina_job_not_found(self):
        pdf = self._pdf(textos=[None])
        job = self._job(pdf, forcar_ocr=True)
        # OCR_MAX_REENVIOS_LOST=2: envio + 2 reenvios, todos perdidos no serviço.
        fila = []
        for _ in range(3):
            fila.append(
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {})
            )
            fila.append((404, self._corpo_erro('JOB_NOT_FOUND'), {}))
        stub = self._stub(fila)

        self._assert_codigo_backend('JOB_NOT_FOUND', job, stub)

        self.assertEqual(len(self._posts(stub)), 3)

    def test_404_no_resultado_apos_succeeded_reenvia_e_conclui(self):
        pdf = self._pdf(textos=[None, None])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (404, self._corpo_erro('JOB_NOT_FOUND'), {}),
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
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
        self.assertEqual(len(self._posts(stub)), 2)

    def test_409_no_resultado_com_processing_continua_o_poll(self):
        pdf = self._pdf(textos=[None, None])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (
                    409,
                    {'job_id': str(job.job_id), 'status': 'processing'},
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

        self.assertEqual(resultado.origem, 'ocr')
        resultados = [
            r for r in stub.recebidas if r['caminho'].endswith('/result')
        ]
        self.assertEqual(len(resultados), 2)

    def test_409_no_resultado_com_failed_falha_com_codigo_do_corpo(self):
        pdf = self._pdf(textos=[None])
        job = self._job(pdf, forcar_ocr=True)
        stub = self._stub(
            [
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (
                    409,
                    {
                        'job_id': str(job.job_id),
                        'status': 'failed',
                        'error': {
                            'code': 'INFERENCE_FAILED',
                            'message': 'detalhe remoto não confiável',
                        },
                    },
                    {},
                ),
            ]
        )

        self._assert_codigo_backend('INFERENCE_FAILED', job, stub)

    def test_queue_full_ate_o_fim_do_prazo_termina_queue_full(self):
        """QUEUE_FULL que esgota o orçamento termina com o código QUEUE_FULL,
        não WORKER_TIMEOUT: a fila do serviço ficou cheia pelo prazo do job."""
        pdf = self._pdf(textos=[None])
        job = self._job(pdf, forcar_ocr=True)
        # Orçamento = lease - margem (1s) ≈ 1.5s, menor que a reserva de
        # reenvio (folga 1s + 1 página) de 2s: o primeiro 503 QUEUE_FULL
        # esgota o orçamento e vira QUEUE_FULL, não WORKER_TIMEOUT.
        OcrJob.objects.filter(pk=job.pk).update(
            lease_expira_em=timezone.now() + timedelta(seconds=2.5)
        )
        job.refresh_from_db()
        stub = self._stub(
            [(503, self._corpo_erro('QUEUE_FULL', 'fila cheia sintética'), {})]
        )

        self._assert_codigo_backend('QUEUE_FULL', job, stub)

    def test_max_pages_desconhecido_usa_o_setting(self):
        """page_count=None (PDF criptográfico inconclusivo localmente): o
        max_pages do envio é o settings.OCR_MAX_PAGINAS, não um 25 literal."""
        from unittest import mock

        from pypdf.errors import DependencyError

        pdf = self._pdf_criptografado(senha_usuario='senha-real-do-usuario')
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (200, self._resultado_servico(job.job_id, sha256), {}),
            ]
        )

        with mock.patch(
            'ia_ocr.leitor_pdf.PdfReader.decrypt',
            side_effect=DependencyError('backend criptografico ausente'),
        ):
            with self.settings(OCR_MAX_PAGINAS=17):
                self._processar(job, stub)

        envio = self._posts(stub)[0]
        self.assertEqual(envio['campos']['max_pages'], '17')

    def test_pdf_aes_sem_senha_de_usuario_chega_ao_servico(self):
        """Issue #280: PDF AES com senha de usuário vazia abre localmente e o
        job segue para o serviço (antes morria em INVALID_PDF)."""
        pdf = gerar_pdf_aes(algoritmo='AES-256', paginas=2)
        job = self._job(pdf)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (200, self._resultado_servico(job.job_id, sha256), {}),
            ]
        )

        resultado = self._processar(job, stub)

        self.assertEqual(len(self._posts(stub)), 1)
        self.assertEqual(self._posts(stub)[0]['campos']['max_pages'], '25')
        self.assertEqual(resultado.origem, 'ocr')
        self.assertEqual(resultado.page_count, 2)

    def test_pdf_aes_sem_provider_local_chega_ao_servico_com_max_pages_do_setting(
        self,
    ):
        """Sem provider AES local (cryptography ausente) a inspeção é
        inconclusiva: o job não pode morrer em INVALID_PDF antes de falar com
        o serviço, que decide. O envio usa o teto do setting."""
        pdf = gerar_pdf_aes(algoritmo='AES-256', paginas=2)
        job = self._job(pdf)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (200, self._resultado_servico(job.job_id, sha256), {}),
            ]
        )

        with sem_provider_aes(), self.settings(OCR_MAX_PAGINAS=17):
            resultado = self._processar(job, stub)

        self.assertEqual(len(self._posts(stub)), 1)
        self.assertEqual(self._posts(stub)[0]['campos']['max_pages'], '17')
        self.assertEqual(resultado.origem, 'ocr')

    def test_max_pages_conhecido_usa_min_do_teto_setting_e_page_count(self):
        pdf = self._pdf(textos=[None, None])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        for max_paginas, esperado in ((3, '3'), (120, '100')):
            with self.subTest(max_paginas=max_paginas):
                stub = self._stub(
                    [
                        (
                            202,
                            {'job_id': str(job.job_id), 'status': 'queued'},
                            {},
                        ),
                        (
                            200,
                            {
                                'job_id': str(job.job_id),
                                'status': 'succeeded',
                            },
                            {},
                        ),
                        (
                            200,
                            self._resultado_servico(job.job_id, sha256),
                            {},
                        ),
                    ]
                )

                with self.settings(OCR_MAX_PAGINAS=max_paginas):
                    self._processar(job, stub)

                envio = self._posts(stub)[0]
                self.assertEqual(envio['campos']['max_pages'], esperado)

    def test_limiar_de_texto_embutido_abaixo_de_200_le_todas_as_paginas_e_conclui(self):
        """Com limiar configurado abaixo de 200, a saída antecipada da
        extração não pode truncar a tupla de páginas (o resultado inteiro
        viraria INVALID_OCR_RESULT na finalização). A página curta no MEIO
        é o caso que truncava: o break ignorava o limiar configurado."""
        textos = ['a' * 220, 'b' * 160, 'c' * 220]
        pdf = self._pdf(textos=textos)
        job = self._job_pendente(pdf, forcar_ocr=False)
        stub = self._stub([])

        with self.settings(OCR_TEXTO_EMBUTIDO_MIN_CHARS_PAGINA=150):
            self._processar_no_worker(job, stub)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.origem, 'texto_embutido')
        self.assertEqual(job.page_count, 3)
        self.assertEqual(
            [
                pagina.texto_ocr
                for pagina in job.paginas.order_by('numero_pagina')
            ],
            textos,
        )
        self.assertEqual(stub.recebidas, [])

    def test_forcar_ocr_sobrevive_ao_retry_e_segunda_tentativa_chama_o_servico(self):
        """PDF COM camada de texto: a tentativa 1 conclui pelo atalho (zero
        HTTP); após falhou (lease perdido antes de persistir), retry() mantém
        forcar_ocr e a tentativa 2 vai ao serviço de verdade."""
        import uuid as modulo_uuid

        from ia_ocr import services

        textos = ['a' * 220, 'b' * 230]
        pdf = self._pdf(textos=textos)
        job = self._job_pendente(pdf, forcar_ocr=False)
        sha256 = hashlib.sha256(pdf).hexdigest()
        # A tentativa 2 usa uuid5(job.job_id, '2') como job_id do serviço.
        job_id_2 = str(modulo_uuid.uuid5(job.job_id, '2'))
        stub = self._stub(
            [
                (202, {'job_id': job_id_2, 'status': 'queued'}, {}),
                (200, {'job_id': job_id_2, 'status': 'succeeded'}, {}),
                (200, self._resultado_servico(job_id_2, sha256), {}),
            ]
        )

        # Tentativa 1: atalho texto_embutido — nenhuma requisição HTTP.
        with self.settings(OCR_SERVICE_URL=stub.base_url):
            claimado = services.claim_proximo_job()
            resultado = OcrServiceBackend().processar(claimado)
        self.assertEqual(resultado.origem, 'texto_embutido')
        self.assertEqual(stub.recebidas, [])

        # O worker antigo perde o lease antes de persistir: reap → falhou.
        OcrJob.objects.filter(pk=job.pk).update(
            lease_expira_em=timezone.now() - timedelta(seconds=1)
        )
        services.reap_jobs_expirados()
        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)

        # Operador força OCR de verdade e reenfileira o MESMO job.
        OcrJob.objects.filter(pk=job.pk).update(forcar_ocr=True)
        job.refresh_from_db()
        job.retry(motivo='forçar OCR no lugar do texto embutido')
        job.refresh_from_db()
        self.assertEqual(job.tentativa, 2)
        self.assertTrue(job.forcar_ocr)  # sobreviveu ao retry()

        # Tentativa 2: mesmo PDF com texto embutido, o serviço É chamado.
        self._processar_no_worker(job, stub)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.origem, 'ocr')
        envios = self._posts(stub)
        self.assertEqual(len(envios), 1)
        self.assertEqual(envios[0]['campos']['job_id'], job_id_2)

    def test_retry_da_fila_usa_uuid5_da_tentativa_e_retries_de_transporte_o_preservam(self):
        import uuid

        pdf = self._pdf(textos=[None, None])
        sha256 = hashlib.sha256(pdf).hexdigest()
        job = self._job_pendente(pdf)
        stub_tentativa_1 = self._stub(
            [
                (
                    200,
                    {
                        'job_id': str(job.job_id),
                        'status': 'failed',
                        'error': {
                            'code': 'INFERENCE_FAILED',
                            'message': 'falha sintética da tentativa 1',
                        },
                    },
                    {},
                )
            ]
        )

        self._processar_no_worker(job, stub_tentativa_1)
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.tentativa, 1)
        job.retry(motivo='nova tentativa solicitada')
        self.assertEqual(job.status, estados.PENDENTE)
        self.assertEqual(job.tentativa, 2)

        job_id_tentativa_2 = str(uuid.uuid5(job.job_id, '2'))
        stub_tentativa_2 = self._stub(
            [
                (None, b'', {}),
                (
                    200,
                    {'job_id': job_id_tentativa_2, 'status': 'succeeded'},
                    {},
                ),
                (
                    200,
                    self._resultado_servico(job_id_tentativa_2, sha256),
                    {},
                ),
            ]
        )

        self._processar_no_worker(job, stub_tentativa_2)

        envios_1 = [
            r for r in stub_tentativa_1.recebidas if r['metodo'] == 'POST'
        ]
        envios_2 = [
            r for r in stub_tentativa_2.recebidas if r['metodo'] == 'POST'
        ]
        self.assertEqual(
            [envio['campos']['job_id'] for envio in envios_1],
            [str(job.job_id)],
        )
        self.assertEqual(
            [envio['campos']['job_id'] for envio in envios_2],
            [job_id_tentativa_2, job_id_tentativa_2],
        )
        self.assertNotEqual(str(job.job_id), job_id_tentativa_2)
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.tentativa, 2)

    def test_sha256_divergente_retorna_erro_interno_e_worker_nao_persiste_paginas(self):
        pdf = self._pdf(textos=[None, None])
        job_direto = self._job(pdf, forcar_ocr=True)
        stub_direto = self._stub(
            [
                (
                    200,
                    {'job_id': str(job_direto.job_id), 'status': 'succeeded'},
                    {},
                ),
                (
                    200,
                    self._resultado_servico(job_direto.job_id, '0' * 64),
                    {},
                ),
            ]
        )

        self._assert_codigo_backend('ERRO_INTERNO', job_direto, stub_direto)

        job_worker = self._job_pendente(pdf)
        stub_worker = self._stub(
            [
                (
                    200,
                    {'job_id': str(job_worker.job_id), 'status': 'succeeded'},
                    {},
                ),
                (
                    200,
                    self._resultado_servico(job_worker.job_id, 'f' * 64),
                    {},
                ),
            ]
        )

        self._processar_no_worker(job_worker, stub_worker)

        self.assertEqual(job_worker.status, estados.FALHOU)
        self.assertEqual(job_worker.erro_codigo, 'ERRO_INTERNO')
        self.assertEqual(job_worker.paginas.count(), 0)
        self.assertEqual(
            job_worker.transicoes.filter(
                para_status=estados.CONCLUIDO
            ).count(),
            0,
        )

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

    def test_finalizar_rejeita_pagina_faltante_sem_paginas_nem_auditoria_de_sucesso(self):
        job = self._finalizar_resultado_invalido(
            [
                {
                    'numero_pagina': 1,
                    'texto': 'somente a primeira página',
                    'blocos': None,
                }
            ]
        )

        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'INVALID_OCR_RESULT')
        self.assertEqual(job.paginas.count(), 0)
        self.assertEqual(
            job.transicoes.filter(
                para_status=estados.CONCLUIDO,
                motivo='processado com sucesso',
            ).count(),
            0,
        )

    def test_finalizar_rejeita_pagina_duplicada_sem_paginas_nem_auditoria_de_sucesso(self):
        job = self._finalizar_resultado_invalido(
            [
                {
                    'numero_pagina': 1,
                    'texto': 'primeira ocorrência',
                    'blocos': None,
                },
                {
                    'numero_pagina': 1,
                    'texto': 'ocorrência duplicada',
                    'blocos': None,
                },
            ]
        )

        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'INVALID_OCR_RESULT')
        self.assertEqual(job.paginas.count(), 0)
        self.assertEqual(
            job.transicoes.filter(
                para_status=estados.CONCLUIDO,
                motivo='processado com sucesso',
            ).count(),
            0,
        )

    @override_settings(OCR_BACKEND='ia_ocr.backends.OcrServiceBackend')
    def test_worker_ponta_a_ponta_conclui_e_persiste_paginas(self):
        """Etapa 14 do plano #259: process_ocr_queue --max-jobs 1 com o
        backend REAL apontando ao stub, documento real e PDF sintético."""
        pdf = self._pdf(textos=[None, None])
        job = self._job_pendente(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (202, {'job_id': str(job.job_id), 'status': 'queued'}, {}),
                (
                    200,
                    {'job_id': str(job.job_id), 'status': 'succeeded'},
                    {},
                ),
                (200, self._resultado_servico(job.job_id, sha256), {}),
            ]
        )

        with self.settings(OCR_SERVICE_URL=stub.base_url):
            call_command('process_ocr_queue', '--max-jobs', '1', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.origem, 'ocr')
        self.assertEqual(job.sha256_pdf, sha256)
        self.assertEqual(job.page_count, 2)
        paginas = list(job.paginas.order_by('numero_pagina'))
        self.assertEqual(
            [pagina.numero_pagina for pagina in paginas], [1, 2]
        )
        self.assertIn('texto OCR sensivel pagina 1', paginas[0].texto_ocr)
        self.assertIn('texto OCR sensivel pagina 2', paginas[1].texto_ocr)
        # A geometria viaja junto no JSONField opaco de blocos.
        self.assertEqual(paginas[0].blocos['dpi'], 200)
        self.assertTrue(paginas[0].blocos['blocos'][0]['bbox'])
        self.assertEqual(
            job.transicoes.filter(
                para_status=estados.CONCLUIDO,
                motivo='processado com sucesso',
            ).count(),
            1,
        )

    @override_settings(OCR_BACKEND='ia_ocr.backends.OcrServiceBackend')
    def test_worker_falha_de_servico_deixa_job_falhou_e_nao_derruba_o_comando(self):
        pdf = self._pdf(textos=[None])
        job = self._job_pendente(pdf, forcar_ocr=True)
        stub = self._stub(
            [
                (
                    200,
                    {
                        'job_id': str(job.job_id),
                        'status': 'failed',
                        'error': {
                            'code': 'INFERENCE_FAILED',
                            'message': 'falha sintética do serviço',
                        },
                    },
                    {},
                )
            ]
        )

        # Sem exceção: o worker engole a falha do serviço e termina (exit 0).
        with self.settings(OCR_SERVICE_URL=stub.base_url):
            call_command('process_ocr_queue', '--max-jobs', '1', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'INFERENCE_FAILED')
        self.assertEqual(job.paginas.count(), 0)


class ReapFinalizarRaceTests(TransactionTestCase):
    """Interleavings determinísticos do CAS usado por reap e finalizar."""

    def setUp(self):
        self.documento = criar_documento_digital(
            nome='corrida-reap-finalizar-sintetica.pdf'
        )

    def _objetos_defasados(self):
        from ia_ocr import services

        job, _ = services.criar_job(self.documento)
        claimado = services.claim_proximo_job(timeout_s=120)
        self.assertEqual(claimado.pk, job.pk)
        OcrJob.objects.filter(pk=job.pk).update(
            lease_expira_em=timezone.now() - timedelta(seconds=1)
        )
        # Ambos são snapshots independentes do mesmo lease antes do vencedor.
        return (
            job,
            OcrJob.objects.get(pk=job.pk),
            OcrJob.objects.get(pk=job.pk),
        )

    @staticmethod
    def _resultado_completo():
        from ia_ocr.backends import ResultadoOcr

        return ResultadoOcr(
            paginas=[
                {
                    'numero_pagina': 1,
                    'texto': 'página sintética 1',
                    'blocos': None,
                },
                {
                    'numero_pagina': 2,
                    'texto': 'página sintética 2',
                    'blocos': None,
                },
            ],
            sha256_pdf='a' * 64,
            page_count=2,
            timings_ms={'total': 10},
            origem='ocr',
        )

    @staticmethod
    def _reap_com_snapshot(job):
        from ia_ocr import services

        return job.transicionar(
            estados.FALHOU,
            motivo='WORKER_TIMEOUT',
            tentativa=job.tentativa,
            erro_codigo='WORKER_TIMEOUT',
            erro_mensagem=services._mensagem_erro_segura('WORKER_TIMEOUT'),
        )

    def _assert_um_unico_desfecho(self, job):
        job.refresh_from_db()
        finais = job.transicoes.filter(
            de_status=estados.EM_EXECUCAO,
            para_status__in=[estados.FALHOU, estados.CONCLUIDO],
        )
        self.assertEqual(finais.count(), 1)
        if job.status == estados.FALHOU:
            self.assertEqual(job.erro_codigo, 'WORKER_TIMEOUT')
            self.assertEqual(job.paginas.count(), 0)
            self.assertEqual(finais.get().para_status, estados.FALHOU)
        else:
            self.assertEqual(job.status, estados.CONCLUIDO)
            self.assertEqual(
                list(job.paginas.values_list('numero_pagina', flat=True)),
                [1, 2],
            )
            self.assertEqual(finais.get().para_status, estados.CONCLUIDO)

    def test_reap_vence_e_finalizacao_com_snapshot_defasado_e_descartada(self):
        from ia_ocr import services

        job, snapshot_reap, snapshot_finalizar = self._objetos_defasados()

        self.assertTrue(self._reap_com_snapshot(snapshot_reap))
        aplicado = services.finalizar(
            snapshot_finalizar,
            self._resultado_completo(),
            tentativa=snapshot_finalizar.tentativa,
        )

        self.assertFalse(aplicado)
        self._assert_um_unico_desfecho(job)

    def test_finalizacao_vence_e_reap_com_snapshot_defasado_perde_o_cas(self):
        from ia_ocr import services
        from ia_ocr.estados import TransicaoConcorrente

        job, snapshot_reap, snapshot_finalizar = self._objetos_defasados()

        aplicado = services.finalizar(
            snapshot_finalizar,
            self._resultado_completo(),
            tentativa=snapshot_finalizar.tentativa,
        )
        with self.assertRaises(TransicaoConcorrente):
            self._reap_com_snapshot(snapshot_reap)

        self.assertTrue(aplicado)
        self._assert_um_unico_desfecho(job)
