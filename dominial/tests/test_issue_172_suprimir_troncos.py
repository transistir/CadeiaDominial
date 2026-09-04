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

    def _contexto(self):
        return CadeiaCompletaService().get_cadeia_completa(
            self.tis.id, self.imovel.id
        )

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

    def test_pdf_nao_exibe_rotulos_em_sequencia_personalizada(self):
        """Mesma supressão no caminho de sequência personalizada."""
        context = self._contexto_sequencia_personalizada()
        html, pdf_bytes = _gerar_pdf(context)
        texto_pdf = _texto_pdf(pdf_bytes)

        self.assertEqual(pdf_bytes[:4], b"%PDF")
        for token in ("TRONCO PRINCIPAL", "TRONCO SECUNDÁRIO", "TRONCO SECUNDARIO"):
            self.assertNotIn(token, html)
            self.assertNotIn(token, texto_pdf)

    def test_pdf_documentos_permanecem(self):
        """Os documentos de todos os troncos continuam listados."""
        context = self._contexto()
        html, pdf_bytes = _gerar_pdf(context)
        texto_pdf = _texto_pdf(pdf_bytes)

        # Ambos os documentos da cadeia devem aparecer no HTML e no PDF.
        for numero in ("M172", "T50"):
            self.assertIn(numero, html, f"Documento {numero} sumiu do HTML")
            self.assertIn(numero, texto_pdf, f"Documento {numero} sumiu do PDF")

    def test_estatisticas_sem_troncos(self):
        """O card 'Troncos' sai das estatísticas; os demais permanecem."""
        context = self._contexto()
        html, _ = _gerar_pdf(context)

        self.assertIn("Estatísticas da Cadeia Completa", html)
        self.assertNotIn(">Troncos<", html)
        self.assertNotIn("estatisticas.total_troncos", html)
        # Estatísticas mantidas.
        for label in ("Documentos", "Lançamentos", "Importados"):
            self.assertIn(f">{label}<", html)
