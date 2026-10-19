"""Formulário obsoleto na confirmação do texto (P1 do review do PR #288).

Dois revisores abrem a mesma página. O formulário do texto devolve a versão da
página que exibiu; se alguém gravou depois disso, o envio é recusado e nada
muda — nem o texto, nem a auditoria, nem o avanço do job. O lock do job só
serializa as escritas: quem detecta o formulário antigo é a versão.
"""

from django.contrib.auth.models import User

from dominial.models import UserTI
from ia_ocr import estados, services
from ia_ocr.models import ESTADO_CONFIRMADA, ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA

from .base_texto import TelaTextoBase
from .test_ui_card_ocr import _atributos, _elementos

TEXTO_ANTIGO = 'Área do imóvel: 100 hectares'
TEXTO_CORRIGIDO = 'Área do imóvel: 180 hectares'
# Página recém-saída do OCR: é a versão que os dois revisores recebem ao abrir
# a tela antes de qualquer gravação.
VERSAO_INICIAL = 0
ACOES = ('confirmar_pagina_ocr', 'editar_pagina_ocr')


class VersaoPaginaTest(TelaTextoBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.revisor_b = User.objects.create_user(
            username='revisor-b-texto', password='senha-revisor-b'
        )
        UserTI.objects.create(user=cls.revisor_b, tis=cls.ti)

    def setUp(self):
        super().setUp()
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=TEXTO_ANTIGO)

    def postar(self, usuario, acao, texto, versao):
        self.client.force_login(usuario)
        return self.client.post(
            self.url(acao, numero=1), {'texto': texto, 'versao': versao}
        )

    def versao_do_formulario(self, numero):
        """Versão que o formulário do texto carrega ao abrir a página."""
        tela = self.client.get(self.url_tela(pagina=numero))
        form = _elementos(
            tela.content.decode(), 'form', presentes=('data-ocr-texto-form',)
        )[0]
        campos = _elementos(
            str(form), 'input', valores={'type': 'hidden', 'name': 'versao'}
        )
        self.assertEqual(len(campos), 1)
        return int(_atributos(campos[0])['value'])

    def assert_recusado(self, resposta):
        """De volta à página, com o aviso do conflito e nada gravado."""
        self.assertRedirects(
            resposta, self.url_tela(pagina=1), fetch_redirect_response=False
        )
        erros = [msg for nivel, msg in self.mensagens(resposta) if nivel == 'error']
        self.assertEqual(len(erros), 1)
        self.assertIn('outra pessoa', erros[0])
        self.assertIn('recarregado', erros[0])

    def assert_intocada(self, numero):
        pagina = self.pagina(numero)
        self.assertEqual(pagina.estado, ESTADO_NAO_CONFIRMADA)
        self.assertIsNone(pagina.texto_confirmado)
        self.assertEqual(pagina.versao, VERSAO_INICIAL)

    def test_confirmar_com_formulario_obsoleto_nao_sobrescreve_correcao_nova(self):
        # A e B abriram a página 1 na versão inicial; A confirma a correção.
        self.postar(self.dono, 'confirmar_pagina_ocr', TEXTO_CORRIGIDO, VERSAO_INICIAL)
        confirmado_em = self.pagina(1).confirmado_em

        # B confirma o formulário que abriu antes, ainda com o texto do OCR.
        resposta = self.postar(
            self.revisor_b, 'confirmar_pagina_ocr', TEXTO_ANTIGO, VERSAO_INICIAL
        )

        pagina = self.pagina(1)
        self.assertEqual(pagina.texto_confirmado, TEXTO_CORRIGIDO)
        self.assertEqual(pagina.confirmado_por, self.dono)
        self.assertEqual(pagina.confirmado_em, confirmado_em)
        self.assert_recusado(resposta)

    def test_editar_com_formulario_obsoleto_nao_sobrescreve_correcao_nova(self):
        self.postar(self.dono, 'confirmar_pagina_ocr', TEXTO_CORRIGIDO, VERSAO_INICIAL)
        confirmado_em = self.pagina(1).confirmado_em

        # B salva como edição o texto antigo do formulário que abriu antes.
        resposta = self.postar(
            self.revisor_b, 'editar_pagina_ocr', TEXTO_ANTIGO, VERSAO_INICIAL
        )

        pagina = self.pagina(1)
        self.assertEqual(pagina.texto_confirmado, TEXTO_CORRIGIDO)
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)
        self.assertEqual(pagina.confirmado_por, self.dono)
        self.assertEqual(pagina.confirmado_em, confirmado_em)
        self.assert_recusado(resposta)

    def test_formulario_obsoleto_nao_confirma_sobre_o_rascunho_nem_libera_extracao(self):
        services.confirmar_pagina(self.job, 2, self.dono)
        services.confirmar_pagina(self.job, 3, self.dono)
        # A salva a correção da página 1 como edição, ainda sem confirmar.
        self.postar(self.dono, 'editar_pagina_ocr', TEXTO_CORRIGIDO, VERSAO_INICIAL)

        resposta = self.postar(
            self.revisor_b, 'confirmar_pagina_ocr', TEXTO_ANTIGO, VERSAO_INICIAL
        )

        pagina = self.pagina(1)
        self.assertEqual(pagina.estado, ESTADO_EDITADA)
        self.assertEqual(pagina.texto_confirmado, TEXTO_CORRIGIDO)
        self.assert_recusado(resposta)
        # Sem a confirmação indevida, o job não avança com o texto antigo.
        self.client.post(self.url('extrair_campos_ocr'))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)

    def test_reenvio_do_formulario_ja_aplicado_e_recusado_sem_mudar_nada(self):
        """Mesmo com o mesmo texto, o formulário já aplicado é obsoleto.

        Duplo clique ou "voltar" do navegador reenviam a versão antiga: a
        recusa não grava nada e a tela recarregada mostra a página confirmada.
        """
        self.postar(self.dono, 'confirmar_pagina_ocr', TEXTO_CORRIGIDO, VERSAO_INICIAL)
        antes = self.pagina(1)

        resposta = self.postar(
            self.dono, 'confirmar_pagina_ocr', TEXTO_CORRIGIDO, VERSAO_INICIAL
        )

        depois = self.pagina(1)
        self.assertEqual(
            (depois.texto_confirmado, depois.confirmado_em, depois.versao),
            (antes.texto_confirmado, antes.confirmado_em, antes.versao),
        )
        self.assert_recusado(resposta)

    def test_versao_incrementa_a_cada_mutacao(self):
        self.assertEqual(self.versao(1), VERSAO_INICIAL)

        pagina, _ = services.confirmar_pagina(self.job, 1, self.dono)
        self.assertEqual((pagina.versao, self.versao(1)), (1, 1))
        pagina, _ = services.editar_pagina(self.job, 1, TEXTO_CORRIGIDO)
        self.assertEqual((pagina.versao, self.versao(1)), (2, 2))
        pagina, _ = services.confirmar_pagina(self.job, 1, self.dono)
        self.assertEqual((pagina.versao, self.versao(1)), (3, 3))

        services.confirmar_todas_paginas(self.job, self.dono)

        # O bulk invalida os formulários abertos das páginas que confirmou; a
        # página já confirmada não é tocada.
        self.assertEqual(
            {p.numero_pagina: p.versao for p in self.job.paginas.all()},
            {1: 3, 2: 1, 3: 1},
        )

    def test_operacao_sem_alteracao_nao_muda_versao(self):
        services.confirmar_pagina(self.job, 1, self.dono)
        services.confirmar_todas_paginas(self.job, self.dono)
        versoes = {p.numero_pagina: p.versao for p in self.job.paginas.all()}

        _p, confirmou = services.confirmar_pagina(
            self.job, 1, self.dono, texto=TEXTO_ANTIGO, versao_esperada=versoes[1],
        )
        _p, editou = services.editar_pagina(
            self.job, 1, TEXTO_ANTIGO, versao_esperada=versoes[1],
        )
        total = services.confirmar_todas_paginas(self.job, self.dono)

        self.assertEqual((confirmou, editou, total), (False, False, 0))
        self.assertEqual(
            {p.numero_pagina: p.versao for p in self.job.paginas.all()}, versoes
        )

    def test_servico_recusa_versao_divergente_antes_de_gravar(self):
        with self.assertRaises(services.PaginaDesatualizada):
            services.confirmar_pagina(
                self.job, 1, self.dono, texto=TEXTO_CORRIGIDO,
                versao_esperada=VERSAO_INICIAL + 1,
            )
        with self.assertRaises(services.PaginaDesatualizada):
            services.editar_pagina(
                self.job, 1, TEXTO_CORRIGIDO, versao_esperada=VERSAO_INICIAL + 1,
            )

        self.assert_intocada(1)

    def test_versao_ausente_no_post_e_400(self):
        self.client.force_login(self.dono)

        for acao in ACOES:
            with self.subTest(acao=acao):
                resposta = self.client.post(
                    self.url(acao, numero=1), {'texto': TEXTO_CORRIGIDO}
                )

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(
                    resposta.content.decode(), 'Campo "versao" ausente ou inválido.'
                )
                self.assert_intocada(1)

    def test_versao_invalida_no_post_e_400(self):
        self.client.force_login(self.dono)

        # Inteiro gigante tem de ser 400, nunca 500 (limite do int() do Python).
        for acao in ACOES:
            for versao in ('', 'abc', '-1', '1.5', '9' * 5000):
                with self.subTest(acao=acao, versao=versao[:10]):
                    resposta = self.client.post(
                        self.url(acao, numero=1),
                        {'texto': TEXTO_CORRIGIDO, 'versao': versao},
                    )

                    self.assertEqual(resposta.status_code, 400)
                    self.assert_intocada(1)

    def test_confirmar_com_versao_atual_funciona(self):
        self.client.force_login(self.dono)
        versao = self.versao_do_formulario(1)
        self.assertEqual(versao, VERSAO_INICIAL)

        resposta = self.client.post(
            self.url('confirmar_pagina_ocr', numero=1),
            {'texto': TEXTO_CORRIGIDO, 'versao': versao},
        )

        self.assertRedirects(
            resposta, self.url_tela(pagina=1), fetch_redirect_response=False
        )
        self.assertIn(('success', 'Página 1 confirmada.'), self.mensagens(resposta))
        pagina = self.pagina(1)
        self.assertEqual(pagina.texto_confirmado, TEXTO_CORRIGIDO)
        self.assertEqual(pagina.confirmado_por, self.dono)

        # Idempotência: a tela recarregada traz a versão nova, e reconfirmar o
        # mesmo texto com ela não grava nada nem muda a versão.
        versao_nova = self.versao_do_formulario(1)
        self.assertEqual(versao_nova, versao + 1)
        resposta = self.client.post(
            self.url('confirmar_pagina_ocr', numero=1),
            {'texto': TEXTO_CORRIGIDO, 'versao': versao_nova},
        )

        self.assertIn(
            ('info', 'A página 1 já estava confirmada com este texto.'),
            self.mensagens(resposta),
        )
        depois = self.pagina(1)
        self.assertEqual(depois.versao, versao_nova)
        self.assertEqual(depois.confirmado_em, pagina.confirmado_em)
        self.assertEqual(depois.confirmado_por, self.dono)

    def test_editar_com_versao_atual_funciona(self):
        self.client.force_login(self.dono)

        resposta = self.client.post(
            self.url('editar_pagina_ocr', numero=1),
            {'texto': TEXTO_CORRIGIDO, 'versao': self.versao_do_formulario(1)},
        )

        self.assertRedirects(
            resposta, self.url_tela(pagina=1), fetch_redirect_response=False
        )
        pagina = self.pagina(1)
        self.assertEqual(pagina.estado, ESTADO_EDITADA)
        self.assertEqual(pagina.texto_confirmado, TEXTO_CORRIGIDO)
        # O rascunho também é mutação: o próximo envio da tela vai com a versão nova.
        self.assertEqual(self.versao_do_formulario(1), VERSAO_INICIAL + 1)
