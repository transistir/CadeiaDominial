"""
Issue #271 — "memória" de Forma e Título da transmissão.

`autocomplete="off"` suprimia o `<datalist>` fixo em vários navegadores.
Agora os dois inputs apontam para datalists vazios que o
`forma_sugestoes.js` preenche com os valores mais usados (endpoint
`forma-autocomplete`), sempre recortados pelos imóveis do usuário.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from ..models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from ..tests.segregacao_fixtures import atribuir_tis

FORMAS_FIXAS = [
    "Compra e Venda", "Doação", "Permuta", "Cessão",
    "Inventário", "Arrematação", "Adjudicação",
]
JS_PATH = Path(settings.BASE_DIR) / "static" / "dominial" / "js" / "forma_sugestoes.js"


class _Base(TestCase):
    def setUp(self):
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_registro = LancamentoTipo.objects.create(tipo="registro")
        self.cartorio = Cartorios.objects.create(
            nome="Cartório 271", cns="CNS271271", cidade="São Paulo"
        )
        self.user, self.tis, self.imovel, self.documento = self._montar("u271a", "A")
        self.client = Client()
        self.client.login(username="u271a", password="senha271")

    def _montar(self, username, sufixo):
        user = User.objects.create_user(username=username, password="senha271")
        tis = TIs.objects.create(
            nome=f"TI 271 {sufixo}", codigo=f"TI271{sufixo}", etnia="Teste", estado="SP"
        )
        atribuir_tis(user, tis)
        pessoa = Pessoas.objects.create(nome=f"Proprietário {sufixo}")
        imovel = Imovel.objects.create(
            nome=f"Imóvel {sufixo}", matricula=f"271{sufixo}",
            terra_indigena_id=tis, proprietario=pessoa,
            tipo_documento_principal="matricula", cartorio=self.cartorio,
        )
        documento = Documento.objects.create(
            numero=f"271{sufixo}", tipo=self.tipo_matricula, imovel=imovel,
            cartorio=self.cartorio, data="2020-01-01", livro="1", folha="1",
        )
        return user, tis, imovel, documento

    def _lanc(self, documento=None, forma=None, titulo=None):
        self._n = getattr(self, "_n", 0) + 1
        return Lancamento.objects.create(
            documento=documento or self.documento, tipo=self.tipo_registro,
            numero_lancamento=str(self._n), data="2020-01-01",
            forma=forma, titulo=titulo,
        )


class TemplateDatalistTest(_Base):
    def _input(self, html, nome):
        m = re.search(rf'<input[^>]*name="{nome}"[^>]*>', html, re.DOTALL)
        self.assertIsNotNone(m, nome)
        return m.group(0)

    def _checar(self, response):
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        forma = self._input(html, "forma_transacao")
        titulo = self._input(html, "titulo_transacao")
        self.assertIn('list="formas-transacao"', forma)
        self.assertIn('list="titulos-transacao"', titulo)
        self.assertNotIn('autocomplete="off"', forma)
        self.assertNotIn('autocomplete="off"', titulo)
        self.assertIn('<datalist id="formas-transacao"></datalist>', html)
        self.assertIn('<datalist id="titulos-transacao"></datalist>', html)
        for valor in FORMAS_FIXAS:
            self.assertNotIn(f'<option value="{valor}"', html)
        self.assertIn("dominial/js/forma_sugestoes.js", html)

    def test_novo_lancamento(self):
        self._checar(self.client.get(
            reverse("novo_lancamento", args=[self.tis.id, self.imovel.id])))

    def test_edicao(self):
        lanc = self._lanc(forma="Doação", titulo="Escritura")
        self._checar(self.client.get(reverse(
            "editar_lancamento", args=[self.tis.id, self.imovel.id, lanc.id])))

    def test_pos_erro_de_validacao(self):
        self._lanc()  # número "1" já existe → POST duplicado cai no erro
        response = self.client.post(
            reverse("novo_lancamento", args=[self.tis.id, self.imovel.id]),
            {
                "tipo_lancamento": str(self.tipo_registro.id),
                "numero_lancamento": "1",
                "numero_lancamento_simples": "1",
                "forma_transacao": "Compra e Venda",
                "titulo_transacao": "Escritura Pública",
            },
        )
        self._checar(response)
        self.assertContains(response, 'value="Compra e Venda"')


class FormaAutocompleteEndpointTest(_Base):
    def setUp(self):
        super().setUp()
        self.url = reverse("forma-autocomplete")

    def _get(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return response.json()["results"]

    def test_exige_login(self):
        response = Client().get(self.url)
        self.assertIn(response.status_code, (302, 403))

    def test_ordena_por_contagem_e_ignora_vazios(self):
        for _ in range(3):
            self._lanc(forma="Doação")
        for _ in range(2):
            self._lanc(forma="Compra e Venda")
        self._lanc(forma="Permuta")
        self._lanc(forma="Arrematação")
        self._lanc(forma="")
        self._lanc(forma="   ")
        self._lanc(forma=None)
        self.assertEqual(self._get(), [
            {"valor": "Doação", "count": 3},
            {"valor": "Compra e Venda", "count": 2},
            {"valor": "Arrematação", "count": 1},
            {"valor": "Permuta", "count": 1},
        ])

    def test_respeita_q(self):
        self._lanc(forma="Compra e Venda")
        self._lanc(forma="Doação")
        self.assertEqual(self._get(q="compra"), [{"valor": "Compra e Venda", "count": 1}])

    def test_limite_de_20(self):
        for i in range(25):
            self._lanc(forma=f"Forma {i:02d}")
        self.assertEqual(len(self._get()), 20)

    def test_campo_titulo(self):
        self._lanc(forma="Doação", titulo="Escritura Pública")
        self._lanc(forma="Doação", titulo="Escritura Pública")
        self._lanc(forma="Doação", titulo="Formal de Partilha")
        self.assertEqual(self._get(campo="titulo"), [
            {"valor": "Escritura Pública", "count": 2},
            {"valor": "Formal de Partilha", "count": 1},
        ])

    def test_campo_invalido_400(self):
        response = self.client.get(self.url, {"campo": "invalido"})
        self.assertEqual(response.status_code, 400)

    def test_nao_vaza_valor_de_outro_usuario(self):
        _, _, _, doc_b = self._montar("u271b", "B")
        self._lanc(forma="Doação", titulo="Título A")
        self._lanc(documento=doc_b, forma="Segredo B", titulo="Título B")
        self.assertEqual(self._get(), [{"valor": "Doação", "count": 1}])
        self.assertEqual(self._get(campo="titulo"), [{"valor": "Título A", "count": 1}])

    def test_valor_com_html_volta_como_texto(self):
        self._lanc(forma="<script>alert(1)</script>")
        self.assertEqual(self._get(), [{"valor": "<script>alert(1)</script>", "count": 1}])


class FormaSugestoesJsTest(TestCase):
    def test_js_existe_e_nao_usa_innerhtml(self):
        self.assertTrue(JS_PATH.exists(), JS_PATH)
        js = JS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", js)
        self.assertIn("createElement('option')", js)
        self.assertIn("AbortController", js)
