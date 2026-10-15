"""Concorrência real de fila: 2 workers, N jobs, nenhum processado 2×.

`TransactionTestCase` + threads com conexões próprias. Exige
`select_for_update ... skip_locked` real: na suíte sqlite esta classe é PULADA
(comportamento esperado); rodar contra um Postgres local para valer.
"""

import threading

from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from ia_ocr import estados, services
from ia_ocr.backends import ResultadoOcr
from ia_ocr.models import OcrJob

from .factories import criar_documento_digital


def _resultado():
    return ResultadoOcr(
        paginas=[{'numero_pagina': 1, 'texto': 'texto sintético', 'blocos': None}],
        sha256_pdf='b' * 64,
        page_count=1,
        timings_ms={'total': 10},
        origem='ocr',
    )


@skipUnlessDBFeature('has_select_for_update_skip_locked')
class DoisWorkersNaoPegamOMesmoJobTest(TransactionTestCase):
    N_JOBS = 8

    def test_nenhum_job_claimado_duplamente(self):
        for _ in range(self.N_JOBS):
            OcrJob.objects.create(documento_digital=criar_documento_digital())

        claimados = []
        erros = []
        trava = threading.Lock()
        barreira = threading.Barrier(2)

        def worker(indice):
            close_old_connections()
            try:
                barreira.wait(timeout=10)
                while True:
                    job = services.claim_proximo_job()
                    if job is None:
                        return
                    with trava:
                        claimados.append(job.pk)
                    services.finalizar(job, _resultado(), job.tentativa)
            except Exception as exc:
                # Exceção engolida na thread esconderia uma quebra real do
                # claim/finalização: o teste tem de falhar por ela também.
                with trava:
                    erros.append(f'worker {indice}: {type(exc).__name__}: {exc}')
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=worker, args=(indice,)) for indice in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(erros, [])
        for thread in threads:
            self.assertFalse(thread.is_alive(), 'worker não terminou em 30 s')
        self.assertEqual(len(claimados), self.N_JOBS)
        self.assertEqual(len(set(claimados)), self.N_JOBS)  # nenhum 2×

        for job in OcrJob.objects.all():
            self.assertEqual(job.status, estados.CONCLUIDO, job.job_id)
            self.assertEqual(
                job.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 1
            )
            self.assertEqual(
                job.transicoes.filter(para_status=estados.CONCLUIDO).count(), 1
            )


@skipUnlessDBFeature('has_select_for_update_skip_locked')
class ReprocessarConcorrenteTest(TransactionTestCase):
    """Dois cliques simultâneos de reprocessar criam exatamente UM job."""

    def test_dois_cliques_simultaneos_criam_exatamente_um_job(self):
        documento = criar_documento_digital()
        antigo = OcrJob.objects.create(documento_digital=documento)
        antigo.transicionar(estados.EM_EXECUCAO)
        antigo.transicionar(estados.CONCLUIDO)

        resultados = []
        erros = []
        trava = threading.Lock()
        barreira = threading.Barrier(2)

        def clicar(indice):
            close_old_connections()
            try:
                barreira.wait(timeout=10)
                job, criado = services.reprocessar(antigo)
                with trava:
                    resultados.append((indice, job.pk, criado))
            except Exception as exc:
                with trava:
                    erros.append(f'clique {indice}: {type(exc).__name__}: {exc}')
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=clicar, args=(indice,))
            for indice in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(erros, [])
        for thread in threads:
            self.assertFalse(thread.is_alive(), 'clique não terminou em 30 s')

        # Exatamente um vencedor (criou) e um recusado pela guarda...
        self.assertEqual(
            sorted(criado for _, _, criado in resultados), [False, True]
        )
        # ...ambos apontando para o MESMO job novo.
        self.assertEqual(len({job_pk for _, job_pk, _ in resultados}), 1)
        # Um único job novo além do antigo, pendente, no mesmo documento.
        self.assertEqual(
            OcrJob.objects.filter(documento_digital=documento).count(), 2
        )
        novo = OcrJob.objects.exclude(pk=antigo.pk).get()
        self.assertEqual(novo.status, estados.PENDENTE)
        self.assertTrue(novo.forcar_ocr)
        antigo.refresh_from_db()
        self.assertEqual(antigo.status, estados.CONCLUIDO)
