"""Partes por cenário de ``test_texto_views``; coletadas pela fachada."""

from unittest import mock

from django.contrib.auth.models import User

from dominial.models import UserTI
from ia_ocr import estados, services
from ia_ocr.models import ESTADO_CONFIRMADA, ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA, OcrJob

from .base_texto import TEXTOS
from .payloads_extracao import TEXTO_PAGINA_1, payload_averbacao
from .test_ui_card_ocr import _atributos, _elementos

class ConfirmarPaginaViewTestParte:
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def test_confirmar_grava_texto_e_auditoria_e_volta_para_a_mesma_pagina(self):
        resposta = self.client.post(
            self.url('confirmar_pagina_ocr', numero=1),
            {'texto': TEXTOS[0], 'versao': self.versao(1)},
        )

        self.assertRedirects(
            resposta, self.url_tela(pagina=1), fetch_redirect_response=False
        )
        pagina = self.pagina(1)
        self.assertEqual(pagina.texto_confirmado, TEXTOS[0])
        self.assertEqual(pagina.confirmado_por, self.dono)
        self.assertIsNotNone(pagina.confirmado_em)
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)
        self.assertIn('success', [nivel for nivel, _msg in self.mensagens(resposta)])

    def test_confirmar_com_texto_editado_grava_o_texto_do_textarea(self):
        resposta = self.client.post(
            self.url('confirmar_pagina_ocr', numero=2),
            {'texto': 'segunda corrigida\r\ncom duas linhas', 'versao': self.versao(2)},
        )

        self.assertEqual(resposta.status_code, 302)
        pagina = self.pagina(2)
        self.assertEqual(pagina.texto_confirmado, 'segunda corrigida\ncom duas linhas')
        self.assertEqual(pagina.texto_ocr, TEXTOS[1])
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)

    def test_confirmar_sem_o_campo_texto_confirma_o_texto_vigente(self):
        resposta = self.client.post(
            self.url('confirmar_pagina_ocr', numero=3), {'versao': self.versao(3)}
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.pagina(3).texto_confirmado, TEXTOS[2])

    def test_editar_depois_de_confirmada_marca_editada_e_exige_reconfirmacao(self):
        self.client.post(
            self.url('confirmar_pagina_ocr', numero=1),
            {'texto': TEXTOS[0], 'versao': self.versao(1)},
        )

        resposta = self.client.post(
            self.url('editar_pagina_ocr', numero=1),
            {'texto': 'primeira editada', 'versao': self.versao(1)},
        )

        self.assertRedirects(
            resposta, self.url_tela(pagina=1), fetch_redirect_response=False
        )
        pagina = self.pagina(1)
        self.assertEqual(pagina.estado, ESTADO_EDITADA)
        self.assertIsNone(pagina.confirmado_em)
        self.assertIsNone(pagina.confirmado_por)
        # A tela passa a mostrar a página como editada e pede reconfirmação.
        tela = self.client.get(self.url_tela(pagina=1))
        abas = _elementos(tela.content.decode(), 'a', presentes=('data-ocr-aba',))
        self.assertEqual(_atributos(abas[0])['data-estado'], ESTADO_EDITADA)
        self.assertEqual(tela.context['confirmadas'], 0)
        self.assertContains(tela, 'Editada')

    def test_editar_sem_o_campo_texto_e_requisicao_invalida_e_nao_esvazia_a_pagina(self):
        resposta = self.client.post(
            self.url('editar_pagina_ocr', numero=1), {'versao': self.versao(1)}
        )

        self.assertEqual(resposta.status_code, 400)
        pagina = self.pagina(1)
        self.assertEqual(pagina.estado, ESTADO_NAO_CONFIRMADA)
        self.assertIsNone(pagina.texto_confirmado)

    def test_post_em_job_fora_de_concluido_nao_grava_e_avisa(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)

        for nome in ('confirmar_pagina_ocr', 'editar_pagina_ocr'):
            with self.subTest(acao=nome):
                resposta = self.client.post(
                    self.url(nome, numero=1),
                    {'texto': 'tarde demais', 'versao': self.versao(1)},
                )

                self.assertRedirects(
                    resposta, self.url_tela(pagina=1), fetch_redirect_response=False
                )
                self.assertIn('error', [n for n, _m in self.mensagens(resposta)])
                pagina = self.pagina(1)
                self.assertIsNone(pagina.texto_confirmado)
                self.assertIsNone(pagina.confirmado_em)

    def test_post_em_pagina_inexistente_recebe_404(self):
        # 10**20 estoura o inteiro do banco: tem de ser 404, nunca 500.
        for nome in ('confirmar_pagina_ocr', 'editar_pagina_ocr'):
            for numero in (99, 10 ** 20):
                with self.subTest(acao=nome, numero=numero):
                    resposta = self.client.post(
                        self.url(nome, numero=numero), {'texto': 'x', 'versao': 0}
                    )

                    self.assertEqual(resposta.status_code, 404)

    def test_qualquer_usuario_com_acesso_ao_documento_confirma(self):
        """Quem tem acesso ao documento confirma: não há dono do job."""
        outro = User.objects.create_user(username='colega', password='senha-colega')
        UserTI.objects.create(user=outro, tis=self.ti)
        self.client.force_login(outro)

        resposta = self.client.post(
            self.url('confirmar_pagina_ocr', numero=1), {'versao': self.versao(1)}
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.pagina(1).confirmado_por, outro)


