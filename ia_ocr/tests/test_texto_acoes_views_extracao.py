"""Extração e campos pendentes da tela de texto, migrados verbatim."""

from ia_ocr import estados, services
from ia_ocr.models import OcrJob
from ia_ocr.views import _disponibilidade_extracao

from .test_texto_acoes_views_base import _botao
from .test_ui_card_ocr import _atributos, _elementos
from .base_texto import _texto_completo


class ExtrairCamposViewTestParte:
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def _confirmar_todas(self):
        services.confirmar_todas_paginas(self.job, self.dono)

    def _estado_do_botao(self, pagina=1):
        resposta = self.client.get(self.url_tela(pagina=pagina))
        conteudo = resposta.content.decode()
        motivo = _elementos(conteudo, 'small', presentes=('data-ocr-extrair-campos-motivo',))
        return (
            resposta,
            _atributos(_botao(conteudo, 'data-ocr-extrair-campos')),
            [' '.join(_texto_completo(m).split()) for m in motivo],
        )

    def test_botao_habilitado_quando_ocr_concluiu(self):
        """#290: a confirmação do texto não é mais pré-requisito da extração."""
        resposta, atributos, motivo = self._estado_do_botao()

        self.assertFalse(resposta.context['todas_confirmadas'])
        self.assertTrue(resposta.context['pode_extrair'])
        self.assertNotIn('disabled', atributos)
        self.assertEqual(motivo, [])

    def test_texto_confirmado_mostra_extrair(self):
        services.confirmar_todas_paginas(self.job, self.dono)
        services.confirmar_texto(self.job, self.dono)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)

        resposta = self.client.get(self.url_tela(pagina=1))
        conteudo = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context['pode_extrair'])
        botao = _botao(conteudo, 'data-ocr-extrair-campos')
        self.assertIsNotNone(botao)
        self.assertNotIn('disabled', _atributos(botao))
        self.assertEqual(
            _elementos(conteudo, 'button', presentes=('data-ocr-confirmar-todas',)),
            [],
        )
        self.assertEqual(
            _elementos(conteudo, 'button', presentes=('data-ocr-reprocessar',)),
            [],
        )
        self.assertEqual(
            len(_elementos(conteudo, 'a', presentes=('data-ocr-campos-link',))),
            1,
        )

    def test_texto_extraido_nao_mostra_extrair(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EXTRAIDO)

        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()

        self.assertIsNone(_botao(conteudo, 'data-ocr-extrair-campos'))
        self.assertEqual(
            len(_elementos(conteudo, 'a', presentes=('data-ocr-campos-link',))),
            1,
        )

    def test_texto_revisado_nao_mostra_extrair(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.REVISADO)

        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()

        self.assertIsNone(_botao(conteudo, 'data-ocr-extrair-campos'))
        self.assertEqual(
            len(_elementos(conteudo, 'a', presentes=('data-ocr-campos-link',))),
            1,
        )

    def test_botao_desabilitado_enquanto_job_nao_concluiu(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EM_EXECUCAO)
        self.job.refresh_from_db()

        # Fora de `concluido` sem texto a tela nem abre (volta ao upload);
        # a regra do botão é verificada diretamente no cálculo da view.
        resposta = self.client.get(self.url_tela(pagina=1))
        self.assertEqual(resposta.status_code, 302)
        self.assertIsNone(_botao(resposta.content.decode(), 'data-ocr-extrair-campos'))
        self.assertEqual(
            _disponibilidade_extracao(self.job, list(self.job.paginas.all())),
            (False, 'Aguardando o OCR terminar.'),
        )

    def test_botao_habilitado_com_pagina_em_branco(self):
        # Verso em branco é OCR legítimo: o serviço aceita, a tela também.
        self.job.paginas.filter(numero_pagina=2).update(texto_ocr='')

        resposta, atributos, motivo = self._estado_do_botao()

        self.assertTrue(resposta.context['pode_extrair'])
        self.assertNotIn('disabled', atributos)
        self.assertEqual(motivo, [])

    def test_sem_texto_ocr_ou_sem_paginas_desabilita(self):
        sem_texto = (False, 'O OCR não devolveu texto para todas as páginas.')
        # Sem páginas: a tela dá 404 antes, mas a regra recusa como o serviço.
        self.assertEqual(_disponibilidade_extracao(self.job, []), sem_texto)
        # PaginaOcr.texto_ocr é NOT NULL: ``None`` não chega do banco, então
        # o ramo (espelho do ``is None`` do serviço) é exercido em memória.
        paginas = list(self.job.paginas.all())
        paginas[1].texto_ocr = None
        self.assertEqual(_disponibilidade_extracao(self.job, paginas), sem_texto)

    def test_confirmacao_de_pagina_nao_muda_o_botao(self):
        _resposta, antes, motivo_antes = self._estado_do_botao()

        services.confirmar_pagina(self.job, 1, self.dono)
        _resposta, depois, motivo_depois = self._estado_do_botao()

        self.assertNotIn('disabled', antes)
        self.assertEqual(antes, depois)
        self.assertEqual(motivo_antes, motivo_depois)

    def test_post_com_pagina_pendente_nao_transiciona(self):
        services.confirmar_pagina(self.job, 1, self.dono)

        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn('error', [n for n, _m in self.mensagens(resposta)])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertFalse(
            self.job.transicoes.filter(para_status=estados.TEXTO_CONFIRMADO).exists()
        )

    def test_post_com_pagina_editada_nao_transiciona(self):
        self._confirmar_todas()
        services.editar_pagina(self.job, 3, 'terceira mexida')

        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertIn('error', [n for n, _m in self.mensagens(resposta)])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)


class CamposPendenteViewTestParte:
    """Ponto de entrada reservado para a I-5 (#262): sem a tela de campos."""

    def test_estado_legado_texto_confirmado_volta_para_a_tela(self):
        """#290: `texto_confirmado` saiu do fluxo — só `concluido` extrai.

        O caminho novo (POST em `concluido` → `extraido`) está em
        `test_extracao_views.ExtrairCamposViewTest`; aqui só se garante que o
        estado legado não abre a revisão de campos.
        """
        services.confirmar_todas_paginas(self.job, self.dono)
        services.confirmar_texto(self.job, self.dono)
        self.client.force_login(self.dono)

        resposta = self.client.get(self.url('campos_job_ocr'))

        self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
        self.assertIn('info', [n for n, _m in self.mensagens(resposta)])

    def test_job_ainda_nao_confirmado_volta_para_a_tela_do_texto(self):
        self.client.force_login(self.dono)

        resposta = self.client.get(self.url('campos_job_ocr'))

        self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
        self.assertIn('info', [n for n, _m in self.mensagens(resposta)])

    def test_permissoes(self):
        url = self.url('campos_job_ocr')

        anonimo = self.client.get(url)
        self.assertEqual(anonimo.status_code, 302)
        self.assertIn('/accounts/login/', anonimo['Location'])

        self.client.force_login(self.sem_acesso)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.dono)
        self.assertEqual(self.client.post(url).status_code, 405)
