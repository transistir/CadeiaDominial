"""
Issue #145 — Regressão: a exportação completa em PDF omitia os textos das
averbações registradas em documentos tipo transcrição.

Contexto do bug (produção): imóvel 499 / TI 67 (Fazenda Monte Alto,
matrícula M29718), 7 lançamentos `averbacao` com `descricao` preenchida.
Na tela os textos apareciam; no PDF as células saíam vazias / com "-".

Estes testes montam fixtures reais no banco, geram o contexto pelo serviço
real (`CadeiaCompletaService.get_cadeia_completa` — sem contexto fake),
renderizam `dominial/cadeia_completa_pdf.html` com `render_to_string` e
também geram o PDF real via WeasyPrint, extraindo o texto do binário com
`pypdf`. Servem de guarda de regressão: o token da descrição precisa estar
presente tanto no HTML quanto no PDF binário.

Diagnóstico (ver docstrings de cada teste):

* Averbação em documento tipo **matrícula**: o texto sempre apareceu no HTML
  e no PDF binário. O bug nunca ocorreu aqui — a hipótese de regressão de
  WeasyPrint/pydyf não se sustentava para matrículas.
* Averbação em documento tipo **transcrição**: o texto sumia já no HTML
  gerado por `render_to_string`, antes de o WeasyPrint entrar em cena. A
  causa era a condição do template
  `templates/dominial/cadeia_completa_pdf.html`
  (`... and item.documento.tipo.tipo != 'transcricao'`), que para
  transcrições trocava a coluna da descrição pelas colunas de transmissão
  (forma/título/cartório/...), todas vazias numa averbação. O template da
  tela (`cadeia_dominial_tabela.html`) não tinha essa restrição, por isso a
  tela mostrava o texto e o PDF não. O fix alinhou a condição do PDF à da
  tela: averbação sempre renderiza a descrição.
"""

import re
from io import BytesIO

from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import TestCase
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
from dominial.views.cadeia_dominial_views import HTML


def _texto_longo(token):
    """Descrição de averbação com > 100 chars e um token único e rastreável."""
    corpo = (
        f"{token}: Retificacao de area e de perimetro do imovel, com "
        "fundamento no art. 213 da Lei 6.015/73 e memorial descritivo "
        "aprovado pelo INCRA, alterando a area registrada de 100,0000 ha "
        "para 98,7654 ha, sem alteracao de titularidade dominial."
    )
    assert len(corpo) > 100
    return corpo


def _gerar_pdf(context):
    html = render_to_string("dominial/cadeia_completa_pdf.html", context)
    css_path = (
        settings.STATICFILES_DIRS[0]
        / "dominial"
        / "css"
        / "cadeia_completa_pdf.css"
    )
    pdf_bytes = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf(
        stylesheets=[str(css_path)] if css_path.exists() else None
    )
    return html, pdf_bytes


def _texto_pdf(pdf_bytes):
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    bruto = "\n".join(p.extract_text() or "" for p in reader.pages)
    return re.sub(r"\s+", " ", bruto)


class _BaseCadeia145(TestCase):
    def setUp(self):
        cache.clear()
        self.tis = TIs.objects.create(nome="TI 145", codigo="TI145", etnia="X")
        self.cartorio = Cartorios.objects.create(
            nome="Cartorio 145", cns="145145", cidade="Cidade", estado="TS"
        )
        self.proprietario = Pessoas.objects.create(
            nome="Proprietario 145", cpf="99988877766"
        )
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Fazenda Monte Alto (teste)",
            proprietario=self.proprietario,
            matricula="M29718",
            cartorio=self.cartorio,
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo="transcricao")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        self.tipo_averbacao = LancamentoTipo.objects.create(
            tipo="averbacao", requer_descricao=True
        )

    def _contexto(self):
        return CadeiaCompletaService().get_cadeia_completa(
            self.tis.id, self.imovel.id
        )

    @staticmethod
    def _descricoes_no_contexto(context):
        return [
            (item["documento"].tipo.tipo, lanc.tipo.tipo, lanc.descricao or "")
            for tronco in context["cadeia_completa"]
            for item in tronco["documentos"]
            for lanc in item["lancamentos"]
        ]


