"""Ações gerais da tela de confirmação do texto (issue #261 / I-4, fatia 2).

POST .../texto/confirmar-todas/   → bulk (só sem edição pendente)
POST .../texto/reprocessar/       → novo job pela I-2, histórico preservado
POST .../texto/extrair-campos/    → concluido → texto_confirmado (só com tudo confirmado)
GET  .../campos/                  → ponto de entrada da I-5 (#262), ainda sem a tela
"""

from ia_ocr import estados, services
from ia_ocr.models import ESTADO_CONFIRMADA, ESTADO_EDITADA, OcrJob
from ia_ocr.views import _disponibilidade_extracao

from .base_texto import TEXTOS, TelaTextoBase, _texto_completo
from .factories import criar_job_concluido
from .test_ui_card_ocr import _atributos, _elementos


def _botao(conteudo, atributo):
    achados = _elementos(conteudo, 'button', presentes=(atributo,))
    return achados[0] if achados else None


class PermissaoAcoesGeraisTest(TelaTextoBase):
    ACOES = ('confirmar_paginas_ocr', 'reprocessar_job_ocr', 'extrair_campos_ocr')

    def test_nao_autenticado_redireciona_para_login_e_nao_muda_nada(self):
        for nome in self.ACOES:
            with self.subTest(acao=nome):
                resposta = self.client.post(self.url(nome))

                self.assertEqual(resposta.status_code, 302)
                self.assertIn('/accounts/login/', resposta['Location'])
        self.assertEqual(OcrJob.objects.count(), 1)
        self.assertEqual(self.job.paginas.filter(confirmado_em__isnull=False).count(), 0)

    def test_usuario_sem_acesso_recebe_404_e_nao_muda_nada(self):
        self.client.force_login(self.sem_acesso)

        for nome in self.ACOES:
            with self.subTest(acao=nome):
                resposta = self.client.post(self.url(nome))

                self.assertEqual(resposta.status_code, 404)
        self.assertEqual(OcrJob.objects.count(), 1)
        self.assertEqual(self.job.paginas.filter(confirmado_em__isnull=False).count(), 0)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)

    def test_get_recebe_405(self):
        self.client.force_login(self.dono)

        for nome in self.ACOES:
            with self.subTest(acao=nome):
                self.assertEqual(self.client.get(self.url(nome)).status_code, 405)


