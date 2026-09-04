"""
Issue #172 — Suprimir os rótulos "TRONCO PRINCIPAL" / "TRONCO SECUNDÁRIO {n}"
das exportações da cadeia dominial completa.

Decisão do cliente (confirmada nos comments da issue): ambos os rótulos são
conceitos internos do código, usados apenas para organizar documentos, e não
têm significado na cadeia dominial real. Os documentos de todos os troncos
PERMANECEM listados — apenas os títulos e a estatística "Troncos" saem.

Estes testes montam fixtures reais no banco, geram o contexto pelo serviço
real (`CadeiaCompletaService` — sem contexto fake), renderizam
`dominial/cadeia_completa_pdf.html` com `render_to_string` e também geram o
PDF binário real via WeasyPrint, extraindo o texto com `pypdf` (mesmo padrão
do `test_issue_145_pdf_averboes.py`).
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
    LancamentoPessoa,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from dominial.services.cadeia_completa_service import CadeiaCompletaService
from dominial.views.cadeia_dominial_views import HTML


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


class _BaseCadeia172(TestCase):
    def setUp(self):
        cache.clear()
        self.tis = TIs.objects.create(nome="TI 172", codigo="TI172", etnia="X")
        self.cartorio = Cartorios.objects.create(
            nome="Cartorio 172", cns="172172", cidade="Cidade", estado="TS"
        )
        self.proprietario = Pessoas.objects.create(
            nome="Proprietario 172", cpf="11122233344"
        )
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Fazenda Teste 172",
            proprietario=self.proprietario,
            matricula="M172",
            cartorio=self.cartorio,
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo="transcricao")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

        # Cadeia real: matrícula M172 -> transcrição T50 de origem. Ambos os
        # documentos entram no tronco principal (get_cadeia_completa).
        self.matricula = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="M172",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1",
        )
        self.transcricao = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_transcricao,
            numero="T50",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="2",
            folha="5",
        )
        # bulk_create para não disparar o signal de origens automáticas.
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.matricula,
                tipo=self.tipo_inicio,
                data=timezone.now().date(),
                cartorio_origem=self.cartorio,
                origem="T50",
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

        # --- Tronco secundário REAL -------------------------------------
        # Um imóvel distinto ("importado" na perspectiva de self.imovel)
        # com seu próprio documento e um lançamento com transmitente
        # rastreável. É um segundo tronco de documentos reais, sem mock.
        #
        # O fluxo público get_cadeia_completa NÃO alcança este documento:
        # CadeiaCompletaService._obter_troncos_secundarios_completos ainda
        # é um stub que retorna [] (troncos secundários não são expandidos
        # na exportação). Por isso o teste de tronco secundário monta o
        # contexto pelo método real _organizar_cadeia_hierarquica, que é
        # quem gera a seção .tronco-section e o título
        # "🌿 TRONCO SECUNDÁRIO 1" que o template precisa suprimir.
        self.imovel_secundario = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Fazenda Secundaria 172",
            proprietario=self.proprietario,
            matricula="M900",
            cartorio=self.cartorio,
        )
        self.doc_secundario = Documento.objects.create(
            imovel=self.imovel_secundario,
            tipo=self.tipo_transcricao,
            numero="T77",
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="7",
            folha="7",
        )
        lanc_secundario = Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.doc_secundario,
                tipo=self.tipo_inicio,
                numero_lancamento="T77",
                data=timezone.now().date(),
                cartorio_origem=self.cartorio,
                origem="",
            ),
        ])[0]
        self.pessoa_secundaria = Pessoas.objects.create(
            nome="TRANSMITENTE_TRONCO_SEC_172", cpf="55566677788"
        )
        LancamentoPessoa.objects.create(
            lancamento=lanc_secundario,
            pessoa=self.pessoa_secundaria,
            tipo="transmitente",
        )

    def _contexto(self):
        return CadeiaCompletaService().get_cadeia_completa(
            self.tis.id, self.imovel.id
        )

    def _contexto_com_tronco_secundario(self):
        """
        Contexto montado pelo método REAL `_organizar_cadeia_hierarquica`
        com DOIS troncos de documentos reais (principal: M172 + T50;
        secundário: T77). Reproduz a estrutura que o template recebe
        quando há troncos secundários, exercitando a supressão do rótulo
        "🌿 TRONCO SECUNDÁRIO 1" que o service coloca em `tronco.titulo`.
        """
        service = CadeiaCompletaService()
        service.imovel_atual = self.imovel
        cadeia = service._organizar_cadeia_hierarquica(
            [self.matricula, self.transcricao],
            [[self.doc_secundario]],
        )
        return {
            "tis": self.tis,
            "imovel": self.imovel,
            "cadeia_completa": cadeia,
            "estatisticas": service._calcular_estatisticas_completas(cadeia),
        }

    def _contexto_sequencia_personalizada(self):
        return CadeiaCompletaService().get_cadeia_completa_com_sequencia_personalizada(
            self.tis.id,
            self.imovel.id,
            f"{self.matricula.id},{self.transcricao.id}",
        )


class SuprimirRotulosTroncoTest(_BaseCadeia172):
    def test_pdf_nao_exibe_rotulos_tronco(self):
        """Nenhum dos dois rótulos aparece no HTML nem no PDF binário."""
        context = self._contexto()
        html, pdf_bytes = _gerar_pdf(context)
        texto_pdf = _texto_pdf(pdf_bytes)

        self.assertEqual(pdf_bytes[:4], b"%PDF")
        for token in ("TRONCO PRINCIPAL", "TRONCO SECUNDÁRIO", "TRONCO SECUNDARIO"):
            self.assertNotIn(token, html, f"'{token}' não deveria aparecer no HTML")
            self.assertNotIn(
                token, texto_pdf, f"'{token}' não deveria aparecer no PDF"
            )

    def test_pdf_nao_exibe_rotulos_com_tronco_secundario(self):
        """
        Mesmo com uma seção de tronco SECUNDÁRIO real na estrutura — cujo
        `titulo` vem do service como "🌿 TRONCO SECUNDÁRIO 1" — nenhum
        rótulo de tronco aparece no HTML nem no PDF binário.
        """
        context = self._contexto_com_tronco_secundario()

        # A fixture realmente produz o rótulo interno que deve ser suprimido.
        self.assertEqual(
            context["cadeia_completa"][1]["tipo"], "tronco_secundario"
        )
        self.assertIn(
            "TRONCO SECUNDÁRIO 1", context["cadeia_completa"][1]["titulo"]
        )

        html, pdf_bytes = _gerar_pdf(context)
        texto_pdf = _texto_pdf(pdf_bytes)

        self.assertEqual(pdf_bytes[:4], b"%PDF")
        for token in ("TRONCO PRINCIPAL", "TRONCO SECUNDÁRIO", "TRONCO SECUNDARIO"):
            self.assertNotIn(token, html, f"'{token}' não deveria aparecer no HTML")
            self.assertNotIn(
                token, texto_pdf, f"'{token}' não deveria aparecer no PDF"
            )

    def test_pdf_nao_exibe_rotulos_em_sequencia_personalizada(self):
        """Mesma supressão no caminho de sequência personalizada."""
        context = self._contexto_sequencia_personalizada()
        html, pdf_bytes = _gerar_pdf(context)
        texto_pdf = _texto_pdf(pdf_bytes)

        self.assertEqual(pdf_bytes[:4], b"%PDF")
        for token in ("TRONCO PRINCIPAL", "TRONCO SECUNDÁRIO", "TRONCO SECUNDARIO"):
            self.assertNotIn(token, html)
            self.assertNotIn(token, texto_pdf)

    def test_pdf_documentos_de_todos_os_troncos_permanecem(self):
        """
        Os documentos de TODOS os troncos continuam listados: os do tronco
        principal (M172, T50) e os do tronco secundário real (T77), com o
        conteúdo dos lançamentos do secundário (transmitente rastreável).
        """
        context = self._contexto_com_tronco_secundario()

        cadeia = context["cadeia_completa"]
        self.assertEqual(cadeia[0]["tipo"], "tronco_principal")
        self.assertEqual(cadeia[1]["tipo"], "tronco_secundario")
        # O secundário carrega mesmo o documento T77 (documento real).
        self.assertEqual(
            cadeia[1]["documentos"][0]["documento"].numero, "T77"
        )

        html, pdf_bytes = _gerar_pdf(context)
        texto_pdf = _texto_pdf(pdf_bytes)
        self.assertEqual(pdf_bytes[:4], b"%PDF")

        # Documentos dos dois troncos aparecem no HTML e no PDF binário.
        for numero in ("M172", "T50", "T77"):
            self.assertIn(numero, html, f"Documento {numero} sumiu do HTML")
            self.assertIn(numero, texto_pdf, f"Documento {numero} sumiu do PDF")

        # O lançamento do tronco secundário é renderizado (seu transmitente
        # aparece na tabela de lançamentos do documento T77).
        self.assertIn(
            "TRANSMITENTE_TRONCO_SEC_172",
            html,
            "O lançamento do tronco secundário não foi renderizado no HTML",
        )

    def test_estatisticas_sem_troncos(self):
        """O card 'Troncos' sai das estatísticas; os demais permanecem."""
        context = self._contexto_com_tronco_secundario()
        # Estrutura com 2 troncos reais — o service ainda conta total_troncos.
        self.assertEqual(context["estatisticas"]["total_troncos"], 2)
        html, _ = _gerar_pdf(context)

        self.assertIn("Estatísticas da Cadeia Completa", html)
        self.assertNotIn(">Troncos<", html)
        self.assertNotIn("estatisticas.total_troncos", html)
        # Estatísticas mantidas.
        for label in ("Documentos", "Lançamentos", "Importados"):
            self.assertIn(f">{label}<", html)
