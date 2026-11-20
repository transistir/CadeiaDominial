"""``ReapJobsExpiradosTest`` — migração VERBATIM de
``ia_ocr/tests/test_fila.py`` (Etapa 13 do plano de 400 linhas).
"""

from datetime import timedelta

from django.utils import timezone

from ia_ocr import estados
from ia_ocr.models import OcrJob
from ia_ocr.services import claim_proximo_job, criar_job, reap_jobs_expirados

from .factories import criar_documento_digital, criar_usuario


class ReapJobsExpiradosTestParte:
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    def _claimar(self):
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job()
        self.assertIsNotNone(claimado)
        return claimado

    def test_em_execucao_recente_nao_e_reapado(self):
        job = self._claimar()
        reapados = reap_jobs_expirados(timeout_s=3600)
        self.assertEqual(reapados, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.EM_EXECUCAO)

    def test_em_execucao_expirado_vira_falhou_worker_timeout(self):
        job = self._claimar()
        # Expira o prazo explícito persistido pelo claim.
        OcrJob.objects.filter(pk=job.pk).update(
            lease_expira_em=timezone.now() - timedelta(seconds=1)
        )
        reapados = reap_jobs_expirados(timeout_s=3600)

        self.assertEqual(reapados, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'WORKER_TIMEOUT')
        transicao = job.transicoes.latest('criado_em')
        self.assertEqual(
            (transicao.de_status, transicao.para_status),
            (estados.EM_EXECUCAO, estados.FALHOU),
        )

    def test_borda_do_timeout_de_um_segundo(self):
        """Lease com 1 s restante não é reapado; vencido há 1 s, é."""
        dentro = self._claimar()
        fora, _ = criar_job(self.documento)
        self.assertIsNotNone(claim_proximo_job())  # claima `fora`

        agora = timezone.now()
        OcrJob.objects.filter(pk=dentro.pk).update(
            lease_expira_em=agora + timedelta(seconds=1)
        )
        OcrJob.objects.filter(pk=fora.pk).update(
            lease_expira_em=agora - timedelta(seconds=1)
        )

        reapados = reap_jobs_expirados(timeout_s=3600)

        self.assertEqual(reapados, 1)
        dentro.refresh_from_db()
        fora.refresh_from_db()
        self.assertEqual(dentro.status, estados.EM_EXECUCAO)
        self.assertEqual(fora.status, estados.FALHOU)
        self.assertEqual(fora.erro_codigo, 'WORKER_TIMEOUT')

    def test_job_legado_sem_lease_usa_atualizado_em_como_fallback(self):
        job = self._claimar()
        OcrJob.objects.filter(pk=job.pk).update(
            lease_expira_em=None,
            atualizado_em=timezone.now() - timedelta(seconds=7200),
        )

        reapados = reap_jobs_expirados(timeout_s=3600)

        self.assertEqual(reapados, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'WORKER_TIMEOUT')
        transicao = job.transicoes.latest('criado_em')
        self.assertEqual(
            (transicao.de_status, transicao.para_status),
            (estados.EM_EXECUCAO, estados.FALHOU),
        )

    def test_lease_longo_nao_e_reapado_por_worker_com_timeout_curto(self):
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job(timeout_s=7200)
        self.assertIsNotNone(claimado)
        OcrJob.objects.filter(pk=job.pk).update(
            atualizado_em=timezone.now() - timedelta(seconds=3600)
        )

        reapados = reap_jobs_expirados(timeout_s=1)

        self.assertEqual(reapados, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.EM_EXECUCAO)

    def test_lease_vencido_e_reapado_mesmo_com_timeout_longo(self):
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job(timeout_s=1)
        self.assertIsNotNone(claimado)
        OcrJob.objects.filter(pk=job.pk).update(
            lease_expira_em=timezone.now() - timedelta(seconds=1),
            atualizado_em=timezone.now(),
        )

        reapados = reap_jobs_expirados(timeout_s=7200)

        self.assertEqual(reapados, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'WORKER_TIMEOUT')
        self.assertEqual(
            job.transicoes.filter(
                de_status=estados.EM_EXECUCAO,
                para_status=estados.FALHOU,
                motivo='WORKER_TIMEOUT',
            ).count(),
            1,
        )