class AutoExtrairTelaTextoTestParte:
    """#314: a tela só se auto-submete quando ainda não há extração."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def _auto(self, resposta):
        return _elementos(resposta.content.decode(), 'form', presentes=('data-ocr-auto-extrair',))

    def test_auto_extrair_verdadeiro_sem_extracao(self):
        resposta = self.client.get(self.url_tela())

        self.assertTrue(resposta.context['auto_extrair'])
        self.assertEqual(len(self._auto(resposta)), 1)
        self.assertContains(resposta, 'aria-live="polite"')
        # Progresso nasce escondido e a região viva vazia (o JS preenche no disparo).
        self.assertContains(resposta, 'hidden data-ocr-auto-extrair-progresso')
        self.assertContains(resposta, 'data-ocr-auto-extrair-aviso role="status" aria-live="polite"></small>')
        self.assertNotContains(resposta, 'Preparando o formulário com os campos reconhecidos')
        self.assertContains(resposta, 'dominial/js/ocr_auto_extrair.js')

    def test_auto_extrair_falso_com_extracao_vigente(self):
        with mock.patch.object(type(self.job), 'extracao_vigente', return_value=object()):
            resposta = self.client.get(self.url_tela())

        self.assertFalse(resposta.context['auto_extrair'])
        self.assertEqual(self._auto(resposta), [])
        self.assertNotContains(resposta, 'ocr_auto_extrair.js')

    def test_auto_extrair_falso_sem_pode_extrair(self):
        with mock.patch(
            'ia_ocr.views._disponibilidade_extracao',
            return_value=(False, 'O OCR não devolveu texto para todas as páginas.'),
        ):
            resposta = self.client.get(self.url_tela())

        self.assertFalse(resposta.context['pode_extrair'])
        self.assertFalse(resposta.context['auto_extrair'])
        self.assertEqual(self._auto(resposta), [])

    def test_auto_extrair_falso_com_job_nao_revisavel(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)

        resposta = self.client.get(self.url_tela())

        self.assertFalse(resposta.context['auto_extrair'])
        self.assertEqual(self._auto(resposta), [])

    def test_tela_auto_nao_servida_com_o_campo_extrair_auto(self):
        """PR #319 tarefa 2 (Codex MUST-FIX): a marca `extrair_auto` não pode
        viver no HTML do form — senão o clique manual do mesmo form a carrega
        e, havendo extração vigente (outra aba/página volta pelo histórico),
        deixa de reextrair e recebe "Os campos já foram extraídos.". O campo
        passa a ser injetado pelo JS só no disparo automático."""
        resposta = self.client.get(self.url_tela())

        self.assertTrue(resposta.context['auto_extrair'])
        self.assertNotContains(resposta, 'name="extrair_auto"')
        # O JS continua achando o form e o job para injetar a marca no disparo.
        self.assertContains(resposta, 'data-ocr-auto-extrair-job=')

        with mock.patch.object(type(self.job), 'extracao_vigente', return_value=object()):
            manual = self.client.get(self.url_tela())
        html_manual = manual.content.decode()

        self.assertFalse(manual.context['auto_extrair'])
        self.assertIn('data-ocr-extrair-campos', html_manual)
        self.assertNotIn('name="extrair_auto"', html_manual)


class AutoExtrairCliqueManualTestParte:
    """PR #319 tarefa 2: o clique manual em "Extrair campos" na tela da
    auto-extração vai SEM `extrair_auto` (o campo não está mais no HTML) e
    continua podendo reextrair sobre uma extração vigente — não vira
    "Os campos já foram extraídos."."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)
        self.documento.tipo.tipo = 'matricula'
        self.documento.tipo.save(update_fields=['tipo'])
        self.backend = mock.Mock(spec=['extrair'])
        self.backend.extrair.return_value = {
            'extracao': payload_averbacao(self.job.job_id),
            'dpi': 300,
            'paginas': [
                {
                    'pagina': pagina.numero_pagina,
                    'texto_corrigido': (
                        TEXTO_PAGINA_1 if pagina.numero_pagina == 1 else pagina.texto_ocr
                    ),
                }
                for pagina in self.job.paginas.all()
            ],
        }
        backend_patch = mock.patch(
            'ia_ocr.services.get_extracao_backend', return_value=self.backend,
        )
        backend_patch.start()
        self.addCleanup(backend_patch.stop)

    def test_clique_manual_sem_flag_reeextrai_sobre_vigente(self):
        """POST manual (sem o campo) com extração vigente: reextrai de verdade
        — 2 extrações e mensagem de sucesso, não o aviso de já-extraído."""
        vigente = services.solicitar_extracao(self.job, self.dono)
        self.assertEqual(self.job.extracoes.count(), 1)

        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertRedirects(
            resposta, self.url('revisar_job_ocr'), fetch_redirect_response=False,
        )
        self.assertIn((
            'success', 'Extração concluída. Revise cada ato no formulário.',
        ), self.mensagens(resposta))
        self.assertNotIn(
            ('info', 'Os campos já foram extraídos.'), self.mensagens(resposta),
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.extracoes.count(), 2)
        self.assertNotEqual(self.job.extracao_vigente(), vigente)
        self.assertEqual(self.backend.extrair.call_count, 2)

