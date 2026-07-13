from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from openpyxl import load_workbook

from dominial.views import cadeia_dominial_views


class TipoDocumentoFake:
    def __init__(self, tipo, display):
        self.tipo = tipo
        self._display = display

    def get_tipo_display(self):
        return self._display


class ExportacaoCadeiaParidadeTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tis = SimpleNamespace(id=10, nome="TI Teste")
        self.imovel = SimpleNamespace(
            id=20,
            nome="Imóvel Teste",
            matricula="100",
            proprietario=SimpleNamespace(nome="Proprietário Teste"),
            cartorio=SimpleNamespace(nome="Cartório Teste"),
        )
        self.documentos = [
            SimpleNamespace(
                id=101,
                numero="M100",
                tipo=TipoDocumentoFake("matricula", "Matrícula"),
            ),
            SimpleNamespace(
                id=202,
                numero="T90",
                tipo=TipoDocumentoFake("transcricao", "Transcrição"),
            ),
        ]
        self.contexto_completo = {
            "tis": self.tis,
            "imovel": self.imovel,
            "cadeia_completa": [
                {
                    "tipo": "tronco_principal",
                    "titulo": "Tronco principal",
                    "documentos": [
                        {
                            "documento": self.documentos[0],
                            "lancamentos": [],
                            "is_importado": False,
                        },
                        {
                            "documento": self.documentos[1],
                            "lancamentos": [],
                            "is_importado": True,
                        },
                    ],
                }
            ],
            "estatisticas": {
                "total_documentos": 2,
                "total_lancamentos": 0,
                "documentos_importados": 1,
            },
        }

    def _request(self, path, query=None):
        request = self.factory.get(path, data=query or {})
        request.user = SimpleNamespace(is_authenticated=True)
        return request

    def test_botao_pdf_padrao_aponta_para_exportacao_completa(self):
        template = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dominial"
            / "cadeia_dominial_tabela.html"
        ).read_text(encoding="utf-8")

        link_esperado = (
            "{% url 'exportar_cadeia_completa_pdf' "
            "tis_id=tis.id imovel_id=imovel.id %}"
        )
        link_antigo = (
            "{% url 'exportar_cadeia_dominial_pdf' "
            "tis_id=tis.id imovel_id=imovel.id %}"
        )

        self.assertIn(link_esperado, template)
        self.assertNotIn(link_antigo, template)

    def test_rota_antiga_de_pdf_permanece_disponivel(self):
        self.assertEqual(
            reverse(
                "exportar_cadeia_dominial_pdf",
                kwargs={"tis_id": self.tis.id, "imovel_id": self.imovel.id},
            ),
            "/dominial/tis/10/imovel/20/cadeia-tabela/pdf/",
        )

    @patch("dominial.services.cadeia_completa_service.CadeiaCompletaService")
    @patch.object(cadeia_dominial_views, "get_object_or_404")
    @patch.object(cadeia_dominial_views, "render_to_string")
    @patch.object(cadeia_dominial_views, "HTML")
    @patch.object(cadeia_dominial_views.os.path, "exists", return_value=True)
    def test_pdf_completo_recebe_contexto_e_ordem_do_servico(
        self,
        _exists,
        html_mock,
        render_to_string_mock,
        get_object_mock,
        service_class_mock,
    ):
        get_object_mock.side_effect = [self.tis, self.imovel]
        service = service_class_mock.return_value
        service.get_cadeia_completa.return_value = self.contexto_completo
        render_to_string_mock.return_value = "<html></html>"
        html_mock.return_value.write_pdf.return_value = b"%PDF-teste"

        response = cadeia_dominial_views.exportar_cadeia_completa_pdf.__wrapped__(
            self._request("/pdf/"), self.tis.id, self.imovel.id
        )

        service.get_cadeia_completa.assert_called_once_with(self.tis.id, self.imovel.id)
        render_to_string_mock.assert_called_once_with(
            "dominial/cadeia_completa_pdf.html", self.contexto_completo
        )
        contexto_pdf = render_to_string_mock.call_args.args[1]
        ids_pdf = [
            item["documento"].id
            for tronco in contexto_pdf["cadeia_completa"]
            for item in tronco["documentos"]
        ]
        self.assertEqual(ids_pdf, [101, 202])
        self.assertEqual(response["Content-Type"], "application/pdf")

    @patch("dominial.services.cadeia_completa_service.CadeiaCompletaService")
    @patch.object(cadeia_dominial_views, "get_object_or_404")
    def test_excel_usa_mesmo_servico_e_preserva_ordem_dos_documentos(
        self, get_object_mock, service_class_mock
    ):
        get_object_mock.side_effect = [self.tis, self.imovel]
        service = service_class_mock.return_value
        service.get_cadeia_completa.return_value = self.contexto_completo

        response = cadeia_dominial_views.exportar_cadeia_dominial_excel.__wrapped__(
            self._request("/excel/"), self.tis.id, self.imovel.id
        )

        service.get_cadeia_completa.assert_called_once_with(self.tis.id, self.imovel.id)
        workbook = load_workbook(BytesIO(response.content))
        valores_coluna_a = [cell.value for cell in workbook.active["A"]]
        titulos_esperados = ["Matrícula: M100", "📥 Transcrição: T90"]
        titulos_documentos = [valor for valor in valores_coluna_a if valor in titulos_esperados]
        self.assertEqual(titulos_documentos, titulos_esperados)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @patch("dominial.services.cadeia_completa_service.CadeiaCompletaService")
    @patch.object(cadeia_dominial_views, "get_object_or_404")
    @patch.object(cadeia_dominial_views, "render_to_string", return_value="<html></html>")
    @patch.object(cadeia_dominial_views, "HTML")
    @patch.object(cadeia_dominial_views.os.path, "exists", return_value=True)
    def test_pdf_com_sequencia_preserva_fluxo_personalizado(
        self,
        _exists,
        html_mock,
        _render_to_string_mock,
        get_object_mock,
        service_class_mock,
    ):
        get_object_mock.side_effect = [self.tis, self.imovel]
        service = service_class_mock.return_value
        service.get_cadeia_completa_com_sequencia_personalizada.return_value = (
            self.contexto_completo
        )
        html_mock.return_value.write_pdf.return_value = b"%PDF-teste"

        cadeia_dominial_views.exportar_cadeia_completa_pdf.__wrapped__(
            self._request("/pdf/", {"sequencia": "202,101"}),
            self.tis.id,
            self.imovel.id,
        )

        service.get_cadeia_completa_com_sequencia_personalizada.assert_called_once_with(
            self.tis.id, self.imovel.id, "202,101"
        )
        service.get_cadeia_completa.assert_not_called()
