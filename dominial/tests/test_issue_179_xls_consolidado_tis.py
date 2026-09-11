"""
Issue #179 — export em Excel consolidado por Terra Indígena: um único
arquivo com a cadeia dominial completa de TODOS os imóveis de uma TI, uma
aba por imóvel, no mesmo layout do export por imóvel (issue #50) e do PDF
completo (`cadeia_completa_pdf.html`), precedidas por uma aba "Resumo".

Reaproveita o padrão de `test_issue_166_cri_export.py`: `RequestFactory` +
`SimpleNamespace(is_authenticated=True)` no `request.user` e
`view.__wrapped__(...)` para chamar a view diretamente, pulando o decorator
`login_required` (que exigiria uma sessão de login real).

Decisões de fixture:
- As matrículas dos 3 imóveis do cenário principal são criadas fora de
  ordem (M300, M100, M200) de propósito: se a view devolvesse os imóveis na
  ordem de criação/pk em vez de ordenar por matrícula, o teste de ordenação
  abaixo pegaria isso.
- Uma segunda TI, com um imóvel de matrícula/nome sentinela
  (`M999OUTRATI` / `IMOVEL_DE_OUTRA_TI_179`), prova que a exportação de uma
  TI não vaza dados de outra.
- `Lancamento.objects.bulk_create` evita o signal
  `processar_origens_automaticas_signal` (que criaria documentos de origem
  automaticamente a partir do texto de `origem`), mesmo padrão já usado em
  `test_exportacao_cadeia.py` e `test_issue_166_cri_export.py`.
- `cache.clear()` no `setUp`: o cache de tronco principal por imovel_id é
  compartilhado entre métodos de teste no mesmo processo.
"""

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook, load_workbook

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
from dominial.services import exportacao_excel_service
from dominial.services.exportacao_excel_service import (
    CABECALHOS_DETALHADOS,
    criar_nome_aba_imovel,
    escrever_celula_segura,
)
from dominial.templatetags.dominial_extras import origem_formatada_completa
from dominial.views import cadeia_dominial_views


class EscreverCelulaSeguraTest(SimpleTestCase):
    def test_forca_prefixos_perigosos_como_texto(self):
        ws = Workbook().active

        for row, valor in enumerate(
            ("=SUM(1+1)", "+foo", "-foo", "@foo", "\tfoo", "\rfoo"),
            start=1,
        ):
            with self.subTest(valor=valor):
                cell = escrever_celula_segura(ws, row, 1, valor)
                self.assertEqual(cell.value, valor)
                self.assertEqual(cell.data_type, "s")

    def test_preserva_inferencia_de_valores_nao_textuais(self):
        ws = Workbook().active
        casos = (
            (1234, "n"),
            (Decimal("1234.5678"), "n"),
            (date(2026, 9, 11), "d"),
            (None, "n"),
        )

        for row, (valor, data_type) in enumerate(casos, start=1):
            with self.subTest(valor=valor):
                cell = escrever_celula_segura(ws, row, 1, valor)
                self.assertEqual(cell.value, valor)
                self.assertEqual(cell.data_type, data_type)


class NomeAbaImovelTest(SimpleTestCase):
    def test_sanitiza_acentos_barras_e_espacos(self):
        nome = criar_nome_aba_imovel("M 100/Á", {"Resumo"})

        self.assertEqual(nome, "m-100a")
        self.assertFalse(set(nome) & set(':\\/?*[]'))

    def test_trunca_e_mantem_sufixo_de_duplicata_no_limite(self):
        matricula = "Matrícula muito longa para o limite do Excel 179"
        primeiro = criar_nome_aba_imovel(matricula, {"Resumo"})
        segundo = criar_nome_aba_imovel(matricula, {"Resumo", primeiro})

        self.assertEqual(len(primeiro), 31)
        self.assertLessEqual(len(segundo), 31)
        self.assertTrue(segundo.endswith("-2"))


