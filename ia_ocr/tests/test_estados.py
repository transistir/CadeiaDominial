"""Máquina de estados do OcrJob: transições, CAS, gating de confirmação."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from ia_ocr import estados
from ia_ocr.estados import (
    TransicaoConcorrente, TransicaoInvalida, TRANSICOES_VALIDAS,
)
from ia_ocr.models import OcrJob, OcrJobTransicao, PaginaOcr
from ia_ocr.services import claim_proximo_job, criar_job, reap_jobs_expirados

from .factories import criar_documento_digital, criar_usuario


class TransicoesValidasTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(),
            criado_por=self.usuario,
        )

    def test_fluxo_completo_cadeia_feliz(self):
        """pendente → em_execucao → concluido → texto_confirmado → extraido → revisado → importado."""
        cadeia = [
            estados.EM_EXECUCAO,
            estados.CONCLUIDO,
            estados.TEXTO_CONFIRMADO,
            estados.EXTRAIDO,
            estados.REVISADO,
            estados.IMPORTADO,
        ]
        de = estados.PENDENTE
        for para in cadeia:
            with self.subTest(transicao=f'{de}→{para}'):
                if para == estados.TEXTO_CONFIRMADO:
                    # Pré-condição: todas as páginas confirmadas.
                    PaginaOcr.objects.create(
                        ocr_job=self.job,
                        numero_pagina=1,
                        texto_ocr='texto sintético',
                        confirmado_por=self.usuario,
                        confirmado_em=timezone.now(),
                    )
                self.assertTrue(self.job.transicionar(para, usuario=self.usuario))
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, para)
            de = para
        # Uma auditoria por transição, na ordem da cadeia.
        auditoria = list(self.job.transicoes.all())
        self.assertEqual(len(auditoria), 6)
        self.assertEqual(
            [(t.de_status, t.para_status) for t in auditoria],
            [
                (estados.PENDENTE, estados.EM_EXECUCAO),
                (estados.EM_EXECUCAO, estados.CONCLUIDO),
                (estados.CONCLUIDO, estados.TEXTO_CONFIRMADO),
                (estados.TEXTO_CONFIRMADO, estados.EXTRAIDO),
                (estados.EXTRAIDO, estados.REVISADO),
                (estados.REVISADO, estados.IMPORTADO),
            ],
        )
        self.assertEqual(
            {t.usuario for t in auditoria}, {self.usuario}
        )

    def test_em_execucao_para_falhou(self):
        """em_execucao → falhou grava código/mensagem de erro e audita."""
        self.job.transicionar(estados.EM_EXECUCAO)
        self.job.transicionar(
            estados.FALHOU,
            motivo='serviço fora do ar',
            erro_codigo='SERVICO_INDISPONIVEL',
            erro_mensagem='gateway respondeu 503',
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.FALHOU)
        self.assertEqual(self.job.erro_codigo, 'SERVICO_INDISPONIVEL')
        self.assertEqual(self.job.erro_mensagem, 'gateway respondeu 503')

    def test_transicao_invalida_nao_grava_nada(self):
        """Transição fora do mapa: TransicaoInvalida, sem status novo e sem auditoria."""
        with self.assertRaises(TransicaoInvalida):
            self.job.transicionar(estados.CONCLUIDO)  # pendente → concluido não existe
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.PENDENTE)
        self.assertEqual(self.job.transicoes.count(), 0)

    def test_transicao_para_o_mesmo_estado_invalida(self):
        with self.assertRaises(TransicaoInvalida):
            self.job.transicionar(estados.PENDENTE)
        self.assertEqual(self.job.transicoes.count(), 0)

    def test_transicionar_pendente_direto_de_falhou_rejeitado(self):
        """falhou → pendente só via retry(); transicionar direto é rejeitado."""
        self.job.transicionar(estados.EM_EXECUCAO)
        self.job.transicionar(estados.FALHOU, erro_codigo='X', erro_mensagem='y')
        with self.assertRaises(TransicaoInvalida):
            self.job.transicionar(estados.PENDENTE)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.FALHOU)
        # Auditoria só das duas transições válidas (em_execucao e falhou).
        self.assertEqual(self.job.transicoes.count(), 2)

    def test_cas_perdido_levanta_transicao_concorrente_sem_auditoria(self):
        """Estado muda entre leitura e update: nada é gravado."""
        job_stale = OcrJob.objects.get(pk=self.job.pk)  # leitura "antiga"
        self.job.transicionar(estados.EM_EXECUCAO)  # outro ator muda o estado
        with self.assertRaises(TransicaoConcorrente):
            # job_stale ainda acredita que o job está pendente; a transição é
            # válida no mapa, mas o CAS falha porque o estado persistido mudou.
            job_stale.transicionar(estados.EM_EXECUCAO)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.EM_EXECUCAO)
        # Apenas a auditoria da transição vencedora.
        self.assertEqual(
            self.job.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 1
        )
        self.assertEqual(self.job.transicoes.count(), 1)

    def test_de_status_explicito_condiciona_o_cas(self):
        """de_status explícito vale mais que o status em memória (que pode estar velho)."""
        self.job.transicionar(estados.EM_EXECUCAO)
        job_stale = OcrJob.objects.get(pk=self.job.pk)
        job_stale.status = estados.PENDENTE  # memória desatualizada
        # O CAS usa de_status=em_execucao (que é o estado real do banco): passa.
        self.assertTrue(
            job_stale.transicionar(estados.CONCLUIDO, de_status=estados.EM_EXECUCAO)
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)

    def test_tentativa_condiciona_o_cas(self):
        """tentativa no filtro: lease de tentativa antiga não transiciona."""
        self.job.transicionar(estados.EM_EXECUCAO)
        self.job.tentativa = 99  # worker com lease velho
        with self.assertRaises(TransicaoConcorrente):
            self.job.transicionar(estados.CONCLUIDO, tentativa=99)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.EM_EXECUCAO)


class ConfirmacaoDeTextoTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(),
        )
        self.job.transicionar(estados.EM_EXECUCAO)
        self.job.transicionar(estados.CONCLUIDO)

    def _criar_paginas(self, numeros, confirmadas=()):
        agora = timezone.now()
        for n in numeros:
            PaginaOcr.objects.create(
                ocr_job=self.job,
                numero_pagina=n,
                texto_ocr=f'texto sintético da página {n}',
                confirmado_por=self.usuario if n in confirmadas else None,
                confirmado_em=agora if n in confirmadas else None,
            )

    def test_bloqueado_com_pagina_nao_confirmada(self):
        self._criar_paginas([1, 2], confirmadas=(1,))
        with self.assertRaises(TransicaoInvalida):
            self.job.transicionar(estados.TEXTO_CONFIRMADO)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertEqual(
            self.job.transicoes.filter(para_status=estados.TEXTO_CONFIRMADO).count(),
            0,
        )

    def test_liberado_com_todas_as_paginas_confirmadas(self):
        self._criar_paginas([1, 2], confirmadas=(1, 2))
        self.job.transicionar(estados.TEXTO_CONFIRMADO)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)

    def test_pagina_em_branco_e_confirmavel(self):
        """Página de verso/branca confirma por confirmado_em, não por texto."""
        PaginaOcr.objects.create(
            ocr_job=self.job,
            numero_pagina=1,
            texto_ocr='',  # sem texto — verso em branco
            confirmado_por=self.usuario,
            confirmado_em=timezone.now(),
        )
        self.job.transicionar(estados.TEXTO_CONFIRMADO)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)

    def test_job_sem_paginas_nao_confirma(self):
        with self.assertRaises(TransicaoInvalida):
            self.job.transicionar(estados.TEXTO_CONFIRMADO)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)

    def test_validacao_roda_depois_do_cas_dentro_do_atomic(self):
        """A pré-condição é validada APÓS o UPDATE vencedor, dentro do atomic
        (sem TOCTOU): falha na validação → rollback do status e sem auditoria."""
        self._criar_paginas([1], confirmadas=(1,))
        status_visto = {}

        def validar_depois_do_update(job):
            # Mesma conexão/transação: se a validação roda depois do UPDATE,
            # o status visível aqui já é o novo.
            status_visto['status'] = OcrJob.objects.get(pk=job.pk).status
            raise TransicaoInvalida('falha sintética pós-update', code='sintetico')

        with mock.patch.object(
            OcrJob, '_validar_confirmacao_de_texto', validar_depois_do_update,
        ):
            with self.assertRaises(TransicaoInvalida):
                self.job.transicionar(estados.TEXTO_CONFIRMADO)

        self.assertEqual(status_visto.get('status'), estados.TEXTO_CONFIRMADO)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)  # rollback do UPDATE
        self.assertEqual(
            self.job.transicoes.filter(para_status=estados.TEXTO_CONFIRMADO).count(),
            0,
        )


class RetryTest(TestCase):
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


class CasSemTentativaExplicitaTest(TestCase):
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