class AverbacaoEmMatriculaTest(_BaseCadeia145):
    """
    SANIDADE: averbação numa MATRÍCULA aparece tanto no HTML quanto no PDF
    binário. Comprova que a hipótese "regressão da lib omite averbação" não
    se sustentava para matrículas — o problema estava restrito a transcrições.
    """

    TOKEN = "TOKEN_AVERBACAO_145_MATRICULA"

    def setUp(self):
        super().setUp()
        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="M29718",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1",
        )
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.documento,
                tipo=self.tipo_inicio,
                data=timezone.now().date(),
                cartorio_origem=self.cartorio,
                origem="",
            ),
        ])
        Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_averbacao,
            numero_lancamento="AV1M29718",
            data=timezone.now().date(),
            descricao=_texto_longo(self.TOKEN),
        )

    def test_averbacao_em_matricula_aparece_no_html_e_no_pdf(self):
        context = self._contexto()
        html, pdf_bytes = _gerar_pdf(context)
        texto_pdf = _texto_pdf(pdf_bytes)

        self.assertEqual(pdf_bytes[:4], b"%PDF")
        self.assertIn(self.TOKEN, html)
        self.assertIn(self.TOKEN, texto_pdf)


class AverbacaoEmTranscricaoTest(_BaseCadeia145):
    """
    REGRESSÃO #145: cadeia real matrícula -> transcrição de origem, com a
    averbação de descrição longa registrada NA TRANSCRIÇÃO.

    O texto:
      * ESTAVA no contexto do serviço (`item['lancamentos']`);
      * SUMIA já no HTML de `render_to_string('dominial/cadeia_completa_pdf.html')`,
        antes do WeasyPrint.
    A causa era a condição do template
    `templates/dominial/cadeia_completa_pdf.html`:
        {% if lancamento.tipo.tipo == 'averbacao'
              and item.documento.tipo.tipo != 'transcricao' %}
    Para transcrição o `else` renderizava as colunas de transmissão
    (forma/título/cartório/livro/folha/data) — todas vazias numa averbação —
    e nunca imprimia `lancamento.descricao`. O fix removeu a restrição a
    transcrições, alinhando a condição à do template da tela; este teste
    garante que o token da descrição aparece no HTML e no PDF binário.
    """

    TOKEN = "TOKEN_AVERBACAO_145_TRANSCRICAO"

    def setUp(self):
        super().setUp()
        self.matricula = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="M29718",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1",
        )
        self.transcricao = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_transcricao,
            numero="T90",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="2",
            folha="5",
        )
        # Início da matrícula aponta textualmente para "T90" (bulk_create p/
        # não disparar o signal de origens automáticas, que criaria um T90
        # duplicado).
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.matricula,
                tipo=self.tipo_inicio,
                data=timezone.now().date(),
                cartorio_origem=self.cartorio,
                origem="T90",
            ),
        ])
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.transcricao,
                tipo=self.tipo_inicio,
                data=timezone.now().date(),
                cartorio_origem=self.cartorio,
                origem="",
            ),
        ])
        # Averbação com descrição longa NA TRANSCRIÇÃO.
        self.averbacao = Lancamento.objects.create(
            documento=self.transcricao,
            tipo=self.tipo_averbacao,
            numero_lancamento="AV1T90",
            data=timezone.now().date(),
            descricao=_texto_longo(self.TOKEN),
        )

    def test_averbacao_em_transcricao_sumida_do_pdf(self):
        context = self._contexto()

        descricoes = self._descricoes_no_contexto(context)
        token_no_contexto = any(
            self.TOKEN in descricao for _, _, descricao in descricoes
        )

        html, pdf_bytes = _gerar_pdf(context)
        texto_pdf = _texto_pdf(pdf_bytes)

        self.assertEqual(pdf_bytes[:4], b"%PDF")

        # A averbação e sua descrição chegam ao contexto do serviço.
        self.assertTrue(
            token_no_contexto,
            "A averbação com descrição não chegou ao contexto do serviço.",
        )

        # Guarda de regressão: a descrição da averbação em transcrição deve
        # aparecer no HTML do PDF (como aparece na tela). Antes do fix a
        # condição do template a descartava para documentos tipo transcrição.
        self.assertIn(
            self.TOKEN,
            html,
            "REGRESSÃO #145: a descrição da averbação em transcrição não foi "
            "renderizada em cadeia_completa_pdf.html.",
        )
        self.assertIn(self.TOKEN, texto_pdf)
