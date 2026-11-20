"""``ClaimProximoJobTest`` e o seletor com disputa — migração VERBATIM de
``ia_ocr/tests/test_fila.py`` (Etapa 13 do plano de 400 linhas).
"""

from datetime import timedelta
from unittest import mock

from django.db import transaction
from django.utils import timezone

from ia_ocr import estados
from ia_ocr.models import OcrJob
from ia_ocr.services import claim_proximo_job, criar_job

from .factories import criar_documento_digital, criar_usuario


class _SeletorComDisputa:
    """Delega ao queryset real; no 1º .first() outro worker "rouba" o
    candidato devolvido (muda o estado entre a seleção e o nosso CAS).

    Diferente do seletor falso antigo: filter/exclude/order_by continuam
    reais — só a disputa do primeiro candidato é injetada.
    """

    def __init__(self, queryset, roubar):
        self._queryset = queryset
        self._roubar = roubar  # lista mutável compartilhada por toda a cadeia

    def _encadear(self, queryset):
        return _SeletorComDisputa(queryset, self._roubar)

    def filter(self, *args, **kwargs):
        return self._encadear(self._queryset.filter(*args, **kwargs))

    def exclude(self, *args, **kwargs):
        return self._encadear(self._queryset.exclude(*args, **kwargs))

    def order_by(self, *args, **kwargs):
        return self._encadear(self._queryset.order_by(*args, **kwargs))

    def first(self):
        candidato = self._queryset.first()
        if candidato is not None and self._roubar:
            self._roubar.clear()
            OcrJob.objects.filter(
                pk=candidato.pk, status=estados.PENDENTE,
            ).update(
                status=estados.EM_EXECUCAO, atualizado_em=timezone.now(),
            )
        return candidato


class ClaimProximoJobTestParte:
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    def test_claim_marca_em_execucao_e_audita(self):
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job()

        self.assertIsNotNone(claimado)
        self.assertEqual(claimado.pk, job.pk)
        self.assertEqual(claimado.status, estados.EM_EXECUCAO)
        self.assertEqual(
            claimado.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 1
        )
        self.assertIsNone(claim_proximo_job())  # fila drenada

    def test_claim_com_timeout_grava_lease_expira_em_no_futuro(self):
        job, _ = criar_job(self.documento)

        claimado = claim_proximo_job(timeout_s=3600)

        self.assertIsNotNone(claimado)
        self.assertEqual(claimado.pk, job.pk)
        self.assertIsNotNone(claimado.lease_expira_em)
        self.assertGreater(claimado.lease_expira_em, timezone.now())

    def test_claim_respeita_ordem_de_criacao(self):
        antigo, _ = criar_job(self.documento)
        novo, _ = criar_job(self.documento)
        with transaction.atomic():
            OcrJob.objects.filter(pk=antigo.pk).update(
                criado_em=timezone.now() - timedelta(minutes=10)
            )
        claimado = claim_proximo_job()
        self.assertEqual(claimado.pk, antigo.pk)

    def test_disputa_real_perde_o_primeiro_candidato_e_claima_o_segundo(self):
        """CAS do candidato A falha (outro worker vence entre a seleção e o
        UPDATE) e o claim segue para o candidato B — seleção real, com
        exclude de verdade."""
        job_antigo, _ = criar_job(self.documento)
        job_novo, _ = criar_job(self.documento)
        with transaction.atomic():
            OcrJob.objects.filter(pk=job_antigo.pk).update(
                criado_em=timezone.now() - timedelta(minutes=10)
            )

        roubar = ['sim']

        def select_for_update_disputa(**kwargs):
            return _SeletorComDisputa(OcrJob.objects.all(), roubar)

        with mock.patch.object(
            OcrJob.objects, 'select_for_update',
            side_effect=select_for_update_disputa,
        ):
            claimado = claim_proximo_job()

        self.assertIsNotNone(claimado)
        self.assertEqual(claimado.pk, job_novo.pk)  # perdeu A, claimou B
        job_antigo.refresh_from_db()
        self.assertEqual(job_antigo.status, estados.EM_EXECUCAO)  # levado pelo outro
        job_novo.refresh_from_db()
        self.assertEqual(job_novo.status, estados.EM_EXECUCAO)
        self.assertEqual(
            job_novo.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 1
        )
        self.assertEqual(
            job_antigo.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 0
        )
