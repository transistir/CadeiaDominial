"""``ValidacaoResultadoOcrTest`` — migração VERBATIM de
``ia_ocr/tests/test_fila.py`` (Etapa 13 do plano de 400 linhas).
"""


from ia_ocr import estados
from ia_ocr.backends import ResultadoOcr
from ia_ocr.services import claim_proximo_job, criar_job, finalizar

from .factories import criar_documento_digital, criar_usuario


class ValidacaoResultadoOcrTestParte:
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    def _finalizar(self, paginas, page_count):
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job()
        resultado = ResultadoOcr(
            paginas=paginas,
            sha256_pdf='b' * 64,
            page_count=page_count,
            timings_ms={'total': 10},
            origem='ocr',
        )
        finalizar(claimado, resultado, tentativa=claimado.tentativa)
        job.refresh_from_db()
        return job

    def test_paginas_faltantes_falham_sem_persistir_e_aceitam_retry(self):
        job = self._finalizar(
            [{'numero_pagina': 1, 'texto': 'página 1', 'blocos': None}],
            page_count=2,
        )

        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'INVALID_OCR_RESULT')
        self.assertEqual(job.paginas.count(), 0)
        self.assertEqual(
            job.transicoes.filter(para_status=estados.CONCLUIDO).count(), 0
        )
        job.retry(motivo='resultado contratualmente inválido')
        self.assertEqual(job.status, estados.PENDENTE)

    def test_page_count_invalido_falha_sem_persistir_e_aceita_retry(self):
        for page_count in (0, '2', True):
            with self.subTest(page_count=page_count):
                job = self._finalizar(
                    [{'numero_pagina': 1, 'texto': 'página 1', 'blocos': None}],
                    page_count=page_count,
                )

                self.assertEqual(job.status, estados.FALHOU)
                self.assertEqual(job.erro_codigo, 'INVALID_OCR_RESULT')
                self.assertEqual(job.paginas.count(), 0)
                self.assertEqual(
                    job.transicoes.filter(para_status=estados.CONCLUIDO).count(),
                    0,
                )
                job.retry(motivo='page_count contratualmente inválido')
                self.assertEqual(job.status, estados.PENDENTE)
                job.delete()

    def test_resultado_sem_paginas_falha(self):
        job = self._finalizar([], page_count=2)

        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'INVALID_OCR_RESULT')
        self.assertEqual(job.paginas.count(), 0)

    def test_paginas_duplicadas_falham_sem_persistir(self):
        job = self._finalizar(
            [
                {'numero_pagina': 1, 'texto': 'página 1', 'blocos': None},
                {'numero_pagina': 1, 'texto': 'página 1 repetida', 'blocos': None},
            ],
            page_count=2,
        )

        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'INVALID_OCR_RESULT')
        self.assertEqual(job.paginas.count(), 0)

    def test_pagina_fora_da_faixa_falha_sem_persistir(self):
        job = self._finalizar(
            [{'numero_pagina': 2, 'texto': 'página 2', 'blocos': None}],
            page_count=1,
        )

        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'INVALID_OCR_RESULT')
        self.assertEqual(job.paginas.count(), 0)

    def test_paginas_em_gerador_sao_persistidas(self):
        paginas = (
            {'numero_pagina': numero, 'texto': f'página {numero}', 'blocos': None}
            for numero in (1, 2)
        )

        job = self._finalizar(paginas, page_count=2)

        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(
            list(job.paginas.values_list('numero_pagina', flat=True)), [1, 2]
        )

    def test_resultado_completo_conclui(self):
        job = self._finalizar(
            [
                {'numero_pagina': 1, 'texto': 'página 1', 'blocos': None},
                {'numero_pagina': 2, 'texto': 'página 2', 'blocos': None},
            ],
            page_count=2,
        )

        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.page_count, 2)
        self.assertEqual(list(job.paginas.values_list('numero_pagina', flat=True)), [1, 2])
