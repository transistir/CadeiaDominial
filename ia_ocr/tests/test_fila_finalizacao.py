"""``FinalizacaoTardiaTest`` — migração VERBATIM de
``ia_ocr/tests/test_fila.py`` (Etapa 13 do plano de 400 linhas).
"""

from datetime import timedelta

from django.utils import timezone

from ia_ocr import estados
from ia_ocr.models import OcrJob
from ia_ocr.services import (
    claim_proximo_job, criar_job, finalizar, reap_jobs_expirados,
)

from .factories import criar_documento_digital, criar_usuario
from .test_fila_base import _resultado


class FinalizacaoTardiaTestParte:
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    def test_finalizacao_do_worker_antigo_e_descartada(self):
        """claim → reap → retry → claim(2): resultado do worker antigo é
        descartado pelo filtro de TENTATIVA (o job está em_execucao na
        tentativa 2 — não é o status que salva)."""
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job()
        self.assertEqual(claimado.tentativa, 1)

        OcrJob.objects.filter(pk=job.pk).update(
            lease_expira_em=timezone.now() - timedelta(seconds=1)
        )
        reap_jobs_expirados(timeout_s=0)  # reapa o lease já expirado
        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)

        job.retry(motivo='reap manual')  # volta a pendente na tentativa 2
        novo_claim = claim_proximo_job()  # tentativa 2 assume o lease
        self.assertIsNotNone(novo_claim)
        self.assertEqual(novo_claim.tentativa, 2)

        # O worker antigo (tentativa 1) tenta finalizar tardiamente.
        with self.assertLogs('ia_ocr.services', level='WARNING') as logs:
            aplicado = finalizar(claimado, _resultado(), tentativa=1)

        self.assertFalse(aplicado)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.EM_EXECUCAO)  # lease da tentativa 2 intacto
        self.assertEqual(job.tentativa, 2)
        self.assertEqual(job.paginas.count(), 0)  # resultado descartado
        self.assertEqual(
            job.transicoes.filter(para_status=estados.CONCLUIDO).count(), 0
        )
        # Auditoria da tentativa 2 intacta: 2 claims (tentativas 1 e 2).
        self.assertEqual(
            job.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 2
        )
        # O log de descarte carrega só job_id/tentativa — sem PII.
        self.assertTrue(
            any(str(job.job_id) in mensagem for mensagem in logs.output)
        )

    def test_finalizacao_valida_aplica_resultado(self):
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job()
        aplicado = finalizar(claimado, _resultado(), tentativa=claimado.tentativa)

        self.assertTrue(aplicado)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.paginas.count(), 2)
