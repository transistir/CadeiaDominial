"""Parte 3 de 3 do corpo de ``OcrServiceBackendTests`` — migração VERBATIM
de ``ia_ocr/tests/test_backend_ocr_servico.py`` (Etapa 12 do plano de
400 linhas).

Classe SIMPLES (sem ``TestCase``); quem coleta é a fachada em
``test_backend_ocr_servico_processar.py``. Corpos verbatim.
"""

import hashlib
from datetime import timedelta

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from ia_ocr import estados
from ia_ocr.backends import OcrServiceBackend
from ia_ocr.models import OcrJob


class OcrServiceBackendTestsParte3:
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

    def test_dpi_remoto_substitui_o_solicitado_no_resultado(self):
        """O serviço devolve o DPI que USOU (300) e o envio pediu 200: o
        resultado carrega o DPI remoto, inclusive no envelope de blocos."""
        pdf = self._pdf(textos=[None])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (200, {'job_id': str(job.job_id), 'status': 'succeeded'}, {}),
                (200, self._resultado_servico(job.job_id, sha256, dpi=300), {}),
            ]
        )

        resultado = self._processar(job, stub)

        self.assertEqual(resultado.dpi, 300)
        self.assertEqual(list(resultado.paginas)[0]['blocos']['dpi'], 300)

    def test_dpi_ausente_cai_no_dpi_solicitado(self):
        """Serviço sem `dpi` no resultado (contrato antigo): o fallback é o
        DPI solicitado no envio (OCR_DPI=200), nunca None."""
        pdf = self._pdf(textos=[None])
        job = self._job(pdf, forcar_ocr=True)
        sha256 = hashlib.sha256(pdf).hexdigest()
        stub = self._stub(
            [
                (200, {'job_id': str(job.job_id), 'status': 'succeeded'}, {}),
                (200, self._resultado_servico(job.job_id, sha256), {}),
            ]
        )

        resultado = self._processar(job, stub)

        self.assertEqual(resultado.dpi, 200)
        self.assertEqual(list(resultado.paginas)[0]['blocos']['dpi'], 200)

    @override_settings(OCR_BACKEND='ia_ocr.backends.OcrServiceBackend')
    def test_worker_persiste_dpi_remoto_no_job(self):
        """Ponta a ponta: resposta com dpi=300 e OCR_DPI=200 → OcrJob.dpi
        persiste 300 (o campo já existe; extração e bbox dependem dele)."""
        pdf = self._pdf(textos=[None])
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
                (200, self._resultado_servico(job.job_id, sha256, dpi=300), {}),
            ]
        )

        with self.settings(OCR_SERVICE_URL=stub.base_url):
            call_command('process_ocr_queue', '--max-jobs', '1', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.dpi, 300)
        self.assertEqual(job.paginas.get(numero_pagina=1).blocos['dpi'], 300)

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
