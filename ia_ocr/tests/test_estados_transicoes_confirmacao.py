"""Transições e confirmação de texto, migradas verbatim."""

from unittest import mock

from django.utils import timezone

from ia_ocr import estados
from ia_ocr.estados import TransicaoConcorrente, TransicaoInvalida
from ia_ocr.models import ExtracaoSugerida, OcrJob, PaginaOcr

from .factories import criar_documento_digital, criar_usuario

class TransicoesValidasTestParte:
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
                if para == estados.EXTRAIDO:
                    # Pré-condição: extração sugerida registrada (I-5).
                    ExtracaoSugerida.objects.create(
                        ocr_job=self.job,
                        schema_version='umbelino-extracao-matricula-v1',
                        payload={},
                        payload_servico={},
                        provider='stub',
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


class ConfirmacaoDeTextoTestParte:
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


class PaginaCorrigidaTestParte:
    """Texto corrigido pelo serviço (I-5 / decisão #290/16-10) convive com
    o texto original do OCR: corrigir não apaga o texto_ocr."""

    def test_pagina_corrigida_nao_apaga_texto_ocr(self):
        job = OcrJob.objects.create(documento_digital=criar_documento_digital())
        pagina = PaginaOcr.objects.create(
            ocr_job=job,
            numero_pagina=1,
            texto_ocr='texto do ocr',
            texto_corrigido='texto corrigido',
            corrigido_em=timezone.now(),
        )
        pagina.refresh_from_db()
        self.assertEqual(pagina.texto_ocr, 'texto do ocr')
        self.assertEqual(pagina.texto_corrigido, 'texto corrigido')
        self.assertIsNotNone(pagina.corrigido_em)
