"""
Issue #157 — campos do bloco Transmissão não persistem após erro de
validação ou fluxo de duplicata.

Cobre os 4 caminhos de perda:
1. Branch else: de falha não dá return → re-render sem form_data
2. Fluxo de duplicata lê forma/titulo genéricos e não repassa hidden fields
3. _processar_campos_transacao sobrescreve lancamento.forma com None
4. processar_dados_lancamento lê forma_registro/forma_inicio (fantasmas)

Tasks 1-3 cobrem o caminho 1; Tasks 4-5 o caminho 2; Tasks 6-7 o caminho 3.
"""

import re

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from ..models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from ..services.lancamento_campos_service import LancamentoCamposService
from ..services.lancamento_form_service import LancamentoFormService


class TransmissaoPersistenciaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="t157", password="t157pass")
        self.client = Client()
        self.client.login(username="t157", password="t157pass")

        self.tis = TIs.objects.create(nome="TI 157", etnia="Teste", estado="SP")
        self.cartorio = Cartorios.objects.create(
            nome="Cartório 157", cns="CNS157157", cidade="São Paulo"
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_registro = LancamentoTipo.objects.create(tipo="registro")
        self.pessoa = Pessoas.objects.create(nome="Proprietário 157", cpf="15715715715")

        self.imovel = Imovel.objects.create(
            nome="Imóvel 157",
            matricula="12345",
            terra_indigena_id=self.tis,
            proprietario=self.pessoa,
            tipo_documento_principal="matricula",
            cartorio=self.cartorio,
        )
        self.documento = Documento.objects.create(
            numero="12345",
            tipo=self.tipo_matricula,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data="2020-01-01",
            livro="1",
            folha="1",
        )
        # Pré-condição: já existe lançamento número "1" neste documento.
        self.lancamento_existente = Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_registro,
            numero_lancamento="1",
            data="2020-01-01",
        )

    def test_erro_validacao_preserva_campos_transacao(self):
        response = self.client.post(
            reverse("novo_lancamento", args=[self.tis.id, self.imovel.id]),
            {
                "tipo_lancamento": str(self.tipo_registro.id),
                "numero_lancamento": "1",  # duplicado → cai no else: de falha
                "numero_lancamento_simples": "1",
                "forma_transacao": "Compra e Venda",
                "titulo_transacao": "Escritura Pública",
                "livro_transacao": "2",
                "folha_transacao": "30",
                "data_transacao": "2020-01-15",
            },
        )

        self.assertEqual(response.status_code, 200)
        form_data = response.context["form_data"]
        self.assertEqual(form_data["forma_transacao"], "Compra e Venda")
        self.assertEqual(form_data["titulo_transacao"], "Escritura Pública")
        self.assertEqual(form_data["livro_transacao"], "2")
        self.assertEqual(form_data["folha_transacao"], "30")
        self.assertEqual(form_data["data_transacao"], "2020-01-15")
        # e o HTML repõe os values:
        self.assertContains(response, 'value="Compra e Venda"')

    def test_erro_validacao_preserva_contexto_heranca(self):
        """O re-render de erro deve carregar a MESMA metadata de cartório/herança
        que um GET fresco — antes o caminho de erro caía no fluxo GET e depois
        passou a montar um contexto pobre, perdendo `is_primeiro_lancamento`,
        `cartorio_origem_correto`, `cartorio_matricula`, etc. (issue #157)."""
        url = reverse("novo_lancamento", args=[self.tis.id, self.imovel.id])

        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(
            url,
            {
                "tipo_lancamento": str(self.tipo_registro.id),
                "numero_lancamento": "1",  # duplicado → else: de falha
                "numero_lancamento_simples": "1",
                "forma_transacao": "Compra e Venda",
            },
        )
        self.assertEqual(post_response.status_code, 200)

        # regressão original: o form_data do POST sobrevive
        self.assertEqual(
            post_response.context["form_data"]["forma_transacao"], "Compra e Venda"
        )

        # a metadata de cartório/herança sobrevive igual ao GET
        self.assertEqual(
            post_response.context["is_primeiro_lancamento"],
            get_response.context["is_primeiro_lancamento"],
        )
        self.assertIn("cartorio_origem_correto", post_response.context)
        self.assertEqual(
            post_response.context["cartorio_origem_correto"],
            get_response.context["cartorio_origem_correto"],
        )

        # e o form_data ainda vence a herança no template (a herança de cartório
        # continua marcada, mas `lancamento` herdado é um Lancamento() vazio, então
        # todos os guards `modo_edicao and lancamento.X` do bloco Transmissão são
        # False e o form_data vence), senão reintroduziria a #157
        self.assertContains(post_response, 'value="Compra e Venda"')

        # os hidden `cartorio`/`cartorio_nome` (herdados do documento) precisam
        # renderizar preenchidos igual ao GET — antes o caminho de erro forçava
        # `modo_edicao=False` e o template deixava `value=""` (issue #157).
        cartorio_hidden = r'name="cartorio"[^>]*value="[^"]+"'
        self.assertRegex(
            get_response.content.decode(), cartorio_hidden,
            "pré-condição: o GET deveria preencher o hidden cartorio",
        )
        self.assertContains(post_response, '<input type="hidden" name="cartorio"')
        self.assertRegex(post_response.content.decode(), cartorio_hidden)
        # o valor postado deve bater com o do GET (id do cartório herdado)
        get_val = re.search(cartorio_hidden, get_response.content.decode()).group(0)
        post_val = re.search(cartorio_hidden, post_response.content.decode()).group(0)
        self.assertEqual(get_val, post_val)

    def test_fluxo_duplicata_preserva_campos_transacao(self):
        # Documento em OUTRO imóvel que será detectado como duplicata da origem.
        outro_imovel = Imovel.objects.create(
            nome="Imóvel origem 157",
            matricula="99999",
            terra_indigena_id=self.tis,
            proprietario=self.pessoa,
            tipo_documento_principal="matricula",
            cartorio=self.cartorio,
        )
        Documento.objects.create(
            numero="99999",
            tipo=self.tipo_matricula,
            imovel=outro_imovel,
            cartorio=self.cartorio,
            data="2019-01-01",
            livro="1",
            folha="1",
        )

        response = self.client.post(
            reverse("novo_lancamento", args=[self.tis.id, self.imovel.id]),
            {
                "tipo_lancamento": str(self.tipo_registro.id),
                "numero_lancamento_simples": "2",
                "data": "2020-02-02",
                "origem_completa[]": "99999",
                "cartorio_origem[]": str(self.cartorio.id),
                "cartorio_origem_nome[]": self.cartorio.nome,
                "forma_transacao": "Compra e Venda",
                "titulo_transacao": "Escritura Pública",
                "livro_transacao": "5",
                "folha_transacao": "10",
                "data_transacao": "2019-05-05",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dominial/duplicata_importacao.html")
        # nenhum campo preservado deve renderizar o literal "None" (issue #157)
        self.assertNotContains(response, 'value="None"')
        form_data = response.context["form_data"]
        self.assertEqual(form_data["forma_transacao"], "Compra e Venda")
        self.assertEqual(form_data["titulo_transacao"], "Escritura Pública")
        self.assertEqual(form_data["livro_transacao"], "5")
        self.assertEqual(form_data["folha_transacao"], "10")
        self.assertEqual(form_data["data_transacao"], "2019-05-05")
        # hidden fields do formulário de importação repassam os campos:
        self.assertContains(response, 'name="forma_transacao"')
        self.assertContains(response, 'name="titulo_transacao"')
        self.assertContains(response, 'value="Compra e Venda"')


class ProcessarCamposTransacaoPreservaTest(TestCase):
    """Caminho 3 — `_processar_campos_transacao` sobrescrevia `forma`/`titulo`
    com `None` quando o bloco Transmissão vinha vazio, apagando o que a
    averbação (em documento transcrição) já havia gravado via `forma_averbacao`
    (issue #157, Tasks 6-7)."""

    def setUp(self):
        self.factory = RequestFactory()
        self.tis = TIs.objects.create(nome="TI 157b", etnia="Teste", estado="SP")
        self.cartorio = Cartorios.objects.create(
            nome="Cartório 157b", cns="CNS157B00", cidade="São Paulo"
        )
        self.pessoa = Pessoas.objects.create(nome="Prop 157b", cpf="15715715799")
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo="transcricao")
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo="averbacao")
        self.tipo_registro = LancamentoTipo.objects.create(tipo="registro")

        self.imovel = Imovel.objects.create(
            nome="Imóvel 157b",
            matricula="55555",
            terra_indigena_id=self.tis,
            proprietario=self.pessoa,
            tipo_documento_principal="transcricao",
            cartorio=self.cartorio,
        )
        self.doc_transcricao = Documento.objects.create(
            numero="55555",
            tipo=self.tipo_transcricao,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data="2020-01-01",
            livro="1",
            folha="1",
        )
        self.doc_matricula = Documento.objects.create(
            numero="55556",
            tipo=self.tipo_matricula,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data="2020-01-01",
            livro="1",
            folha="1",
        )

    def test_averbacao_transcricao_preserva_forma_averbacao(self):
        lancamento = Lancamento.objects.create(
            documento=self.doc_transcricao,
            tipo=self.tipo_averbacao,
            numero_lancamento="AV1",
            data="2020-02-02",
        )
        request = self.factory.post(
            "/", {"forma_averbacao": "Averbação de Construção", "forma_transacao": ""}
        )
        LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
        self.assertEqual(lancamento.forma, "Averbação de Construção")

    def test_averbacao_transcricao_transacao_preenchida_vence(self):
        lancamento = Lancamento.objects.create(
            documento=self.doc_transcricao,
            tipo=self.tipo_averbacao,
            numero_lancamento="AV2",
            data="2020-02-02",
        )
        request = self.factory.post(
            "/",
            {"forma_averbacao": "Averbação de Construção", "forma_transacao": "Compra e Venda"},
        )
        LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
        self.assertEqual(lancamento.forma, "Compra e Venda")

    def test_edicao_registro_limpar_forma_transacao_vira_none(self):
        lancamento = Lancamento.objects.create(
            documento=self.doc_matricula,
            tipo=self.tipo_registro,
            numero_lancamento="R1",
            data="2020-02-02",
            forma="Compra e Venda",
        )
        request = self.factory.post("/", {"forma_transacao": ""})
        LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
        self.assertIsNone(lancamento.forma)

    def test_averbacao_transcricao_preserva_titulo_existente(self):
        lancamento = Lancamento.objects.create(
            documento=self.doc_transcricao,
            tipo=self.tipo_averbacao,
            numero_lancamento="AV3",
            data="2020-02-02",
            titulo="Escritura Pública",
        )
        request = self.factory.post(
            "/", {"forma_averbacao": "Averbação de Construção", "titulo_transacao": ""}
        )
        LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
        self.assertEqual(lancamento.titulo, "Escritura Pública")

    def test_edicao_registro_limpar_titulo_transacao_vira_none(self):
        lancamento = Lancamento.objects.create(
            documento=self.doc_matricula,
            tipo=self.tipo_registro,
            numero_lancamento="R2",
            data="2020-02-02",
            titulo="Escritura Pública",
        )
        request = self.factory.post("/", {"titulo_transacao": ""})
        LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
        self.assertIsNone(lancamento.titulo)


class ProcessarDadosLancamentoFormaTransacaoTest(TestCase):
    """Caminho 4 — `processar_dados_lancamento` lia os nomes fantasmas
    `forma_registro`/`forma_inicio` (zero emitters em templates) para os tipos
    `registro` e `inicio_matricula`, de forma que `forma` nunca vinha do
    formulário. Unificado em `forma_transacao` (issue #157, Task 8)."""

    def setUp(self):
        self.factory = RequestFactory()
        self.tipo_registro = LancamentoTipo.objects.create(tipo="registro")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

    def test_registro_le_forma_transacao(self):
        request = self.factory.post(
            "/", {"numero_lancamento": "R1 M123", "forma_transacao": "Compra e Venda"}
        )
        dados = LancamentoFormService.processar_dados_lancamento(request, self.tipo_registro)
        self.assertEqual(dados["forma"], "Compra e Venda")

    def test_inicio_matricula_le_forma_transacao(self):
        request = self.factory.post(
            "/", {"numero_lancamento": "M123", "forma_transacao": "Doação"}
        )
        dados = LancamentoFormService.processar_dados_lancamento(request, self.tipo_inicio)
        self.assertEqual(dados["forma"], "Doação")
