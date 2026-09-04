"""Issue #171 — Árvore da cadeia embutida no modal de seleção de sequência.

Cobre o dado e o markup que o novo painel D3 do modal consome:
- a view ``cadeia_dominial_tabela`` renderiza o SVG da árvore e o link para a
  visualização em tela cheia (``cadeia_dominial_d3``);
- o endpoint ``cadeia_dominial_arvore`` devolve o JSON da árvore do imóvel;
- regressão: a lista arrastável de documentos (``documentosLista``) continua
  presente no HTML do modal.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase
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


class Issue171ArvoreModalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="issue171", password="testpass"
        )
        cls.tis = TIs.objects.create(
            nome="TI Issue 171", codigo="TI-171", etnia="Teste"
        )
        cls.pessoa = Pessoas.objects.create(nome="Pessoa Issue 171")
        cls.cartorio = Cartorios.objects.create(
            nome="Cartório Issue 171",
            cns="CNS-ISSUE-171",
            cidade="Campo Grande",
            estado="MS",
        )
        cls.imovel = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome="Imóvel Issue 171",
            proprietario=cls.pessoa,
            matricula="M171",
            cartorio=cls.cartorio,
        )
        cls.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        cls.tipo_registro = LancamentoTipo.objects.create(tipo="registro")
        cls.documento = Documento.objects.create(
            imovel=cls.imovel,
            tipo=cls.tipo_matricula,
            numero="M171",
            data=timezone.now().date(),
            cartorio=cls.cartorio,
            livro="1",
            folha="1",
        )
        cls.lancamento = Lancamento.objects.create(
            documento=cls.documento,
            tipo=cls.tipo_registro,
            data=timezone.now().date(),
            origem="",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def _tabela_url(self):
        return reverse(
            "cadeia_dominial_tabela",
            kwargs={"tis_id": self.tis.id, "imovel_id": self.imovel.id},
        )

    def _arvore_url(self):
        return reverse(
            "cadeia_dominial_arvore",
            kwargs={"tis_id": self.tis.id, "imovel_id": self.imovel.id},
        )

    def test_tabela_renderiza_svg_da_arvore_no_modal(self):
        response = self.client.get(self._tabela_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="modal-arvore-svg"')

    def test_tabela_tem_link_para_arvore_em_tela_cheia(self):
        response = self.client.get(self._tabela_url())

        self.assertEqual(response.status_code, 200)
        link = reverse(
            "cadeia_dominial_d3",
            kwargs={"tis_id": self.tis.id, "imovel_id": self.imovel.id},
        )
        self.assertContains(response, 'href="%s"' % link)

    def test_tabela_expoe_data_arvore_url_no_painel(self):
        response = self.client.get(self._tabela_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'data-arvore-url="%s"' % self._arvore_url()
        )

    def test_tabela_mantem_lista_de_documentos_do_modal(self):
        """Regressão: a lista arrastável de documentos segue no modal."""
        response = self.client.get(self._tabela_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="documentosLista"')

    def test_endpoint_arvore_retorna_json_do_imovel(self):
        response = self.client.get(self._arvore_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = json.loads(response.content)
        self.assertIn("documentos", data)
        self.assertIsInstance(data["documentos"], list)
        numeros = {doc.get("numero") for doc in data["documentos"]}
        self.assertIn("M171", numeros)