class ExportacaoTisXlsConsolidadoTest(TestCase):
    """
    Cenário principal: uma TI com 3 imóveis (cada um com um documento e um
    lançamento) e uma segunda TI usada apenas para provar isolamento — nada
    dela deve aparecer na planilha da primeira.
    """

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

        self.tis = TIs.objects.create(
            nome="TI Teste 179", codigo="TI179", etnia="Teste"
        )
        self.cartorio = Cartorios.objects.create(
            nome="Cartório de Registro de Imóveis Teste 179",
            cns="179001",
            cidade="Cidade 179",
            estado="TS",
        )
        self.proprietario = Pessoas.objects.create(
            nome="Proprietário 179", cpf="10120120312"
        )

        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

        # Matrículas propositalmente fora da ordem de criação.
        self.imovel_m300 = self._criar_imovel_com_cadeia(self.tis, "M300")
        self.imovel_m100 = self._criar_imovel_com_cadeia(self.tis, "M100")
        self.imovel_m200 = self._criar_imovel_com_cadeia(self.tis, "M200")

        # Segunda TI: nada dela deve vazar para a planilha da primeira.
        self.tis_outra = TIs.objects.create(
            nome="TI Outra 179", codigo="TI179OUTRA", etnia="Teste"
        )
        self.imovel_outra_ti = self._criar_imovel_com_cadeia(
            self.tis_outra, "M999OUTRATI", nome="IMOVEL_DE_OUTRA_TI_179"
        )

    def _criar_imovel_com_cadeia(
        self, tis, matricula, nome=None, cartorio=None
    ):
        cartorio = cartorio or self.cartorio
        imovel = Imovel.objects.create(
            terra_indigena_id=tis,
            nome=nome or f"Imóvel {matricula}",
            proprietario=self.proprietario,
            matricula=matricula,
            cartorio=cartorio,
        )
        documento = Documento.objects.create(
            imovel=imovel,
            tipo=self.tipo_matricula,
            numero=matricula,
            data=timezone.now().date(),
            cartorio=cartorio,
            livro="1",
            folha="1",
        )
        # bulk_create evita o signal de processamento automático de origens
        # (mesmo padrão de test_issue_166_cri_export.py).
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento,
                tipo=self.tipo_inicio,
                data=timezone.now().date(),
                cartorio_origem=cartorio,
                origem="",
                area=Decimal("0"),
            ),
        ])
        return imovel

    def _request(self, path):
        request = self.factory.get(path)
        request.user = SimpleNamespace(is_authenticated=True)
        return request

    def _exportar(self, tis):
        response = cadeia_dominial_views.exportar_cadeia_dominial_excel_tis.__wrapped__(
            self._request("/excel-tis/"), tis.id
        )
        self.assertEqual(response.status_code, 200)
        return response

    @staticmethod
    def _abrir(response):
        return load_workbook(BytesIO(response.content))

    # 1 e 2 -------------------------------------------------------------

    def test_rota_responde_200_com_xlsx_e_abre_no_openpyxl(self):
        response = self._exportar(self.tis)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(".xlsx", response["Content-Disposition"])

        # Não deve levantar exceção ao abrir.
        workbook = self._abrir(response)
        self.assertEqual(
            workbook.sheetnames, ["Resumo", "m100", "m200", "m300"]
        )

    # 3 -------------------------------------------------------------------

    def test_cada_aba_contem_o_bloco_do_proprio_imovel_sem_vazar_outro(self):
        response = self._exportar(self.tis)
        workbook = self._abrir(response)

        for matricula in ("M100", "M200", "M300"):
            ws = workbook[matricula.lower()]
            self.assertEqual(ws["A4"].value, "Matrícula:")
            self.assertEqual(ws["B4"].value, matricula)
            valores = [cell.value for row in ws.iter_rows() for cell in row]
            self.assertIn(f"Matrícula: {matricula}", valores)
            for outra in {"M100", "M200", "M300"} - {matricula}:
                self.assertNotIn(outra, valores)

    # 4 -------------------------------------------------------------------

    def test_nao_vaza_imovel_de_outra_ti(self):
        response = self._exportar(self.tis)
        workbook = self._abrir(response)

        for ws in workbook.worksheets:
            for linha in ws.iter_rows():
                for celula in linha:
                    if isinstance(celula.value, str):
                        self.assertNotIn("M999OUTRATI", celula.value)
                        self.assertNotIn("IMOVEL_DE_OUTRA_TI_179", celula.value)

    # 5 -------------------------------------------------------------------

    def test_ordem_das_abas_e_lista_do_resumo_seguem_a_matricula(self):
        response = self._exportar(self.tis)
        workbook = self._abrir(response)

        self.assertEqual(
            workbook.sheetnames, ["Resumo", "m100", "m200", "m300"]
        )
        self.assertEqual(
            [workbook["Resumo"].cell(row=linha, column=1).value
             for linha in range(8, 11)],
            ["M100", "M200", "M300"],
        )

    def test_matricula_com_barra_e_acento_vira_nome_de_aba_valido(self):
        self._criar_imovel_com_cadeia(
            self.tis, "M 100/Á", nome="Imóvel matrícula especial"
        )

        workbook = self._abrir(self._exportar(self.tis))

        self.assertIn("m-100a", workbook.sheetnames)
        self.assertEqual(workbook["m-100a"]["B4"].value, "M 100/Á")
        self.assertLessEqual(len("m-100a"), 31)
        self.assertFalse(set("m-100a") & set(':\\/?*[]'))

    def test_matriculas_duplicadas_recebem_sufixo_sem_colidir(self):
        outro_cartorio = Cartorios.objects.create(
            nome="Segundo CRI Teste 179",
            cns="179099",
            cidade="Outra Cidade 179",
            estado="TS",
        )
        self._criar_imovel_com_cadeia(
            self.tis,
            "M100",
            nome="Imóvel duplicado M100",
            cartorio=outro_cartorio,
        )

        workbook = self._abrir(self._exportar(self.tis))

        self.assertIn("m100", workbook.sheetnames)
        self.assertIn("m100-2", workbook.sheetnames)
        self.assertEqual(workbook["m100"]["B5"].value, "Imóvel M100")
        self.assertEqual(
            workbook["m100-2"]["B5"].value, "Imóvel duplicado M100"
        )

    def test_erro_parcial_fica_na_aba_do_imovel_e_nao_afeta_a_seguinte(self):
        renderer_real = exportacao_excel_service.escrever_secao_documentos
        chamadas = 0

        def renderer_com_falha_parcial(
            ws, cadeia_completa, linha_inicial, estilos
        ):
            nonlocal chamadas
            chamadas += 1
            if chamadas == 2:
                # Simula uma exceção depois de o renderer já ter avançado e
                # escrito parte da seção do segundo imóvel.
                escrever_celula_segura(
                    ws,
                    linha_inicial + 3,
                    1,
                    "LINHA PARCIAL DO IMÓVEL M200",
                )
                raise ValueError("falha de fixture no renderer")
            return renderer_real(
                ws, cadeia_completa, linha_inicial, estilos
            )

        with (
            patch.object(
                exportacao_excel_service,
                "escrever_secao_documentos",
                side_effect=renderer_com_falha_parcial,
            ),
            patch.object(cadeia_dominial_views.logger, "exception"),
        ):
            response = self._exportar(self.tis)

        workbook = self._abrir(response)
        linhas_m200 = {
            cell.value: cell.row
            for cell in workbook["m200"]["A"]
            if isinstance(cell.value, str)
        }

        self.assertLess(
            linhas_m200["LINHA PARCIAL DO IMÓVEL M200"],
            linhas_m200["Erro ao exportar este imóvel."],
        )
        self.assertEqual(workbook["m300"]["B4"].value, "M300")
        self.assertIn(
            "Matrícula: M300", [cell.value for cell in workbook["m300"]["A"]]
        )

    def test_queries_ficam_sob_teto_com_tres_imoveis_e_dois_documentos(self):
        tipo_transcricao = DocumentoTipo.objects.create(tipo="transcricao")
        pessoa_transmitente = Pessoas.objects.create(
            nome="Transmitente 179", cpf="11122233344"
        )
        pessoa_adquirente = Pessoas.objects.create(
            nome="Adquirente 179", cpf="55566677788"
        )

        for indice, imovel in enumerate(
            (self.imovel_m100, self.imovel_m200, self.imovel_m300), start=1
        ):
            numero_origem = f"T{indice}79"
            documento_origem = Documento.objects.create(
                imovel=imovel,
                tipo=tipo_transcricao,
                numero=numero_origem,
                data=timezone.now().date(),
                cartorio=self.cartorio,
                livro="2",
                folha="2",
            )
            lancamento_origem = Lancamento.objects.create(
                documento=documento_origem,
                tipo=self.tipo_inicio,
                data=timezone.now().date(),
                cartorio_origem=self.cartorio,
                origem="",
            )
            lancamento_principal = Lancamento.objects.get(
                documento__imovel=imovel,
                documento__tipo=self.tipo_matricula,
            )
            lancamento_principal.origem = numero_origem
            lancamento_principal.save(update_fields=["origem"])

            LancamentoPessoa.objects.bulk_create(
                [
                    LancamentoPessoa(
                        lancamento=lancamento_principal,
                        pessoa=pessoa_transmitente,
                        tipo="transmitente",
                    ),
                    LancamentoPessoa(
                        lancamento=lancamento_principal,
                        pessoa=pessoa_adquirente,
                        tipo="adquirente",
                    ),
                    LancamentoPessoa(
                        lancamento=lancamento_origem,
                        pessoa=pessoa_transmitente,
                        tipo="transmitente",
                    ),
                    LancamentoPessoa(
                        lancamento=lancamento_origem,
                        pessoa=pessoa_adquirente,
                        tipo="adquirente",
                    ),
                ]
            )

        cache.clear()
        with CaptureQueriesContext(connection) as queries:
            response = self._exportar(self.tis)

        # A recursão histórica do serviço de cadeia ainda custa consultas por
        # nó (fora do escopo da #179). O teto cobre 3 imóveis x 2 documentos
        # com folga pequena, mas não admite as 2 consultas adicionais por
        # lançamento que `.transmitentes/.adquirentes.filter()` causavam.
        self.assertLessEqual(len(queries), 100)
        counts_de_imoveis = [
            query["sql"]
            for query in queries.captured_queries
            if "COUNT(" in query["sql"].upper()
            and "dominial_imovel" in query["sql"]
        ]
        self.assertEqual(counts_de_imoveis, [])
        workbook = self._abrir(response)
        valores = [
            cell.value
            for ws in workbook.worksheets[1:]
            for row in ws.iter_rows()
            for cell in row
        ]
        self.assertIn("Transmitente 179", valores)
        self.assertIn("Adquirente 179", valores)

    # 6 -------------------------------------------------------------------

    def test_estrutura_de_colunas_igual_ao_export_por_imovel(self):
        response = self._exportar(self.tis)
        ws = self._abrir(response)["m100"]

        header = None
        for linha in ws.iter_rows():
            if linha and linha[0].value == "Nº":
                header = linha
                break
        self.assertIsNotNone(
            header, "Linha de cabeçalho detalhado (começando em 'Nº') não encontrada"
        )

        valores = [cell.value for cell in header]
        self.assertEqual(valores, CABECALHOS_DETALHADOS)
        self.assertEqual(valores[3], "CRI")
        self.assertEqual(valores[9], "CRI")

    def test_aba_do_consolidado_tem_o_mesmo_layout_do_xls_individual(self):
        ws_consolidado = self._abrir(self._exportar(self.tis))["m100"]
        response_individual = (
            cadeia_dominial_views.exportar_cadeia_dominial_excel.__wrapped__(
                self._request("/excel/"), self.tis.id, self.imovel_m100.id
            )
        )
        self.assertEqual(response_individual.status_code, 200)
        ws_individual = load_workbook(BytesIO(response_individual.content)).active

        def valores(ws):
            return [
                [cell.value for cell in row]
                for row in ws.iter_rows(
                    min_row=1,
                    max_row=ws.max_row,
                    min_col=1,
                    max_col=ws.max_column,
                )
            ]

        self.assertEqual(ws_consolidado.dimensions, ws_individual.dimensions)
        self.assertEqual(valores(ws_consolidado), valores(ws_individual))
        self.assertEqual(
            {str(intervalo) for intervalo in ws_consolidado.merged_cells.ranges},
            {str(intervalo) for intervalo in ws_individual.merged_cells.ranges},
        )
        self.assertEqual(
            [ws_consolidado.column_dimensions[coluna].width
             for coluna in "ABCDEFGHIJKLMNOP"],
            [ws_individual.column_dimensions[coluna].width
             for coluna in "ABCDEFGHIJKLMNOP"],
        )

    def test_tipografia_cores_zebra_bordas_e_alturas_espelham_pdf(self):
        documento = Documento.objects.get(imovel=self.imovel_m100)
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento,
                tipo=self.tipo_inicio,
                numero_lancamento="R2-M100",
                data=timezone.now().date(),
                cartorio_origem=self.cartorio,
                origem="",
            ),
        ])

        response = self._exportar(self.tis)
        ws = self._abrir(response)["m100"]

        def rgb(cor):
            return cor.rgb[-6:]

        linha_agrupamento = next(
            cell.row for cell in ws["A"] if cell.value == "MATRÍCULA"
        )
        linha_cabecalho = next(cell.row for cell in ws["A"] if cell.value == "Nº")
        primeira_linha_dados = linha_cabecalho + 1
        segunda_linha_dados = linha_cabecalho + 2

        self.assertEqual(ws["A1"].font.name, "Arial")
        self.assertEqual(ws["A1"].font.sz, 18)
        self.assertEqual(rgb(ws["A1"].font.color), "2C5AA0")

        agrupamento = ws.cell(linha_agrupamento, 1)
        self.assertEqual(agrupamento.font.name, "Arial")
        self.assertEqual(agrupamento.font.sz, 6)
        self.assertEqual(rgb(agrupamento.font.color), "333333")
        self.assertEqual(rgb(agrupamento.fill.fgColor), "E1EDF7")
        self.assertEqual(
            rgb(ws.cell(linha_agrupamento, 14).fill.fgColor), "F8F9FA"
        )

        cabecalho = ws.cell(linha_cabecalho, 1)
        self.assertEqual(cabecalho.font.name, "Arial")
        self.assertEqual(cabecalho.font.sz, 6)
        self.assertTrue(cabecalho.font.bold)
        self.assertEqual(rgb(cabecalho.fill.fgColor), "F8F9FA")

        for lado in (cabecalho.border.left, cabecalho.border.right,
                     cabecalho.border.top, cabecalho.border.bottom):
            self.assertEqual(lado.style, "thin")
            self.assertEqual(rgb(lado.color), "DDDDDD")

        dado_par = ws.cell(primeira_linha_dados, 1)
        dado_impar = ws.cell(segunda_linha_dados, 1)
        self.assertEqual(dado_par.font.name, "Arial")
        self.assertEqual(dado_par.font.sz, 6)
        self.assertEqual(rgb(dado_par.fill.fgColor), "F8F9FA")
        self.assertEqual(rgb(dado_impar.fill.fgColor), "FFFFFF")
        self.assertEqual(ws.row_dimensions[linha_agrupamento].height, 12)
        self.assertEqual(ws.row_dimensions[linha_cabecalho].height, 12)
        self.assertIsNone(ws.row_dimensions[primeira_linha_dados].height)
        self.assertFalse(ws.row_dimensions[primeira_linha_dados].customHeight)

        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    self.assertEqual(cell.font.name, "Arial")

    # 7 -------------------------------------------------------------------

    def test_nao_menciona_tronco_principal_ou_secundario(self):
        response = self._exportar(self.tis)
        workbook = self._abrir(response)

        for ws in workbook.worksheets:
            for linha in ws.iter_rows():
                for celula in linha:
                    if isinstance(celula.value, str):
                        self.assertNotIn("TRONCO PRINCIPAL", celula.value)
                        self.assertNotIn("TRONCO SECUNDÁRIO", celula.value)

    def test_mantem_so_resumo_geral_sem_bloco_de_estatisticas(self):
        response = self._exportar(self.tis)
        workbook = self._abrir(response)
        ws = workbook["Resumo"]

        self.assertEqual(ws["A3"].value, "TI:")
        self.assertEqual(ws["A4"].value, "Total de imóveis:")
        self.assertEqual(ws["A5"].value, "Data de Exportação:")

        valores = [
            cell.value
            for planilha in workbook.worksheets
            for row in planilha.iter_rows()
            for cell in row
        ]
        self.assertNotIn("ESTATÍSTICAS", valores)
        self.assertNotIn("Total de Documentos:", valores)
        self.assertNotIn("Total de Lançamentos:", valores)
        self.assertNotIn("Documentos Compartilhados:", valores)

    # 8 -------------------------------------------------------------------

    def test_area_zerada_exibe_traco_na_coluna_14(self):
        # Os lançamentos das fixtures têm area=Decimal("0"); por decisão
        # de produto (Hiure, 10/09/2026) área zerada é exibida como "-",
        # nunca como "0,0000".
        response = self._exportar(self.tis)
        ws = self._abrir(response)["m100"]

        valores_coluna_14 = [
            ws.cell(row=linha[0].row, column=14).value for linha in ws.iter_rows()
        ]
        self.assertIn("-", valores_coluna_14)
        self.assertNotIn("0,0000", valores_coluna_14)

    def test_area_nao_zerada_exibe_texto_pt_br_com_quatro_casas(self):
        Lancamento.objects.filter(
            documento__imovel=self.imovel_m100
        ).update(area=Decimal("1234.5678"))

        response = self._exportar(self.tis)
        ws = self._abrir(response)["m100"]

        valores_coluna_14 = [cell.value for cell in ws["N"]]
        self.assertIn("1234,5678", valores_coluna_14)

    def test_origem_fim_cadeia_usa_mesma_frase_tratada_do_pdf(self):
        origem_bruta = "Destacamento Público:INCRA:origem_lidima"
        Lancamento.objects.filter(
            documento__imovel=self.imovel_m100
        ).update(origem=origem_bruta)
        lancamento = Lancamento.objects.select_related("cartorio_origem").get(
            documento__imovel=self.imovel_m100
        )
        texto_pdf = origem_formatada_completa(lancamento)

        ws = self._abrir(self._exportar(self.tis))["m100"]
        valores_origem = [cell.value for cell in ws["O"]]

        self.assertEqual(
            texto_pdf,
            "Destacamento Público : INCRA (Origem Lídima)",
        )
        self.assertIn(texto_pdf, valores_origem)
        self.assertNotIn(origem_bruta, valores_origem)

    def test_origem_matricula_anterior_usa_mesmo_texto_do_pdf(self):
        origem_bruta = "M99"
        Lancamento.objects.filter(
            documento__imovel=self.imovel_m100
        ).update(origem=origem_bruta)
        lancamento = Lancamento.objects.select_related("cartorio_origem").get(
            documento__imovel=self.imovel_m100
        )
        texto_pdf = origem_formatada_completa(lancamento)

        ws = self._abrir(self._exportar(self.tis))["m100"]
        valores_origem = [cell.value for cell in ws["O"]]

        self.assertEqual(
            texto_pdf,
            f"M99 ({self.cartorio.nome})",
        )
        self.assertIn(texto_pdf, valores_origem)
        self.assertNotIn(origem_bruta, valores_origem)

    def test_multiplas_origens_usam_quebra_de_linha_e_wrap_text(self):
        Lancamento.objects.filter(
            documento__imovel=self.imovel_m100
        ).update(origem="M99; Sem Origem::sem_origem")
        lancamento = Lancamento.objects.select_related("cartorio_origem").get(
            documento__imovel=self.imovel_m100
        )
        texto_pdf = origem_formatada_completa(lancamento)
        texto_xls = texto_pdf.replace("<br>", "\n")

        ws = self._abrir(self._exportar(self.tis))["m100"]
        celula_origem = next(cell for cell in ws["O"] if cell.value == texto_xls)

        self.assertEqual(texto_xls.count("\n"), 1)
        primeira_origem, segunda_origem = texto_xls.split("\n")
        self.assertIn("M99", primeira_origem)
        self.assertIn("Sem Origem", segunda_origem)
        self.assertNotIn("<br>", celula_origem.value)
        self.assertTrue(celula_origem.alignment.wrap_text)
        dimensao_linha = ws.row_dimensions[celula_origem.row]
        self.assertIsNone(dimensao_linha.height)
        self.assertFalse(dimensao_linha.customHeight)

    def test_neutraliza_prefixos_de_formula_nos_dados_do_lancamento(self):
        origem_perigosa = "=HYPERLINK(\"https://example.invalid\")"
        valores_perigosos = {
            "observacoes": "=SUM(1+1)",
            "forma": "+foo",
            "titulo": "-foo",
            "livro_transacao": "@foo",
            "origem": origem_perigosa,
        }
        Lancamento.objects.filter(
            documento__imovel=self.imovel_m100
        ).update(**valores_perigosos)

        response = self._exportar(self.tis)
        ws = self._abrir(response)["m100"]
        celulas_por_valor = {
            cell.value: cell
            for row in ws.iter_rows()
            for cell in row
            if cell.value in valores_perigosos.values()
        }
        celula_origem = next(
            cell
            for cell in ws["O"]
            if isinstance(cell.value, str)
            and cell.value.startswith(origem_perigosa)
        )

        for valor in (
            valores_perigosos["observacoes"],
            valores_perigosos["forma"],
            valores_perigosos["titulo"],
            valores_perigosos["livro_transacao"],
        ):
            with self.subTest(valor=valor):
                self.assertIn(valor, celulas_por_valor)
                self.assertEqual(celulas_por_valor[valor].value, valor)
                self.assertEqual(celulas_por_valor[valor].data_type, "s")
        self.assertEqual(celula_origem.data_type, "s")

    def test_neutraliza_formula_nos_metadados_e_preserva_total_numerico(self):
        formula = "=SUM(1+1)"
        self.tis.nome = formula
        self.tis.save(update_fields=["nome"])

        response = self._exportar(self.tis)
        ws = self._abrir(response)["Resumo"]

        self.assertEqual(ws["B3"].value, formula)
        self.assertEqual(ws["B3"].data_type, "s")
        self.assertEqual(ws["B4"].value, 3)
        self.assertEqual(ws["B4"].data_type, "n")

    def test_neutraliza_formula_na_lista_e_na_aba_do_imovel(self):
        formula = "=SUM(1+1)"
        self._criar_imovel_com_cadeia(self.tis, formula)

        workbook = self._abrir(self._exportar(self.tis))
        celula_resumo = next(
            cell for cell in workbook["Resumo"]["A"] if cell.value == formula
        )
        celula_imovel = next(
            ws["B4"] for ws in workbook.worksheets[1:]
            if ws["B4"].value == formula
        )

        self.assertEqual(celula_resumo.data_type, "s")
        self.assertEqual(celula_imovel.data_type, "s")

    # 10 ------------------------------------------------------------------

    def test_rota_resolve_por_nome(self):
        url = reverse("exportar_cadeia_tis_excel", kwargs={"tis_id": self.tis.id})
        self.assertEqual(url, f"/dominial/tis/{self.tis.id}/imoveis/excel/")

    def test_rota_redireciona_usuario_anonimo_para_login(self):
        url = reverse("exportar_cadeia_tis_excel", kwargs={"tis_id": self.tis.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"{settings.LOGIN_URL}?next={url}",
            fetch_redirect_response=False,
        )

    # 11 ------------------------------------------------------------------

    def test_botao_presente_em_imoveis_html(self):
        template = (
            Path(settings.BASE_DIR) / "templates" / "dominial" / "imoveis.html"
        ).read_text(encoding="utf-8")

        self.assertIn("{% url 'exportar_cadeia_tis_excel' tis_id=tis.id %}", template)
        self.assertIn("Exportar XLS da TI", template)

    def test_botao_presente_em_tis_detail_html(self):
        template = (
            Path(settings.BASE_DIR) / "templates" / "dominial" / "tis_detail.html"
        ).read_text(encoding="utf-8")

        self.assertIn("{% url 'exportar_cadeia_tis_excel' tis_id=tis.id %}", template)
        self.assertIn("Exportar XLS da TI", template)


class ExportacaoTisXlsImovelSemDocumentosTest(TestCase):
    """
    Caso dedicado (item 9 da issue #179): um imóvel sem nenhum documento
    cadastrado ainda deve gerar sua aba (com o aviso "Sem documentos
    cadastrados."), numa TI própria — para não alterar a contagem de 3
    imóveis exercitada em `ExportacaoTisXlsConsolidadoTest`.
    """

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

        self.tis = TIs.objects.create(
            nome="TI Sem Documentos 179", codigo="TI179SD", etnia="Teste"
        )
        self.cartorio = Cartorios.objects.create(
            nome="Cartório Teste 179 SD", cns="179002", cidade="Cidade", estado="TS"
        )
        self.proprietario = Pessoas.objects.create(
            nome="Proprietário 179 SD", cpf="98765432100"
        )
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel Sem Documentos",
            proprietario=self.proprietario,
            matricula="M400",
            cartorio=self.cartorio,
        )

    def _request(self, path):
        request = self.factory.get(path)
        request.user = SimpleNamespace(is_authenticated=True)
        return request

    def test_imovel_sem_documentos_gera_secao_com_aviso(self):
        response = cadeia_dominial_views.exportar_cadeia_dominial_excel_tis.__wrapped__(
            self._request("/excel-tis/"), self.tis.id
        )
        self.assertEqual(response.status_code, 200)

        workbook = load_workbook(BytesIO(response.content))
        ws = workbook["m400"]
        valores_coluna_a = [cell.value for cell in ws["A"]]

        self.assertEqual(workbook.sheetnames, ["Resumo", "m400"])
        self.assertEqual(ws["B4"].value, "M400")
        self.assertEqual(ws["B5"].value, "Imóvel Sem Documentos")
        self.assertIn("Sem documentos cadastrados.", valores_coluna_a)
