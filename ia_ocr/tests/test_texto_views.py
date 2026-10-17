"""Tela de confirmação do texto OCR (issue #261 / I-4, fatia 1).

GET   .../documento/<id>/ocr-job/<uuid>/texto/?pagina=N   → split-view PDF × texto
POST  .../texto/pagina/<n>/confirmar/                      → grava texto + auditoria
POST  .../texto/pagina/<n>/editar/                         → "editada": exige reconfirmação

Permissões: a mesma política do upload (login_required + hierarquia
TI→Imóvel→Documento). Fora do escopo do usuário → 404, o padrão do projeto
(ver test_views_ocr_jobs / test_segregacao_usuario); anônimo → 302 para o login.
"""

import uuid
from datetime import date

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.template.defaultfilters import date as filtro_date
from django.urls import reverse
from django.utils import timezone

from dominial.models import Documento, UserTI
from ia_ocr import estados, services
from ia_ocr.models import (
    ESTADO_CONFIRMADA, ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA, OcrJob,
    PaginaOcr,
)

from .base_texto import TEXTOS, TelaTextoBase, _texto_completo
from .test_ui_card_ocr import _atributos, _elementos


class PermissaoTelaTextoTest(TelaTextoBase):
    def test_nao_autenticado_redireciona_para_login(self):
        resposta = self.client.get(self.url_tela())

        self.assertEqual(resposta.status_code, 302)
        self.assertIn('/accounts/login/', resposta['Location'])

    def test_post_nao_autenticado_redireciona_e_nao_grava(self):
        for nome in ('confirmar_pagina_ocr', 'editar_pagina_ocr'):
            with self.subTest(acao=nome):
                resposta = self.client.post(
                    self.url(nome, numero=1), {'texto': 'invasor'}
                )

                self.assertEqual(resposta.status_code, 302)
                self.assertIn('/accounts/login/', resposta['Location'])
                self.assertEqual(self.pagina(1).estado, ESTADO_NAO_CONFIRMADA)

    def test_usuario_sem_acesso_a_hierarquia_recebe_404(self):
        self.client.force_login(self.sem_acesso)

        resposta = self.client.get(self.url_tela())

        self.assertEqual(resposta.status_code, 404)

    def test_usuario_sem_acesso_nao_confirma_nem_edita(self):
        self.client.force_login(self.sem_acesso)

        for nome in ('confirmar_pagina_ocr', 'editar_pagina_ocr'):
            with self.subTest(acao=nome):
                resposta = self.client.post(
                    self.url(nome, numero=1), {'texto': 'invasor'}
                )

                self.assertEqual(resposta.status_code, 404)
                pagina = self.pagina(1)
                self.assertEqual(pagina.estado, ESTADO_NAO_CONFIRMADA)
                self.assertIsNone(pagina.texto_confirmado)

    def test_job_inexistente_recebe_404(self):
        self.client.force_login(self.dono)
        url = reverse('texto_job_ocr', kwargs={
            **self.kwargs_url(), 'job_id': uuid.uuid4(),
        })

        self.assertEqual(self.client.get(url).status_code, 404)

    def test_job_de_outro_documento_da_mesma_hierarquia_recebe_404(self):
        """O job tem de pertencer ao documento da URL (hierarquia completa)."""
        outro = Documento.objects.create(
            imovel=self.imovel, tipo=self.documento.tipo, numero='R-OUTRO',
            data=date(2024, 2, 2), cartorio=self.documento.cartorio,
            livro='1', folha='2',
        )
        self.client.force_login(self.dono)
        url = reverse('texto_job_ocr', kwargs={
            **self.kwargs_url(), 'documento_id': outro.pk,
        })

        self.assertEqual(self.client.get(url).status_code, 404)

    def test_get_nos_endpoints_de_acao_recebe_405(self):
        self.client.force_login(self.dono)

        for nome in ('confirmar_pagina_ocr', 'editar_pagina_ocr'):
            with self.subTest(acao=nome):
                resposta = self.client.get(self.url(nome, numero=1))

                self.assertEqual(resposta.status_code, 405)

    def test_post_na_tela_recebe_405(self):
        self.client.force_login(self.dono)

        self.assertEqual(self.client.post(self.url_tela()).status_code, 405)


