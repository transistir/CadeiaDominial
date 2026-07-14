"""
T25 — Exibir identidade documental completa nas opções apresentadas ao usuário.

Critérios de aceite (CHECKPOINT_ATUAL.md):
- Mostrar tipo e número do documento.
- Mostrar cartório com CNS e localização suficiente para distinguir homônimos.
- Incluir o imóvel/cadeia quando a opção reutiliza documento existente.
- Cobrir o conteúdo na view/template sem ainda mudar o contrato de seleção (T26).

Estes testes falham antes da implementação da T25 e passam depois.
Nenhum migração é aplicada ao banco compartilhado; rodam no banco de testes.
"""

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from dominial.services.lancamento_duplicata_service import LancamentoDuplicataService
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


class T25IdentidadeOpcoesTest(IdentidadeDocumentoFixture):
    """Reaproveita o fixture canônico (cartório A/B, tipos, imóvel/documento)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(username="t25", password="t25pass")

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(username="t25", password="t25pass")

    # ------------------------------------------------------------------
    # DTO da duplicata/importação — obter_dados_duplicata_para_template
    # ------------------------------------------------------------------

    def test_dto_documento_origem_contem_identidade_completa(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        doc_a = self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)

        dados = LancamentoDuplicataService.obter_dados_duplicata_para_template({
            "tem_duplicata": True,
            "documento_origem": doc_a,
            "documentos_importaveis": [],
            "cadeia_dominial": [],
        })

        origem = dados["documento_origem"]
        self.assertEqual(origem["numero"], "M123")
        self.assertEqual(origem["tipo"], "Matrícula")
        self.assertEqual(origem["cartorio"], "Cartório A")
        self.assertEqual(origem["cartorio_cns"], "CNS-A")
        self.assertEqual(origem["cartorio_cidade"], "Cidade A")
        self.assertEqual(origem["cartorio_uf"], "MS")
        self.assertEqual(origem["imovel_id"], imovel_a.id)
        self.assertEqual(origem["imovel_nome"], "Imóvel A")
        self.assertEqual(origem["imovel_matricula"], "123")

    def test_dto_cadeia_contem_identidade_completa(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        doc_a = self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)

        dados = LancamentoDuplicataService.obter_dados_duplicata_para_template({
            "tem_duplicata": True,
            "documento_origem": doc_a,
            "documentos_importaveis": [],
            "cadeia_dominial": [{"documento": doc_a, "lancamentos": []}],
        })

        item = dados["cadeia_dominial"][0]["documento"]
        self.assertEqual(item["numero"], "M123")
        self.assertEqual(item["tipo"], "Matrícula")
        self.assertEqual(item["cartorio"], "Cartório A")
        self.assertEqual(item["cartorio_cns"], "CNS-A")
        self.assertEqual(item["cartorio_cidade"], "Cidade A")
        self.assertEqual(item["cartorio_uf"], "MS")
        self.assertEqual(item["imovel_id"], imovel_a.id)
        self.assertEqual(item["imovel_nome"], "Imóvel A")
        self.assertEqual(item["imovel_matricula"], "123")

    def test_dto_distingue_homonimos_em_cartorios_diferentes(self):
        """Dois M123 em cartórios distintos precisam de blocos distinguíveis."""
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Imóvel B")
        doc_a = self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)
        doc_b = self.criar_documento(imovel_b, self.tipo_matricula, "M123", self.cartorio_b)

        dados = LancamentoDuplicataService.obter_dados_duplicata_para_template({
            "tem_duplicata": True,
            "documento_origem": doc_a,
            "documentos_importaveis": [],
            "cadeia_dominial": [
                {"documento": doc_a, "lancamentos": []},
                {"documento": doc_b, "lancamentos": []},
            ],
        })

        item_a = dados["cadeia_dominial"][0]["documento"]
        item_b = dados["cadeia_dominial"][1]["documento"]
        # Mesmo número e tipo: sem a identidade completa seriam indistinguíveis.
        self.assertEqual(item_a["numero"], item_b["numero"])
        self.assertEqual(item_a["tipo"], item_b["tipo"])
        # A identidade completa os distingue.
        self.assertNotEqual(item_a["cartorio_cns"], item_b["cartorio_cns"])
        self.assertNotEqual(item_a["cartorio"], item_b["cartorio"])
        self.assertNotEqual(item_a["imovel_nome"], item_b["imovel_nome"])

    def test_dto_documentos_importaveis_contem_identidade(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        doc_a = self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)

        dados = LancamentoDuplicataService.obter_dados_duplicata_para_template({
            "tem_duplicata": True,
            "documento_origem": doc_a,
            "documentos_importaveis": [doc_a],
            "cadeia_dominial": [],
        })

        imp = dados["documentos_importaveis"][0]
        self.assertEqual(imp["cartorio"], "Cartório A")
        self.assertEqual(imp["cartorio_cns"], "CNS-A")
        self.assertEqual(imp["cartorio_cidade"], "Cidade A")
        self.assertEqual(imp["cartorio_uf"], "MS")
        self.assertEqual(imp["imovel_nome"], "Imóvel A")
        self.assertEqual(imp["imovel_matricula"], "123")

    def test_dto_preserva_campos_existentes_do_contrato(self):
        """T25 só adiciona campos; não remove/renomeia os atuais (contrato é T26)."""
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        doc_a = self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)

        dados = LancamentoDuplicataService.obter_dados_duplicata_para_template({
            "tem_duplicata": True,
            "documento_origem": doc_a,
            "documentos_importaveis": [doc_a],
            "cadeia_dominial": [{"documento": doc_a, "lancamentos": []}],
        })

        origem = dados["documento_origem"]
        for chave in ("id", "numero", "tipo", "imovel_nome", "cartorio", "livro", "folha", "total_lancamentos"):
            self.assertIn(chave, origem, f"campo existente {chave} não pode sumir")
        imp = dados["documentos_importaveis"][0]
        for chave in ("id", "numero", "tipo", "livro", "folha", "total_lancamentos", "selecionado"):
            self.assertIn(chave, imp, f"campo existente {chave} não pode sumir")
        item = dados["cadeia_dominial"][0]["documento"]
        for chave in ("id", "numero", "tipo", "livro", "folha"):
            self.assertIn(chave, item, f"campo existente {chave} não pode sumir")

    # ------------------------------------------------------------------
    # View de seleção de documento para novo lançamento
    # ------------------------------------------------------------------

    def test_selecionar_documento_exibe_tipo_cartorio_cns_e_localidade(self):
        imovel = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        self.criar_documento(imovel, self.tipo_matricula, "M123", self.cartorio_a)

        url = reverse("selecionar_documento_lancamento", kwargs={
            "tis_id": self.ti.id, "imovel_id": imovel.id,
        })
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Tipo exibido corretamente (documento.tipo.get_tipo_display).
        # Antes da T25 o template usava documento.get_tipo_display (FK), que renderiza vazio.
        self.assertIn("Matrícula", content)
        # Cartório com CNS e localização.
        self.assertIn("CNS-A", content)
        self.assertIn("Cidade A", content)

    def test_selecionar_documento_distingue_homonimos_em_cartorios_diferentes(self):
        """Dois M123 em cartórios distintos no mesmo imóvel devem aparecer
        com cartório/CNS/localização diferentes na mesma tela."""
        imovel = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        self.criar_documento(imovel, self.tipo_matricula, "M123", self.cartorio_a)
        self.criar_documento(imovel, self.tipo_matricula, "M123", self.cartorio_b)

        url = reverse("selecionar_documento_lancamento", kwargs={
            "tis_id": self.ti.id, "imovel_id": imovel.id,
        })
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("CNS-A", content)
        self.assertIn("Cidade A", content)
        self.assertIn("CNS-B", content)
        self.assertIn("Cidade B", content)
