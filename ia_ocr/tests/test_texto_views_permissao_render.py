"""Partes por cenário de ``test_texto_views``; coletadas pela fachada."""

import uuid
from datetime import date

from django.template.defaultfilters import date as filtro_date
from django.urls import reverse
from django.utils import timezone

from dominial.models import Documento
from ia_ocr import estados, services
from ia_ocr.models import ESTADO_CONFIRMADA, ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA, OcrJob, PaginaOcr

from .base_texto import TEXTOS, _texto_completo
from .test_ui_card_ocr import _atributos, _elementos


class PermissaoTelaTextoTestParte:
    def test_nao_autenticado_redireciona_para_login(self):
        resposta = self.client.get(self.url_tela())

        self.assertEqual(resposta.status_code, 302)
        self.assertIn('/accounts/login/', resposta['Location'])

    def test_post_nao_autenticado_redireciona_e_nao_grava(self):
        for nome in ('confirmar_pagina_ocr', 'editar_pagina_ocr'):
            with self.subTest(acao=nome):
                resposta = self.client.post(
                    self.url(nome, numero=1),
                    {'texto': 'invasor', 'versao': self.versao(1)},
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
                    self.url(nome, numero=1),
                    {'texto': 'invasor', 'versao': self.versao(1)},
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


class RenderTelaTextoTestParte:
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def test_renderiza_o_texto_da_pagina_pedida_e_link_para_o_pdf(self):
        resposta = self.client.get(self.url_tela(pagina=2))
        conteudo = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        # Sem PDF embutido: o viewer nativo abria o diálogo de impressão.
        self.assertEqual(_elementos(conteudo, 'iframe'), [])
        links = _elementos(
            conteudo, 'a',
            valores={'href': f'{self.url_pdf()}#page=2', 'target': '_blank'},
        )
        self.assertEqual(len(links), 1)
        self.assertNotIn(f'href="{self.url_pdf()}"', conteudo)
        self.assertEqual(_atributos(links[0]).get('rel'), 'noopener')
        self.assertIn('Abrir o PDF em nova aba', _texto_completo(links[0]))
        # Texto em coluna única, no textarea monoespaçado.
        areas = _elementos(conteudo, 'textarea', presentes=('name',), valores={'name': 'texto'})
        self.assertEqual(len(areas), 1)
        self.assertIn('font-monospace', _atributos(areas[0]).get('class', ''))
        self.assertEqual(resposta.context['pagina'].numero_pagina, 2)
        self.assertEqual(resposta.context['texto_atual'], TEXTOS[1])
        self.assertContains(resposta, TEXTOS[1])
        self.assertNotContains(resposta, TEXTOS[0])
        self.assertNotContains(resposta, TEXTOS[2])

    def test_instrucao_e_texto_vem_antes_do_cta_de_confirmar(self):
        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()

        instrucao = conteudo.index('data-ocr-instrucao')
        area = conteudo.index('data-ocr-texto-area')
        confirmar = conteudo.index('data-ocr-confirmar-pagina')

        self.assertLess(instrucao, area)
        self.assertLess(area, confirmar)

    def test_pagina_editada_avisa_acima_do_texto_e_destaca_o_confirmar(self):
        services.editar_pagina(self.job, 1, 'primeira editada')
        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()

        aviso = conteudo.index('data-ocr-aviso-editada')
        area = conteudo.index('data-ocr-texto-area')
        self.assertLess(aviso, area)
        botoes = _elementos(conteudo, 'button', presentes=('data-ocr-confirmar-pagina',))
        self.assertEqual(len(botoes), 1)
        classes = _atributos(botoes[0]).get('class', '').split()
        self.assertIn('btn-success', classes)
        self.assertIn('btn-principal-destaque', classes)
        self.assertNotIn('btn-lg', classes)

    def test_pagina_limpa_nao_destaca_o_confirmar(self):
        conteudo = self.client.get(self.url_tela(pagina=2)).content.decode()

        botoes = _elementos(conteudo, 'button', presentes=('data-ocr-confirmar-pagina',))
        self.assertEqual(len(botoes), 1)
        classes = _atributos(botoes[0]).get('class', '').split()
        self.assertIn('btn-success', classes)
        self.assertNotIn('btn-principal-destaque', classes)

    def test_salvar_edicao_usa_o_botao_secundario_do_projeto(self):
        conteudo = self.client.get(self.url_tela(pagina=1)).content.decode()

        botoes = _elementos(conteudo, 'button', presentes=('data-ocr-salvar-edicao',))
        self.assertEqual(len(botoes), 1)
        classes = _atributos(botoes[0]).get('class', '').split()
        self.assertIn('btn-secondary', classes)
        self.assertNotIn('btn-outline-secondary', classes)

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