class RenderTelaTextoTest(TelaTextoBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def test_renderiza_o_pdf_e_o_texto_da_pagina_pedida(self):
        resposta = self.client.get(self.url_tela(pagina=2))
        conteudo = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        # PDF à esquerda: o mecanismo existente (servir_documento_digital),
        # aberto na página pedida pelo parâmetro #page= do viewer do navegador.
        iframes = _elementos(
            conteudo, 'iframe', valores={'src': f'{self.url_pdf()}#page=2'}
        )
        self.assertEqual(len(iframes), 1)
        # Texto à direita, no textarea monoespaçado.
        areas = _elementos(conteudo, 'textarea', presentes=('name',), valores={'name': 'texto'})
        self.assertEqual(len(areas), 1)
        self.assertIn('font-monospace', _atributos(areas[0]).get('class', ''))
        self.assertEqual(resposta.context['pagina'].numero_pagina, 2)
        self.assertEqual(resposta.context['texto_atual'], TEXTOS[1])
        self.assertContains(resposta, TEXTOS[1])
        self.assertNotContains(resposta, TEXTOS[0])
        self.assertNotContains(resposta, TEXTOS[2])

    def test_textarea_exibe_o_texto_confirmado_quando_existe(self):
        services.confirmar_pagina(self.job, 1, self.dono, texto='texto já corrigido')

        resposta = self.client.get(self.url_tela(pagina=1))

        self.assertEqual(resposta.context['texto_atual'], 'texto já corrigido')
        self.assertContains(resposta, 'texto já corrigido')

    def test_sem_parametro_abre_a_primeira_pagina_pendente(self):
        services.confirmar_pagina(self.job, 1, self.dono)

        resposta = self.client.get(self.url_tela())

        self.assertEqual(resposta.context['pagina'].numero_pagina, 2)

    def test_sem_parametro_e_tudo_confirmado_abre_a_primeira(self):
        for numero in (1, 2, 3):
            services.confirmar_pagina(self.job, numero, self.dono)

        resposta = self.client.get(self.url_tela())

        self.assertEqual(resposta.context['pagina'].numero_pagina, 1)

    def test_pagina_invalida_recebe_404(self):
        # '9' * 5000: int() de string enorme levanta ValueError no Python 3.11+.
        for valor in ('0', '4', '99', 'abc', '-1', '1.5', '', '9' * 5000):
            with self.subTest(pagina=valor):
                resposta = self.client.get(self.url_tela(), {'pagina': valor})

                self.assertEqual(resposta.status_code, 404)

    def test_texto_do_ocr_e_escapado_no_textarea(self):
        PaginaOcr.objects.filter(ocr_job=self.job, numero_pagina=1).update(
            texto_ocr='</textarea><script>alert(1)</script>'
        )

        resposta = self.client.get(self.url_tela(pagina=1))

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, '<script>alert(1)</script>')
        self.assertContains(resposta, '&lt;/textarea&gt;&lt;script&gt;alert(1)')

    def test_textarea_preserva_a_quebra_de_linha_inicial(self):
        """O HTML descarta o 1º \\n depois de <textarea>; sem um \\n extra o
        texto que começa por quebra perderia a linha em branco ao salvar."""
        PaginaOcr.objects.filter(ocr_job=self.job, numero_pagina=1).update(
            texto_ocr='\nlinha inicial'
        )

        resposta = self.client.get(self.url_tela(pagina=1))

        self.assertRegex(
            resposta.content.decode(), r'<textarea[^>]*>\n\nlinha inicial'
        )

    def test_abas_por_pagina_com_estado_e_indicador_de_confirmadas(self):
        services.confirmar_pagina(self.job, 1, self.dono)
        services.editar_pagina(self.job, 2, 'segunda corrigida')

        resposta = self.client.get(self.url_tela(pagina=3))
        conteudo = resposta.content.decode()

        abas = _elementos(conteudo, 'a', presentes=('data-ocr-aba',))
        self.assertEqual([_atributos(a)['data-pagina'] for a in abas], ['1', '2', '3'])
        self.assertEqual(
            [_atributos(a)['data-estado'] for a in abas],
            [ESTADO_CONFIRMADA, ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA],
        )
        self.assertEqual(
            [_atributos(a)['href'] for a in abas],
            [self.url_tela(pagina=n) for n in (1, 2, 3)],
        )
        atuais = [a for a in abas if _atributos(a).get('aria-current') == 'page']
        self.assertEqual([_atributos(a)['data-pagina'] for a in atuais], ['3'])
        self.assertContains(resposta, '1 de 3 páginas confirmadas')
        self.assertEqual(resposta.context['confirmadas'], 1)
        self.assertEqual(resposta.context['total'], 3)

    def test_navegacao_anterior_e_proxima_entre_paginas(self):
        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()
        self.assertEqual(_elementos(conteudo, 'a', presentes=('data-ocr-anterior',)), [])
        proxima = _elementos(conteudo, 'a', presentes=('data-ocr-proxima',))
        self.assertEqual(_atributos(proxima[0])['href'], self.url_tela(pagina=2))

        conteudo = self.client.get(self.url_tela(pagina=3)).content.decode()
        self.assertEqual(_elementos(conteudo, 'a', presentes=('data-ocr-proxima',)), [])
        anterior = _elementos(conteudo, 'a', presentes=('data-ocr-anterior',))
        self.assertEqual(_atributos(anterior[0])['href'], self.url_tela(pagina=2))

    def test_estado_da_pagina_nao_depende_so_de_cor_ou_icone(self):
        """Cada aba carrega o estado também em texto para leitores de tela."""
        services.confirmar_pagina(self.job, 1, self.dono)

        resposta = self.client.get(self.url_tela(pagina=1))

        abas = _elementos(resposta.content.decode(), 'a', presentes=('data-ocr-aba',))
        self.assertIn('Confirmada', _texto_completo(abas[0]))
        self.assertIn('Não confirmada', _texto_completo(abas[1]))

    def test_exibe_quem_confirmou_e_quando(self):
        services.confirmar_pagina(self.job, 1, self.dono)
        pagina = self.pagina(1)

        resposta = self.client.get(self.url_tela(pagina=1))

        linha = _elementos(
            resposta.content.decode(), 'p', presentes=('data-ocr-auditoria-atual',)
        )
        self.assertEqual(len(linha), 1)
        texto = ' '.join(_texto_completo(linha[0]).split())
        self.assertIn('Confirmada por', texto)
        self.assertIn('dono-texto', texto)
        self.assertIn(filtro_date(pagina.confirmado_em, 'd/m/Y H:i'), texto)

    def test_tabela_de_auditoria_lista_todas_as_paginas(self):
        services.confirmar_pagina(self.job, 1, self.dono)

        resposta = self.client.get(self.url_tela(pagina=2))
        conteudo = resposta.content.decode()

        linhas = _elementos(conteudo, 'tr', presentes=('data-ocr-auditoria-pagina',))
        self.assertEqual(
            [_atributos(linha)['data-ocr-auditoria-pagina'] for linha in linhas],
            ['1', '2', '3'],
        )
        self.assertIn('dono-texto', _texto_completo(linhas[0]))
        self.assertIn('Confirmada', _texto_completo(linhas[0]))
        self.assertIn('Não confirmada', _texto_completo(linhas[1]))
        self.assertNotIn('dono-texto', _texto_completo(linhas[1]))

    def test_pagina_nao_confirmada_nao_mostra_auditoria_de_confirmacao(self):
        resposta = self.client.get(self.url_tela(pagina=1))

        self.assertEqual(
            _elementos(
                resposta.content.decode(), 'p', presentes=('data-ocr-auditoria-atual',)
            ),
            [],
        )

    def test_job_que_ainda_nao_concluiu_volta_para_o_upload_com_aviso(self):
        for status in (estados.PENDENTE, estados.EM_EXECUCAO, estados.FALHOU):
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)

                resposta = self.client.get(self.url_tela())

                self.assertRedirects(
                    resposta, self.url_upload(), fetch_redirect_response=False
                )
                self.assertTrue(self.mensagens(resposta))

    def test_job_texto_confirmado_abre_somente_leitura(self):
        PaginaOcr.objects.filter(ocr_job=self.job).update(confirmado_em=timezone.now())
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)

        resposta = self.client.get(self.url_tela(pagina=1))
        conteudo = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.context['editavel'])
        area = _elementos(conteudo, 'textarea', presentes=('name',))[0]
        self.assertIn('readonly', _atributos(area))
        self.assertEqual(
            _elementos(conteudo, 'button', presentes=('data-ocr-confirmar-pagina',)), []
        )
        self.assertEqual(
            _elementos(conteudo, 'button', presentes=('data-ocr-salvar-edicao',)), []
        )


