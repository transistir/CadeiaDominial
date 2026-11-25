"""
Issue #400 — PDF e Excel exportam SÓ o texto documental.

v4 (P1 #1/#2 do Greptile): o bloco ``[ANÁLISE — autor — data] … [/ANÁLISE]`` é
pendência de revisão, não texto do cartório — sai das duas exportações pela
mesma ``remover_analises`` usada pelo badge e pela gravação. Antes o texto ia
verbatim (regra 3 original do §5) e uma autoria forjada no textarea documental
chegava ao PDF/Excel.

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
from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
from dominial.services.observacoes_analise import registrar_analise
from dominial.tests.segregacao_fixtures import usuario_com_tis
from dominial.views import cadeia_dominial_views


TEXTO_DOCUMENTAL = 'Área remanescente de 55 ha 69 a 85 ca'
MARCADOR = '[ANÁLISE — fulano — 2026-11-25]'
ANALISE = 'Soma das áreas confere com o R.5.'
OBSERVACOES = registrar_analise(
    TEXTO_DOCUMENTAL,
    ANALISE,
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


class PdfSomenteDocumentalTest(_BaseExportacao400):
    def test_pdf_mostra_o_documental_e_omite_o_bloco_de_analise(self):
        contexto = CadeiaCompletaService(
            documentos_queryset=ESCOPO_GLOBAL,
        ).get_cadeia_completa(self.tis.id, self.imovel.id)

        html = render_to_string('dominial/cadeia_completa_pdf.html', contexto)

        self.assertIn(TEXTO_DOCUMENTAL, html)
        self.assertNotIn(MARCADOR, html)
        self.assertNotIn(ANALISE, html)
        self.assertNotIn('[/ANÁLISE]', html)

    def test_pdf_da_cadeia_dominial_tambem_omite_o_bloco_de_analise(self):
        # O outro template que usa ``texto_documental`` (linha do lançamento)
        # fica no caminho do PDF da tabela: sem este teste, um revert do filtro
        # vazaria a análise do revisor para o relatório.
        contexto = CadeiaDominialTabelaService(
            documentos_queryset=ESCOPO_GLOBAL,
        ).get_cadeia_dominial_tabela(self.tis.id, self.imovel.id, session={})

        html = render_to_string('dominial/cadeia_dominial_pdf.html', contexto)

        self.assertIn(TEXTO_DOCUMENTAL, html)
        self.assertNotIn(MARCADOR, html)
        self.assertNotIn(ANALISE, html)
        self.assertNotIn('[/ANÁLISE]', html)


class ExcelSomenteDocumentalTest(_BaseExportacao400):
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

    def test_excel_mostra_o_documental_e_omite_o_bloco_de_analise(self):
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
        self.assertNotIn(MARCADOR, texto)
        self.assertNotIn(ANALISE, texto)
        self.assertNotIn('[/ANÁLISE]', texto)
