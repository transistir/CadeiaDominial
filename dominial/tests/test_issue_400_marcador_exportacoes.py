"""
Issue #400 — PDF e Excel já imprimem ``Lancamento.observacoes`` cru: o
marcador ``[ANÁLISE — autor — data]`` precisa aparecer verbatim nas duas
exportações (§5, regra 3). Nenhuma alteração nesses arquivos — o teste prova
o comportamento existente contra a fixture real da cadeia.

Fixture no molde de ``test_issue_172_suprimir_troncos.py``:
``Lancamento.objects.bulk_create`` evita o signal de origens automáticas e
``cache.clear()`` no setUp porque o tronco principal é cacheado por imóvel.
"""

from datetime import date
from io import BytesIO

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.template.loader import render_to_string
from openpyxl import load_workbook

from dominial.managers import ESCOPO_GLOBAL
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
from dominial.services.observacoes_analise import registrar_analise
from dominial.tests.segregacao_fixtures import usuario_com_tis
from dominial.views import cadeia_dominial_views


TEXTO_DOCUMENTAL = 'Área remanescente de 55 ha 69 a 85 ca'
MARCADOR = '[ANÁLISE — fulano — 2026-11-25]'
OBSERVACOES = registrar_analise(
    TEXTO_DOCUMENTAL,
    'Soma das áreas confere com o R.5.',
    'fulano',
    date(2026, 11, 25),
)


class _BaseExportacao400(TestCase):
    def setUp(self):
        cache.clear()
        self.tis = TIs.objects.create(nome='TI 400', codigo='TI400', etnia='X')
        self.cartorio = Cartorios.objects.create(
            nome='Cartório 400', cns='400400', cidade='Cidade', estado='TS',
        )
        self.proprietario = Pessoas.objects.create(nome='Proprietário 400')
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Imóvel 400',
            proprietario=self.proprietario,
            matricula='M400',
            cartorio=self.cartorio,
        )
        tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        self.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')
        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=tipo_matricula,
            numero='M400',
            data=date(2020, 1, 10),
            cartorio=self.cartorio,
            livro='1',
            folha='1',
        )
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.documento,
                tipo=self.tipo_inicio,
                data=date(2020, 1, 10),
                cartorio_origem=self.cartorio,
                origem='',
                observacoes=OBSERVACOES,
            ),
        ])


class PdfMarcadorAnaliseTest(_BaseExportacao400):
    def test_pdf_mostra_documental_e_marcador_verbatim(self):
        contexto = CadeiaCompletaService(
            documentos_queryset=ESCOPO_GLOBAL,
        ).get_cadeia_completa(self.tis.id, self.imovel.id)

        html = render_to_string('dominial/cadeia_completa_pdf.html', contexto)

        self.assertIn(TEXTO_DOCUMENTAL, html)
        self.assertIn(MARCADOR, html)
        self.assertIn('Soma das áreas confere com o R.5.', html)


class ExcelMarcadorAnaliseTest(_BaseExportacao400):
    def _workbook(self):
        request = RequestFactory().get('/excel/')
        request.user = usuario_com_tis('user_test_400', self.tis)
        resposta = (
            cadeia_dominial_views.exportar_cadeia_dominial_excel.__wrapped__(
                request, self.tis.id, self.imovel.id,
            )
        )

        self.assertEqual(resposta.status_code, 200)
        return load_workbook(BytesIO(resposta.content))

    def test_excel_mostra_documental_e_marcador_em_celula(self):
        workbook = self._workbook()
        celulas = [
            str(cell.value)
            for ws in workbook.worksheets
            for row in ws.iter_rows()
            for cell in row
            if cell.value is not None
        ]
        texto = '\n'.join(celulas)

        self.assertIn(TEXTO_DOCUMENTAL, texto)
        self.assertIn(MARCADOR, texto)
