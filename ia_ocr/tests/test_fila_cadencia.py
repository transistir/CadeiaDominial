"""``CadenciaReapCommandTest`` — migração VERBATIM de
``ia_ocr/tests/test_fila.py`` (Etapa 13 do plano de 400 linhas).
"""

from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from ia_ocr import estados, services
from ia_ocr.models import OcrJob
from ia_ocr.services import claim_proximo_job, criar_job

from .factories import criar_documento_digital, criar_usuario


class CadenciaReapCommandTestParte:
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendSucesso')
    def test_max_jobs_reapa_lease_expirado_sem_drenar_backlog(self):
        expirado, _ = criar_job(self.documento)
        self.assertIsNotNone(claim_proximo_job())
        OcrJob.objects.filter(pk=expirado.pk).update(
            lease_expira_em=timezone.now() - timedelta(seconds=1)
        )
        pendentes = [criar_job(self.documento)[0] for _ in range(3)]

        call_command(
            'process_ocr_queue', '--max-jobs', '2', '--interval', '0',
            '--timeout', '3600', '--no-reap-stale', verbosity=0,
        )

        expirado.refresh_from_db()
        self.assertEqual(expirado.status, estados.FALHOU)
        self.assertEqual(expirado.erro_codigo, 'WORKER_TIMEOUT')
        self.assertEqual(
            OcrJob.objects.filter(
                pk__in=[job.pk for job in pendentes], status=estados.PENDENTE,
            ).count(),
            1,
        )
        expirado.retry(motivo='reap periódico')
        self.assertEqual(expirado.status, estados.PENDENTE)

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendSucesso')
    def test_once_reapa_somente_no_inicio(self):
        criar_job(self.documento)
        criar_job(self.documento)

        with mock.patch.object(
            services, 'reap_jobs_expirados', wraps=services.reap_jobs_expirados,
        ) as reap:
            call_command('process_ocr_queue', '--once', '--interval', '0', verbosity=0)

        reap.assert_called_once()
