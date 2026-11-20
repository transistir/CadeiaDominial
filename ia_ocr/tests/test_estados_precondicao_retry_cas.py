"""Pré-condição de extração, retry e CAS, migrados verbatim."""

from datetime import timedelta

from django.utils import timezone

from ia_ocr import estados
from ia_ocr.estados import TransicaoConcorrente, TransicaoInvalida
from ia_ocr.models import OcrJob, PaginaOcr
from ia_ocr.services import claim_proximo_job, criar_job, reap_jobs_expirados

from .factories import criar_documento_digital, criar_usuario

class PreCondicaoDeExtracaoTestParte:
    """texto_confirmado → extraido exige uma ExtracaoSugerida no job."""

    def setUp(self):
        self.usuario = criar_usuario()
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(),
        )
        self.job.transicionar(estados.EM_EXECUCAO)
        self.job.transicionar(estados.CONCLUIDO)
        PaginaOcr.objects.create(
            ocr_job=self.job,
            numero_pagina=1,
            texto_ocr='texto sintético',
            confirmado_por=self.usuario,
            confirmado_em=timezone.now(),
        )
        self.job.transicionar(estados.TEXTO_CONFIRMADO)

    def test_extraido_sem_extracao_recusado(self):
        with self.assertRaises(TransicaoInvalida) as contexto:
            self.job.transicionar(estados.EXTRAIDO)
        self.assertEqual(contexto.exception.code, 'sem_extracao')
        # Nada gravado: status volta e não há auditoria da transição.
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)
        self.assertEqual(
            self.job.transicoes.filter(para_status=estados.EXTRAIDO).count(),
            0,
        )


class RetryTestParte:
    def setUp(self):
        self.usuario = criar_usuario()
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(),
        )
        self.job.transicionar(estados.EM_EXECUCAO)
        self.job.transicionar(
            estados.FALHOU,
            erro_codigo='SERVICO_INDISPONIVEL',
            erro_mensagem='gateway respondeu 503',
        )

    def test_retry_volta_para_pendente_e_incrementa_tentativa(self):
        PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr='texto sintético'
        )
        self.job.retry(usuario=self.usuario, motivo='nova tentativa manual')

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.PENDENTE)
        self.assertEqual(self.job.tentativa, 2)
        self.assertEqual(self.job.erro_codigo, '')
        self.assertEqual(self.job.erro_mensagem, '')
        # Páginas anteriores são preservadas.
        self.assertEqual(self.job.paginas.count(), 1)
        # Auditoria da transição falhou → pendente.
        ultima = self.job.transicoes.latest('criado_em')
        self.assertEqual(
            (ultima.de_status, ultima.para_status),
            (estados.FALHOU, estados.PENDENTE),
        )
        self.assertEqual(ultima.usuario, self.usuario)
        self.assertEqual(ultima.motivo, 'nova tentativa manual')

    def test_retry_somente_de_falhou(self):
        self.job.retry()
        self.job.refresh_from_db()
        with self.assertRaises(TransicaoInvalida):
            self.job.retry()  # agora está pendente
        self.assertEqual(self.job.tentativa, 2)

    def test_retry_com_estado_mudado_embaixo_levanta_concorrente(self):
        job_stale = OcrJob.objects.get(pk=self.job.pk)
        self.job.retry()  # consome a transição
        with self.assertRaises(TransicaoConcorrente):
            job_stale.retry()
        self.job.refresh_from_db()
        self.assertEqual(self.job.tentativa, 2)  # incrementado uma única vez

    def test_retry_recusado_com_outro_job_em_execucao_do_documento(self):
        vizinho = OcrJob.objects.create(
            documento_digital_id=self.job.documento_digital_id
        )
        vizinho.transicionar(estados.EM_EXECUCAO)
        with self.assertRaises(TransicaoInvalida):
            self.job.retry(usuario=self.usuario, motivo='reprocessar o antigo')

        # Nada mudou: CAS/tentativa preservados e sem auditoria nova.
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.FALHOU)
        self.assertEqual(self.job.tentativa, 1)
        self.assertEqual(self.job.erro_codigo, 'SERVICO_INDISPONIVEL')
        self.assertEqual(
            self.job.transicoes.filter(para_status=estados.PENDENTE).count(), 0
        )

    def test_retry_passa_com_outro_job_apenas_pendente(self):
        """Controle positivo da guarda estreita: retry é recuperação e não
        pode ficar preso em falhou só porque existe backlog do documento."""
        vizinho = OcrJob.objects.create(
            documento_digital_id=self.job.documento_digital_id
        )

        self.job.retry(motivo='reap periódico')

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.PENDENTE)
        self.assertEqual(self.job.tentativa, 2)
        vizinho.refresh_from_db()
        self.assertEqual(vizinho.status, estados.PENDENTE)


class CasSemTentativaExplicitaTestParte:
    """transicionar sem `tentativa` usa self.tentativa no CAS: o lease é
    SEMPRE parte da condição — objeto velho da tentativa 1 não encerra a
    tentativa 2 de outro worker."""

    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital()
        self.job, _ = criar_job(self.documento)

    def _reclaimar_tentativa_2(self):
        """claim(1) → reap → retry → claim(2); devolve objetos antigo e novo."""
        antigo = claim_proximo_job()
        self.assertIsNotNone(antigo)
        OcrJob.objects.filter(pk=self.job.pk).update(
            lease_expira_em=timezone.now() - timedelta(seconds=1)
        )
        reap_jobs_expirados(timeout_s=0)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.FALHOU)
        self.job.retry()
        novo = claim_proximo_job()
        self.assertIsNotNone(novo)
        return antigo, novo

    def test_objeto_velho_da_tentativa_1_nao_conclui_a_tentativa_2(self):
        antigo, _ = self._reclaimar_tentativa_2()
        # `antigo` em memória: status=em_execucao, tentativa=1 — igualzinho ao
        # banco, exceto pela tentativa (2). Só o CAS na tentativa pode salvar.
        with self.assertRaises(TransicaoConcorrente):
            antigo.transicionar(estados.CONCLUIDO)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.EM_EXECUCAO)
        self.assertEqual(self.job.tentativa, 2)
        self.assertEqual(self.job.paginas.count(), 0)
        self.assertEqual(
            self.job.transicoes.filter(para_status=estados.CONCLUIDO).count(), 0
        )
        # Auditoria da tentativa 2 intacta: claims das tentativas 1 e 2.
        self.assertEqual(
            self.job.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 2
        )

    def test_finalizacao_legitima_da_tentativa_2_transiciona(self):
        _, novo = self._reclaimar_tentativa_2()
        self.assertTrue(novo.transicionar(estados.CONCLUIDO))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertEqual(self.job.tentativa, 2)
