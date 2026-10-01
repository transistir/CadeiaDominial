"""
Issue #13 — exibir a Área (ha) no padrão brasileiro (vírgula, 4 casas
decimais) nas tabelas HTML da Cadeia Dominial Geral e do Documento
Detalhado.

`Lancamento.area` é um `DecimalField(max_digits=12, decimal_places=4,
null=True, blank=True)`. Os dois templates exibiam o valor com
`{{ lancamento.area|default_if_none:"-" }}`, que usa a formatação padrão
do Python para Decimal — ponto como separador decimal (ex.: "0.0000").
A correção é só de EXIBIÇÃO: o helper `formatar_area_ha`
(`dominial/utils/formatacao_utils.py`) e o filtro de template `area_ha`
(`dominial/templatetags/dominial_extras.py`) trocam o separador decimal
para vírgula (padrão brasileiro), sem alterar o valor persistido no banco
nem a função `formatar_area` já existente (usada em outro lugar).
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

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
from dominial.services.cadeia_completa_service import CadeiaCompletaService
from dominial.services.cadeia_dominial_tabela_service import (
    CadeiaDominialTabelaService,
)
from dominial.utils.formatacao_utils import formatar_area_ha


class FormatarAreaHaTest(SimpleTestCase):
    """Testes unitários da função utilitária `formatar_area_ha`."""

    def test_zero_decimal_exibe_traco(self):
        # Decisão Hiure (10/09/2026): área zerada é exibida como "-",
        # não como "0,0000".
        self.assertEqual(formatar_area_ha(Decimal("0.0000")), "-")

    def test_zero_inteiro_exibe_traco(self):
        self.assertEqual(formatar_area_ha(Decimal("0")), "-")

    def test_zero_int_python_exibe_traco(self):
        self.assertEqual(formatar_area_ha(0), "-")

    def test_zero_float_exibe_traco(self):
        self.assertEqual(formatar_area_ha(0.0), "-")

    def test_zero_string_exibe_traco(self):
        self.assertEqual(formatar_area_ha("0"), "-")
        self.assertEqual(formatar_area_ha("0.0000"), "-")

    def test_zero_com_padrao_customizado(self):
        self.assertEqual(formatar_area_ha(Decimal("0"), padrao="N/A"), "N/A")

    def test_valor_sem_separador_de_milhar(self):
        self.assertEqual(formatar_area_ha(Decimal("1234.5")), "1234,5000")

    def test_valor_grande_sem_milhar_e_com_quatro_decimais(self):
        self.assertEqual(formatar_area_ha(Decimal("12345.6789")), "12345,6789")

    def test_string_numerica_e_convertida(self):
        self.assertEqual(formatar_area_ha("1234.5"), "1234,5000")

    def test_int_e_convertido(self):
        self.assertEqual(formatar_area_ha(10), "10,0000")

    def test_float_sem_ruido_binario(self):
        # 0.1 + 0.2 tem ruído binário em float puro (0.30000000000000004);
        # a conversão via Decimal(str(valor)) evita que esse ruído vaze
        # para a exibição.
        self.assertEqual(formatar_area_ha(0.1 + 0.2), "0,3000")

    def test_none_retorna_padrao(self):
        self.assertEqual(formatar_area_ha(None), "-")

    def test_string_vazia_retorna_padrao(self):
        self.assertEqual(formatar_area_ha(""), "-")

    def test_padrao_customizado_para_none(self):
        self.assertEqual(formatar_area_ha(None, padrao="N/A"), "N/A")

    def test_padrao_customizado_para_string_vazia(self):
        self.assertEqual(formatar_area_ha("", padrao="N/A"), "N/A")

    def test_valor_invalido_retorna_padrao(self):
        self.assertEqual(formatar_area_ha("abc"), "-")

    def test_valor_invalido_com_padrao_customizado(self):
        self.assertEqual(formatar_area_ha("abc", padrao="N/A"), "N/A")

    def test_valores_nao_finitos_retornam_padrao(self):
        for valor in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(valor=valor):
                self.assertEqual(formatar_area_ha(valor), "-")

    def test_nao_altera_formatar_area_existente(self):
        """`formatar_area` (com sufixo " ha" e 2 casas) continua intacta."""
        from dominial.utils.formatacao_utils import formatar_area

        self.assertEqual(formatar_area(Decimal("1234.5")), "1.234,50 ha")
        self.assertEqual(formatar_area(None), "0,00 ha")


class AreaHaTemplatetagTest(SimpleTestCase):
    """O filtro `area_ha` registrado em `dominial_extras`."""

    def _render(self, valor):
        template = Template("{% load dominial_extras %}{{ valor|area_ha }}")
        return template.render(Context({"valor": valor}))

    def _render_com_padrao(self, valor, padrao):
        template = Template(
            '{% load dominial_extras %}{{ valor|area_ha:padrao }}'
        )
        return template.render(Context({"valor": valor, "padrao": padrao}))

    def test_filtro_area_zerada_exibe_traco(self):
        self.assertEqual(self._render(Decimal("0.0000")), "-")

    def test_filtro_formata_valor_sem_milhar(self):
        self.assertEqual(self._render(Decimal("12345.6789")), "12345,6789")

    def test_filtro_none_retorna_traco(self):
        self.assertEqual(self._render(None), "-")

    def test_filtro_aceita_padrao_customizado(self):
        self.assertEqual(self._render_com_padrao(None, "N/A"), "N/A")


class AreaHaTabelasIntegracaoTest(TestCase):
    """
    Integração: monta fixtures reais no banco e renderiza as DUAS telas
    afetadas — Cadeia Dominial Geral (`cadeia_dominial_tabela.html`) e
    Documento Detalhado (`documento_detalhado.html`) — confirmando que o
    formato "cru" do Decimal (bug original, "0.0000") não aparece mais e
    que área zerada sai como "-" (decisão Hiure, 10/09/2026), nunca como
    "0,0000".
    """

    def setUp(self):
        # LocMemCache é compartilhado entre testes no mesmo processo; sem
        # isto, o cache de tronco principal por imovel_id poderia vazar
        # entre testes (mesmo padrão de test_exportacao_cadeia.py).
        cache.clear()

        self.user = User.objects.create_user(
            username="areapt13", password="areapt13pass"
        )
        self.client = Client()
        self.client.force_login(self.user)

        self.tis = TIs.objects.create(nome="TI 13", codigo="TI13", etnia="Teste")
        self.cartorio = Cartorios.objects.create(
            nome="Cartorio 13", cns="130013", cidade="Cidade", estado="TS"
        )
        self.proprietario = Pessoas.objects.create(
            nome="Proprietario 13", cpf="11122233355"
        )
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Fazenda Teste 13",
            proprietario=self.proprietario,
            matricula="M13",
            cartorio=self.cartorio,
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo="averbacao")

        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="M13",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1",
        )

        # bulk_create para não disparar o signal de processamento de
        # origens (mesmo padrão de test_issue_166_cri_export.py e
        # test_issue_172_suprimir_troncos.py). Um lançamento com area=0 e
        # outro com area=None e um terceiro não-zero, no mesmo documento.
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.documento,
                tipo=self.tipo_inicio,
                numero_lancamento="M13",
                data=timezone.now().date(),
                cartorio_origem=self.cartorio,
                origem="",
                area=Decimal("0"),
            ),
            Lancamento(
                documento=self.documento,
                tipo=self.tipo_averbacao,
                numero_lancamento="AV1M13",
                data=timezone.now().date(),
                origem="",
                area=None,
            ),
            Lancamento(
                documento=self.documento,
                tipo=self.tipo_averbacao,
                numero_lancamento="AV2M13",
                data=timezone.now().date(),
                origem="",
                area=Decimal("1234.5678"),
            ),
        ])

    def test_cadeia_dominial_geral_exibe_area_no_padrao_brasileiro(self):
        url = reverse(
            "cadeia_dominial_tabela",
            kwargs={"tis_id": self.tis.id, "imovel_id": self.imovel.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        # Área zerada sai como "-" na célula da coluna "Área (ha)"; o
        # formato "cru" do Decimal ("0.0000") e o "0,0000" antigo não
        # aparecem mais.
        self.assertIn("<td>-</td>", html)
        self.assertIn("<td>1234,5678</td>", html)
        self.assertNotIn("0.0000", html)
        self.assertNotIn("0,0000", html)
        self.assertNotIn("1.234,5678", html)

    def test_documento_detalhado_exibe_area_no_padrao_brasileiro(self):
        url = reverse(
            "documento_detalhado",
            kwargs={
                "tis_id": self.tis.id,
                "imovel_id": self.imovel.id,
                "documento_id": self.documento.id,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        self.assertIn("<td>-</td>", html)
        self.assertIn("<td>1234,5678</td>", html)
        self.assertNotIn("0.0000", html)
        self.assertNotIn("0,0000", html)
        self.assertNotIn("1.234,5678", html)

    def test_templates_pdf_usam_o_filtro_de_area(self):
        contextos = (
            (
                "dominial/cadeia_dominial_pdf.html",
                CadeiaDominialTabelaService().get_cadeia_dominial_tabela(
                    self.tis.id, self.imovel.id, session={}
                ),
            ),
            (
                "dominial/cadeia_completa_pdf.html",
                CadeiaCompletaService().get_cadeia_completa(
                    self.tis.id, self.imovel.id
                ),
            ),
        )

        for template, contexto in contextos:
            with self.subTest(template=template):
                html = render_to_string(template, contexto)
                self.assertIn("<td>1234,5678</td>", html)
                self.assertNotIn("<td>1234.5678</td>", html)
                self.assertNotIn("<td>1.234,5678</td>", html)
