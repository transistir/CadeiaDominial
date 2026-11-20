"""Parte 1 de 3 do corpo de ``OcrServiceBackendTests`` — migração VERBATIM
de ``ia_ocr/tests/test_backend_ocr_servico.py`` (Etapa 12 do plano de
400 linhas).

Classe SIMPLES (sem ``TestCase``); quem coleta é a fachada em
``test_backend_ocr_servico_processar.py``. Corpos verbatim.
"""

import hashlib
from datetime import timedelta

from django.utils import timezone

from ia_ocr import estados
from ia_ocr.models import OcrJob


class OcrServiceBackendTestsParte1:
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