class ConfirmarTodasViewTest(TelaTextoBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def test_post_confirma_todas_as_pendentes_e_volta_para_a_mesma_pagina(self):
        resposta = self.client.post(self.url('confirmar_paginas_ocr'), {'pagina': '2'})

        self.assertRedirects(
            resposta, self.url_tela(pagina=2), fetch_redirect_response=False
        )
        for numero in (1, 2, 3):
            pagina = self.pagina(numero)
            self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)
            self.assertEqual(pagina.confirmado_por, self.dono)
            self.assertEqual(pagina.texto_confirmado, TEXTOS[numero - 1])
        self.assertIn('success', [n for n, _m in self.mensagens(resposta)])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)

    def test_mensagem_de_sucesso_concorda_com_o_numero_de_paginas(self):
        plural = self.client.post(self.url('confirmar_paginas_ocr'))
        self.assertIn(
            ('success', '3 páginas confirmadas sem alteração.'), self.mensagens(plural)
        )

        unico = criar_job_concluido(self.arquivo, textos=['única página'])
        singular = self.client.post(self.url('confirmar_paginas_ocr', unico))
        self.assertIn(
            ('success', '1 página confirmada sem alteração.'), self.mensagens(singular)
        )

    def test_pagina_invalida_no_post_cai_na_tela_sem_parametro(self):
        for valor in ('../../x', '-1', '9' * 5000):
            with self.subTest(pagina=valor[:20]):
                resposta = self.client.post(
                    self.url('confirmar_paginas_ocr'), {'pagina': valor}
                )

                self.assertRedirects(
                    resposta, self.url_tela(), fetch_redirect_response=False
                )

    def test_post_com_pagina_editada_nao_confirma_nada_e_avisa(self):
        services.editar_pagina(self.job, 2, 'segunda mexida')

        resposta = self.client.post(self.url('confirmar_paginas_ocr'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn('error', [n for n, _m in self.mensagens(resposta)])
        self.assertEqual(self.job.paginas.filter(confirmado_em__isnull=False).count(), 0)
        self.assertEqual(self.pagina(2).estado, ESTADO_EDITADA)

    def test_post_em_job_fora_de_concluido_avisa_e_nao_grava(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)

        resposta = self.client.post(self.url('confirmar_paginas_ocr'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn('error', [n for n, _m in self.mensagens(resposta)])
        self.assertEqual(self.job.paginas.filter(confirmado_em__isnull=False).count(), 0)

    def test_botao_habilitado_quando_ha_pendentes_e_nenhuma_edicao(self):
        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()

        botao = _botao(conteudo, 'data-ocr-confirmar-todas')
        self.assertIsNotNone(botao)
        self.assertNotIn('disabled', _atributos(botao))

    def test_botao_desabilitado_com_pagina_editada_e_explica_o_motivo(self):
        services.editar_pagina(self.job, 2, 'segunda mexida')

        resposta = self.client.get(self.url_tela(pagina=1))
        conteudo = resposta.content.decode()

        self.assertIn('disabled', _atributos(_botao(conteudo, 'data-ocr-confirmar-todas')))
        motivo = _elementos(conteudo, 'small', presentes=('data-ocr-confirmar-todas-motivo',))
        self.assertEqual(len(motivo), 1)
        self.assertIn('editada', _texto_completo(motivo[0]))

    def test_botao_desabilitado_quando_nao_ha_pendentes(self):
        services.confirmar_todas_paginas(self.job, self.dono)

        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()

        self.assertIn('disabled', _atributos(_botao(conteudo, 'data-ocr-confirmar-todas')))


class ReprocessarViewTest(TelaTextoBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def test_post_cria_novo_job_pendente_e_preserva_o_historico_do_anterior(self):
        services.confirmar_pagina(self.job, 1, self.dono, texto='primeira corrigida')
        services.confirmar_pagina(self.job, 2, self.dono)
        pagina_antes = self.pagina(1)
        transicoes_antes = list(self.job.transicoes.values_list('pk', flat=True))

        resposta = self.client.post(self.url('reprocessar_job_ocr'))

        self.assertRedirects(resposta, self.url_upload(), fetch_redirect_response=False)
        # Novo ciclo: outro job, pendente, para o mesmo arquivo, forçando OCR.
        novo = OcrJob.objects.exclude(pk=self.job.pk).get()
        self.assertEqual(novo.status, estados.PENDENTE)
        self.assertEqual(novo.documento_digital_id, self.arquivo.pk)
        self.assertEqual(novo.criado_por, self.dono)
        self.assertTrue(novo.forcar_ocr)
        self.assertNotEqual(novo.job_id, self.job.job_id)
        self.assertEqual(novo.paginas.count(), 0)
        # Histórico: o job anterior, suas páginas e sua auditoria ficam intactos.
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertEqual(self.job.paginas.count(), 3)
        pagina = self.pagina(1)
        self.assertEqual(pagina.texto_confirmado, 'primeira corrigida')
        self.assertEqual(pagina.confirmado_por, self.dono)
        self.assertEqual(pagina.confirmado_em, pagina_antes.confirmado_em)
        self.assertEqual(self.pagina(2).estado, ESTADO_CONFIRMADA)
        self.assertEqual(
            list(self.job.transicoes.values_list('pk', flat=True)), transicoes_antes
        )
        self.assertIn('success', [n for n, _m in self.mensagens(resposta)])

    def test_com_job_ativo_no_documento_nao_cria_outro(self):
        ativo, _criado = services.criar_job(self.arquivo, criado_por=self.dono)

        resposta = self.client.post(self.url('reprocessar_job_ocr'))

        self.assertRedirects(resposta, self.url_upload(), fetch_redirect_response=False)
        self.assertEqual(OcrJob.objects.count(), 2)
        self.assertIn('info', [n for n, _m in self.mensagens(resposta)])
        self.assertTrue(OcrJob.objects.filter(pk=ativo.pk).exists())

    def test_job_fora_de_concluido_recusa_e_nao_cria_job(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)

        resposta = self.client.post(self.url('reprocessar_job_ocr'))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn('error', [n for n, _m in self.mensagens(resposta)])
        self.assertEqual(OcrJob.objects.count(), 1)

    def test_tela_avisa_que_o_texto_confirmado_so_e_substituido_apos_o_novo_ciclo(self):
        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()

        botao = _botao(conteudo, 'data-ocr-reprocessar')
        self.assertIsNotNone(botao)
        self.assertNotIn('disabled', _atributos(botao))
        aviso = _elementos(conteudo, 'small', presentes=('data-ocr-reprocessar-aviso',))
        self.assertEqual(len(aviso), 1)
        texto = ' '.join(_texto_completo(aviso[0]).split())
        self.assertIn('só será substituído', texto)
        self.assertIn('histórico', texto)


class ExtrairCamposViewTest(TelaTextoBase):
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

    # Fluxo antigo (texto_confirmado → link da I-5) removido pela #290: o job
    # vai de `concluido` direto a `extraido` e a extração é solicitada ao
    # serviço. Os casos estão em `test_extracao_views.py`:
    #   - sucesso/transição: test_extrair_sucesso_redireciona_e_transiciona
    #   - nova extração sobre job já extraído: test_reextracao_*


class CamposPendenteViewTest(TelaTextoBase):
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
