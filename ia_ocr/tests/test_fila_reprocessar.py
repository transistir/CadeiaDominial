"""``ReprocessarTest`` — migração VERBATIM de ``ia_ocr/tests/test_fila.py``
(Etapa 13 do plano de 400 linhas).
"""

from django.utils import timezone

from ia_ocr import estados, services
from ia_ocr.models import OcrJob
from ia_ocr.services import claim_proximo_job, criar_job, finalizar

from .factories import criar_documento_digital, criar_usuario
from .test_fila_base import _resultado


class ReprocessarTestParte:
    """reprocessar: job novo com forcar_ocr, histórico intacto, guarda de vigente."""

    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)
        self.job, _ = criar_job(self.documento)

    def _concluir_e_confirmar(self):
        """Leva o job até texto_confirmado, com páginas confirmadas."""
        claimado = claim_proximo_job()
        self.assertIsNotNone(claimado)
        finalizar(claimado, _resultado(), tentativa=claimado.tentativa)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        for pagina in self.job.paginas.all():
            pagina.confirmado_por = self.usuario
            pagina.confirmado_em = timezone.now()
            pagina.texto_confirmado = pagina.texto_ocr
            pagina.save()
        self.job.transicionar(estados.TEXTO_CONFIRMADO, usuario=self.usuario)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)

    def test_cria_job_novo_com_uuid_diferente_e_deixa_o_antigo_intacto(self):
        self._concluir_e_confirmar()
        pks_paginas_antes = list(
            self.job.paginas.values_list('pk', flat=True)
        )
        pks_transicoes_antes = list(
            self.job.transicoes.values_list('pk', flat=True)
        )

        novo, criado = services.reprocessar(self.job, usuario=self.usuario)

        self.assertTrue(criado)
        self.assertNotEqual(novo.job_id, self.job.job_id)  # UUID novo
        self.assertEqual(novo.documento_digital_id, self.documento.pk)
        self.assertEqual(novo.status, estados.PENDENTE)
        self.assertTrue(novo.forcar_ocr)
        self.assertEqual(novo.origem, 'ocr')
        self.assertEqual(novo.criado_por, self.usuario)
        # Job antigo intacto: mesmo status, mesmas páginas confirmadas
        # (mesmos pks) e mesma auditoria — nada migrou para o novo.
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)
        self.assertEqual(
            list(self.job.paginas.values_list('pk', flat=True)),
            pks_paginas_antes,
        )
        pagina = self.job.paginas.get(numero_pagina=1)
        self.assertIsNotNone(pagina.confirmado_em)
        self.assertIsNotNone(pagina.confirmado_por)
        self.assertEqual(pagina.texto_confirmado, pagina.texto_ocr)
        self.assertEqual(
            list(self.job.transicoes.values_list('pk', flat=True)),
            pks_transicoes_antes,
        )
        self.assertEqual(novo.paginas.count(), 0)
        self.assertEqual(novo.transicoes.count(), 0)

    def test_com_job_vigente_devolve_o_vigente_e_nao_cria_segundo(self):
        self._concluir_e_confirmar()
        for status_desejado in (estados.PENDENTE, estados.EM_EXECUCAO):
            with self.subTest(status_desejado=status_desejado):
                vigente, _ = criar_job(self.documento)
                if status_desejado == estados.EM_EXECUCAO:
                    vigente.transicionar(estados.EM_EXECUCAO)
                total_antes = OcrJob.objects.count()

                devolvido, criado = services.reprocessar(
                    self.job, usuario=self.usuario
                )

                self.assertFalse(criado)
                self.assertEqual(devolvido.pk, vigente.pk)
                self.assertEqual(OcrJob.objects.count(), total_antes)
                vigente.delete()

    def test_job_de_origem_nao_terminal_recusa_sem_criar_job_reivindicavel(self):
        for status_desejado in (estados.PENDENTE, estados.EM_EXECUCAO):
            with self.subTest(status_desejado=status_desejado):
                origem, _ = criar_job(
                    criar_documento_digital(upload_por=self.usuario)
                )
                if status_desejado == estados.EM_EXECUCAO:
                    origem.transicionar(estados.EM_EXECUCAO)
                total_antes = OcrJob.objects.count()

                with self.assertRaises(services.JobEmExecucao) as contexto:
                    services.reprocessar(origem, usuario=self.usuario)

                self.assertEqual(contexto.exception.codigo, 'JOB_EM_EXECUCAO')
                self.assertEqual(OcrJob.objects.count(), total_antes)
                self.assertFalse(
                    OcrJob.objects.filter(
                        documento_digital_id=origem.documento_digital_id
                    ).exclude(pk=origem.pk).exists()
                )
