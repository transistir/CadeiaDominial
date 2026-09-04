"""
Issue #166 — usar a sigla "CRI" no lugar de "Cartório de Registro de Imóveis"
nas exportações (Excel e PDF completo).

Escopo: sigla nos valores + rótulos, APENAS nas exportações. A UI de cadastro
continua exibindo o nome por extenso (decisão da issue #50). Models,
migrations e dados não são alterados.
"""

from io import BytesIO
from types import SimpleNamespace

from django.core.cache import cache
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone
from openpyxl import load_workbook

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from dominial.utils.formatacao_utils import abreviar_cartorio
from dominial.views import cadeia_dominial_views


class AbreviarCartorioTest(SimpleTestCase):
    """Testes unitários da função utilitária `abreviar_cartorio`."""

    def test_prefixo_simples(self):
        self.assertEqual(
            abreviar_cartorio("Cartório de Registro de Imóveis de Prado"),
            "CRI de Prado",
        )

    def test_prefixo_com_comarca(self):
        self.assertEqual(
            abreviar_cartorio(
                "Cartório de Registro de Imóveis da Comarca de Teodoro Sampaio"
            ),
            "CRI da Comarca de Teodoro Sampaio",
        )

    def test_nome_sem_prefixo_fica_inalterado(self):
        self.assertEqual(
            abreviar_cartorio("2º Ofício de Notas de Belém"),
            "2º Ofício de Notas de Belém",
        )

    def test_prefixo_em_caixa_alta_preserva_caixa_do_resto(self):
        self.assertEqual(
            abreviar_cartorio("CARTÓRIO DE REGISTRO DE IMÓVEIS DE PRADO"),
            "CRI DE PRADO",
        )

    def test_prefixo_sem_resto(self):
        self.assertEqual(
            abreviar_cartorio("Cartório de Registro de Imóveis"),
            "CRI",
        )

    def test_none_fica_inalterado(self):
        self.assertIsNone(abreviar_cartorio(None))

    def test_string_vazia_fica_inalterada(self):
        self.assertEqual(abreviar_cartorio(""), "")

    def test_variante_do_registro_nao_casa(self):
        self.assertEqual(
            abreviar_cartorio("Cartório do Registro de Imóveis de X"),
            "Cartório do Registro de Imóveis de X",
        )


class AbreviarCartorioTemplatetagTest(SimpleTestCase):
    """O filtro `abreviar_cartorio` registrado em `dominial_extras`."""

    def _render(self, valor):
        template = Template(
            "{% load dominial_extras %}{{ valor|abreviar_cartorio }}"
        )
        return template.render(Context({"valor": valor}))

    def test_filtro_abrevia_prefixo(self):
        self.assertEqual(
            self._render("Cartório de Registro de Imóveis de Prado"),
            "CRI de Prado",
        )

    def test_filtro_mantem_nome_sem_prefixo(self):
        self.assertEqual(
            self._render("2º Ofício de Notas de Belém"),
            "2º Ofício de Notas de Belém",
        )


class ExportacaoExcelUsaSiglaCRITest(TestCase):
    """A planilha exportada deve trazer a sigla CRI nos valores e no cabeçalho."""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

        self.tis = TIs.objects.create(
            nome="TI Teste 166", codigo="TI166", etnia="Teste"
        )
        self.cartorio = Cartorios.objects.create(
            nome="Cartório de Registro de Imóveis de Prado",
            cns="166166",
            cidade="Prado",
            estado="BA",
        )
        self.proprietario = Pessoas.objects.create(
            nome="Proprietário 166", cpf="55566677788"
        )
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel Teste 166",
            proprietario=self.proprietario,
            matricula="M700",
            cartorio=self.cartorio,
        )

        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="M700",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1",
        )
        # bulk_create para não disparar o signal de processamento de origens.
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.documento,
                tipo=self.tipo_inicio,
                data=timezone.now().date(),
                cartorio_origem=self.cartorio,
                origem="",
            ),
        ])

    def _request(self, path):
        request = self.factory.get(path)
        request.user = SimpleNamespace(is_authenticated=True)
        return request

    def test_excel_usa_sigla_cri_no_valor_e_no_cabecalho(self):
        response = cadeia_dominial_views.exportar_cadeia_dominial_excel.__wrapped__(
            self._request("/excel/"), self.tis.id, self.imovel.id
        )
        self.assertEqual(response.status_code, 200)

        workbook = load_workbook(BytesIO(response.content))
        ws = workbook.active
        valores = [
            cell.value
            for linha in ws.iter_rows()
            for cell in linha
            if isinstance(cell.value, str)
        ]

        # Valor da célula de cartório abreviado.
        self.assertIn("CRI de Prado", valores)
        # Cabeçalho detalhado usa 'CRI' e não mais 'Cartório'.
        self.assertIn("CRI", valores)
        self.assertNotIn("Cartório", valores)

        # O bloco de informações básicas do imóvel permanece por extenso.
        self.assertEqual(ws["B7"].value, "Cartório de Registro de Imóveis de Prado")