class ContratoHtmlJsTest(TelaTextoBase):
    """O HTML oferece os ganchos que static/dominial/js/ocr_texto.js procura."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def test_pagina_carrega_o_js_e_oferece_os_ganchos_que_ele_usa(self):
        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()

        scripts = [_atributos(s)['src'] for s in _elementos(conteudo, 'script', presentes=('src',))]
        self.assertTrue(
            any(src.endswith('dominial/js/ocr_texto.js') for src in scripts), scripts
        )
        self.assertEqual(len(_elementos(conteudo, 'textarea', presentes=('data-ocr-texto-area',))), 1)
        self.assertEqual(len(_elementos(conteudo, 'form', presentes=('data-ocr-texto-form',))), 1)
        self.assertEqual(
            len(_elementos(conteudo, 'small', presentes=('data-ocr-nao-salvo', 'hidden'))), 1
        )
        # Confirmar todas / Reprocessar / Extrair campos: as 3 ações gerais.
        self.assertEqual(len(_elementos(conteudo, 'button', presentes=('data-ocr-acao-global',))), 3)

    def test_estaticos_da_tela_existem(self):
        for caminho in ('dominial/js/ocr_texto.js', 'dominial/css/ocr_texto.css'):
            with self.subTest(estatico=caminho):
                self.assertIsNotNone(finders.find(caminho))

    def test_regra_hidden_escopada_esta_no_css_da_tela(self):
        """Mesmo motivo do card (#260-A): .btn sobrepõe o [hidden] do navegador."""
        css = finders.find('dominial/css/ocr_texto.css')

        with open(css, encoding='utf-8') as arquivo:
            conteudo = arquivo.read()
        self.assertIn('[data-ocr-texto] [hidden]', conteudo)
        self.assertIn('display: none !important', conteudo)


class ConfirmarPaginaViewTest(TelaTextoBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def test_confirmar_grava_texto_e_auditoria_e_volta_para_a_mesma_pagina(self):
        resposta = self.client.post(
            self.url('confirmar_pagina_ocr', numero=1), {'texto': TEXTOS[0]}
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
            {'texto': 'segunda corrigida\r\ncom duas linhas'},
        )

        self.assertEqual(resposta.status_code, 302)
        pagina = self.pagina(2)
        self.assertEqual(pagina.texto_confirmado, 'segunda corrigida\ncom duas linhas')
        self.assertEqual(pagina.texto_ocr, TEXTOS[1])
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)

    def test_confirmar_sem_o_campo_texto_confirma_o_texto_vigente(self):
        resposta = self.client.post(self.url('confirmar_pagina_ocr', numero=3))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.pagina(3).texto_confirmado, TEXTOS[2])

    def test_editar_depois_de_confirmada_marca_editada_e_exige_reconfirmacao(self):
        self.client.post(self.url('confirmar_pagina_ocr', numero=1), {'texto': TEXTOS[0]})

        resposta = self.client.post(
            self.url('editar_pagina_ocr', numero=1), {'texto': 'primeira editada'}
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
        resposta = self.client.post(self.url('editar_pagina_ocr', numero=1))

        self.assertEqual(resposta.status_code, 400)
        pagina = self.pagina(1)
        self.assertEqual(pagina.estado, ESTADO_NAO_CONFIRMADA)
        self.assertIsNone(pagina.texto_confirmado)

    def test_post_em_job_fora_de_concluido_nao_grava_e_avisa(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)

        for nome in ('confirmar_pagina_ocr', 'editar_pagina_ocr'):
            with self.subTest(acao=nome):
                resposta = self.client.post(
                    self.url(nome, numero=1), {'texto': 'tarde demais'}
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
                        self.url(nome, numero=numero), {'texto': 'x'}
                    )

                    self.assertEqual(resposta.status_code, 404)

    def test_qualquer_usuario_com_acesso_ao_documento_confirma(self):
        """Quem tem acesso ao documento confirma: não há dono do job."""
        outro = User.objects.create_user(username='colega', password='senha-colega')
        UserTI.objects.create(user=outro, tis=self.ti)
        self.client.force_login(outro)

        resposta = self.client.post(self.url('confirmar_pagina_ocr', numero=1))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.pagina(1).confirmado_por, outro)
