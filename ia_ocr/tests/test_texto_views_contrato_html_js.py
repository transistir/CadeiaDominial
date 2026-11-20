"""Partes por cenário de ``test_texto_views``; coletadas pela fachada."""

from django.contrib.staticfiles import finders

from .test_ui_card_ocr import _atributos, _elementos

class ContratoHtmlJsTestParte:
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

    def test_css_da_tela_tem_a_classe_de_destaque_do_confirmar(self):
        css = finders.find('dominial/css/ocr_texto.css')

        with open(css, encoding='utf-8') as arquivo:
            conteudo = arquivo.read()
        self.assertIn('.btn-principal-destaque', conteudo)
        self.assertIn('font-size: 1.15em', conteudo)
        self.assertIn('padding: 14px 28px', conteudo)

