"""Parte 2 de 3 do corpo de ``OcrServiceBackendTests`` — migração VERBATIM
de ``ia_ocr/tests/test_backend_ocr_servico.py`` (Etapa 12 do plano de
400 linhas).

Classe SIMPLES (sem ``TestCase``); quem coleta é a fachada em
``test_backend_ocr_servico_processar.py``. Corpos verbatim.
"""

import hashlib
from datetime import timedelta

from django.utils import timezone

from ia_ocr import estados
from ia_ocr.backends import OcrServiceBackend
from ia_ocr.models import OcrJob
from ia_ocr.tests.pdf_cifrado import gerar_pdf_aes, sem_provider_aes


class OcrServiceBackendTestsParte2:
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
