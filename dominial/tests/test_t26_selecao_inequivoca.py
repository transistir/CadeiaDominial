"""
T26 — Exigir seleção inequívoca por ID e validar no backend que o ID
corresponde à identidade oferecida.

Critérios de aceite (CHECKPOINT_ATUAL.md / TAREFAS.md):
- O botão de seleção de documento usa `novo_lancamento_documento`
  (com `documento_id`), e o backend redireciona um `documento_id` que não
  pertença ao imóvel da URL para o imóvel de origem.
- A importação de duplicata (`documento_origem_id` e
  `documentos_importaveis[]`) é validada contra uma duplicata
  recalculada no servidor a partir da origem/cartório originalmente
  submetidos; PKs arbitrários ou incompatíveis são recusados mesmo
  que existam no banco.

Nenhuma migração é aplicada; os testes rodam no banco de testes.
"""

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase, override_settings
from django.contrib.messages.storage.fallback import FallbackStorage
from django.urls import reverse

from dominial.services.lancamento_duplicata_service import LancamentoDuplicataService
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


def _request_com_messages(factory, path, data):
    request = factory.post(path, data)
    setattr(request, "session", {})
    setattr(request, "_messages", FallbackStorage(request))
    return request


class T26SelecaoDocumentoTest(IdentidadeDocumentoFixture):
    """`novo_lancamento_documento` deve redirecionar documento de outro imóvel."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(username="t26", password="t26pass")

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(username="t26", password="t26pass")

    def test_documento_id_de_outro_imovel_redireciona_para_origem(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_b = self.criar_imovel("456", self.cartorio_b, nome="Imóvel B")
        doc_a = self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)

        url = reverse("novo_lancamento_documento", kwargs={
            "tis_id": self.ti.id, "imovel_id": imovel_b.id, "documento_id": doc_a.id,
        })
        response = self.client.get(url)

        url_origem = reverse("novo_lancamento_documento", kwargs={
            "tis_id": self.ti.id, "imovel_id": imovel_a.id, "documento_id": doc_a.id,
        })
        self.assertRedirects(response, url_origem, fetch_redirect_response=False)

    def test_documento_id_do_proprio_imovel_e_aceito(self):
        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        doc_a = self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)

        url = reverse("novo_lancamento_documento", kwargs={
            "tis_id": self.ti.id, "imovel_id": imovel_a.id, "documento_id": doc_a.id,
        })
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)


@override_settings(DUPLICATA_VERIFICACAO_ENABLED=True)
class T26ImportacaoDuplicataIdentidadeTest(IdentidadeDocumentoFixture):
    """`processar_importacao_duplicata` deve validar os IDs recebidos contra
    a duplicata recalculada no servidor, nunca confiar apenas nos PKs do POST."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(username="t26dup", password="t26pass")

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def test_importacao_aceita_quando_identidade_confere(self):
        imovel_origem = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_destino = self.criar_imovel("999", self.cartorio_b, nome="Imóvel Destino")
        doc_origem = self.criar_documento(imovel_origem, self.tipo_matricula, "M123", self.cartorio_a)
        doc_destino = self.criar_documento(imovel_destino, self.tipo_matricula, "M999", self.cartorio_b)

        request = _request_com_messages(self.factory, "/fake-url/", {
            "documento_origem_id": str(doc_origem.id),
            "documentos_importaveis[]": [str(doc_origem.id)],
            "origem_completa[]": ["M123"],
            "cartorio_origem[]": [str(self.cartorio_a.id)],
        })

        resultado = LancamentoDuplicataService.processar_importacao_duplicata(
            request, doc_destino, self.user
        )

        self.assertTrue(resultado["sucesso"], resultado.get("mensagem"))

    def test_documento_importavel_fora_da_cadeia_e_recusado(self):
        """Um documento existente no banco, mas que não pertence à cadeia da
        origem informada, não pode ser aceito só porque a PK é válida."""
        imovel_origem = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_destino = self.criar_imovel("999", self.cartorio_b, nome="Imóvel Destino")
        imovel_alheio = self.criar_imovel("777", self.cartorio_b, nome="Imóvel Alheio")
        doc_origem = self.criar_documento(imovel_origem, self.tipo_matricula, "M123", self.cartorio_a)
        doc_destino = self.criar_documento(imovel_destino, self.tipo_matricula, "M999", self.cartorio_b)
        doc_alheio = self.criar_documento(imovel_alheio, self.tipo_matricula, "M777", self.cartorio_b)

        request = _request_com_messages(self.factory, "/fake-url/", {
            "documento_origem_id": str(doc_origem.id),
            "documentos_importaveis[]": [str(doc_origem.id), str(doc_alheio.id)],
            "origem_completa[]": ["M123"],
            "cartorio_origem[]": [str(self.cartorio_a.id)],
        })

        resultado = LancamentoDuplicataService.processar_importacao_duplicata(
            request, doc_destino, self.user
        )

        self.assertFalse(resultado["sucesso"])
        self.assertIn("não pertencem à cadeia dominial", resultado["mensagem"])

    def test_documento_origem_id_incompativel_com_origem_informada_e_recusado(self):
        """documento_origem_id deve corresponder exatamente ao documento que a
        origem/cartório originalmente submetidos resolveriam no servidor."""
        imovel_origem = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_outro = self.criar_imovel("321", self.cartorio_b, nome="Imóvel Outro")
        imovel_destino = self.criar_imovel("999", self.cartorio_b, nome="Imóvel Destino")
        self.criar_documento(imovel_origem, self.tipo_matricula, "M123", self.cartorio_a)
        doc_outro = self.criar_documento(imovel_outro, self.tipo_matricula, "M321", self.cartorio_b)
        doc_destino = self.criar_documento(imovel_destino, self.tipo_matricula, "M999", self.cartorio_b)

        request = _request_com_messages(self.factory, "/fake-url/", {
            # documento_origem_id aponta para um documento diferente do que
            # "M123" no cartório A efetivamente resolve.
            "documento_origem_id": str(doc_outro.id),
            "documentos_importaveis[]": [str(doc_outro.id)],
            "origem_completa[]": ["M123"],
            "cartorio_origem[]": [str(self.cartorio_a.id)],
        })

        resultado = LancamentoDuplicataService.processar_importacao_duplicata(
            request, doc_destino, self.user
        )

        self.assertFalse(resultado["sucesso"])
        self.assertIn("Não foi possível confirmar", resultado["mensagem"])

    def test_importacao_sem_origem_preservada_e_recusada(self):
        """Sem os campos ocultos origem_completa[]/cartorio_origem[], a
        duplicata não pode ser reconfirmada e a importação é recusada,
        mesmo com PKs existentes no banco."""
        imovel_origem = self.criar_imovel("123", self.cartorio_a, nome="Imóvel A")
        imovel_destino = self.criar_imovel("999", self.cartorio_b, nome="Imóvel Destino")
        doc_origem = self.criar_documento(imovel_origem, self.tipo_matricula, "M123", self.cartorio_a)
        doc_destino = self.criar_documento(imovel_destino, self.tipo_matricula, "M999", self.cartorio_b)

        request = _request_com_messages(self.factory, "/fake-url/", {
            "documento_origem_id": str(doc_origem.id),
            "documentos_importaveis[]": [str(doc_origem.id)],
        })

        resultado = LancamentoDuplicataService.processar_importacao_duplicata(
            request, doc_destino, self.user
        )

        self.assertFalse(resultado["sucesso"])
        self.assertIn("Não foi possível confirmar", resultado["mensagem"])
