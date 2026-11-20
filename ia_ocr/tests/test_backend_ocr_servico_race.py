"""``ReapFinalizarRaceTests`` — migração VERBATIM de
``ia_ocr/tests/test_backend_ocr_servico.py`` (Etapa 12 do plano de 400 linhas).

``TransactionTestCase`` preservado; classe inteira neste arquivo.
"""

from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone

from ia_ocr import estados
from ia_ocr.models import OcrJob
from ia_ocr.tests.factories import criar_documento_digital


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
