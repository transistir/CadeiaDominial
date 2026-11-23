"""Issue #396 — parser único de área pt-BR (formulário manual, revisão OCR, edição).

O defeito: `1.000` (mil hectares) era aceito como decimal por `float()` e virava
`1.0000` ha no banco, sem erro. Havia quatro caminhos divergentes de conversão
(`float(area.replace(',', '.'))` no service de campos, no de criação e na view,
mais `float(area)` na validação) e nenhum deles tratava separador de milhar.

Decisão registrada na issue (23/11/2026): vírgula é sempre decimal; ponto é
milhar apenas quando forma grupo de 3 dígitos E há vírgula ou mais de um ponto;
separador único com exatamente 3 dígitos após e 1–3 antes é **ambíguo** → erro
explícito, nunca interpretação.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

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
from dominial.tests.segregacao_fixtures import atribuir_tis
from dominial.utils.area_br import AreaInvalida, parse_area_br


class ParseAreaBrTest(SimpleTestCase):
    def test_vazio_vira_none(self):
        for entrada in (None, "", "   ", "\u00a0"):
            with self.subTest(entrada=entrada):
                self.assertIsNone(parse_area_br(entrada))

    def test_virgula_e_decimal(self):
        self.assertEqual(parse_area_br("150,5"), Decimal("150.5000"))
        self.assertEqual(parse_area_br("1234,5678"), Decimal("1234.5678"))

    def test_ponto_com_ate_duas_casas_e_decimal(self):
        # Ponto isolado seguido de 1–2 dígitos não forma grupo de milhar:
        # é decimal inequívoco (valor que a revisão OCR já entrega).
        self.assertEqual(parse_area_br("150.5"), Decimal("150.5000"))
        self.assertEqual(parse_area_br("74.6755"), Decimal("74.6755"))

    def test_ponto_milhar_com_virgula_decimal(self):
        self.assertEqual(parse_area_br("1.234,5678"), Decimal("1234.5678"))
        self.assertEqual(parse_area_br("1.234.567,89"), Decimal("1234567.8900"))

    def test_varios_pontos_sem_virgula_sao_milhar(self):
        self.assertEqual(parse_area_br("1.234.567"), Decimal("1234567.0000"))

    def test_tres_casas_com_zero_inicial_nao_e_ambiguo(self):
        # 0.012 ha = 120 m²: zero à esquerda não abre grupo de milhar.
        self.assertEqual(parse_area_br("0.012"), Decimal("0.0120"))
        self.assertEqual(parse_area_br("0,012"), Decimal("0.0120"))

    def test_quatro_casas_nao_formam_grupo_de_milhar(self):
        self.assertEqual(parse_area_br("1,2345"), Decimal("1.2345"))
        self.assertEqual(parse_area_br("1.2345"), Decimal("1.2345"))

    def test_ambiguos_levantam_erro(self):
        for entrada in ("1.000", "1,000", "12.345", "150,500"):
            with self.subTest(entrada=entrada):
                with self.assertRaises(AreaInvalida) as ctx:
                    parse_area_br(entrada)
                mensagem = str(ctx.exception)
                self.assertIn("ambígua", mensagem.lower())
                # A mensagem precisa oferecer AS DUAS leituras, sem escolher.
                inteiro, decimais = entrada.replace(",", ".").split(".")
                leitura_decimal = f"{Decimal(f'{inteiro}.{decimais}'):.4f}"
                leitura_milhar = f"{Decimal(inteiro + decimais):.0f}"
                self.assertIn(leitura_decimal, mensagem)
                self.assertIn(leitura_milhar, mensagem)

    def test_invalidos_levantam_erro(self):
        for entrada in ("-1", ",5", "1..2", "1,2,3", "abc", "1,23456", "1 2"):
            with self.subTest(entrada=entrada):
                with self.assertRaises(AreaInvalida):
                    parse_area_br(entrada)

    def test_devolve_decimal_quantizado_em_quatro_casas(self):
        valor = parse_area_br("150,5")
        self.assertIsInstance(valor, Decimal)
        self.assertEqual(valor.as_tuple().exponent, -4)

    def test_zero_e_aceito(self):
        # Não introduzimos regra nova de negócio além do formato (#396): zero
        # continua aceito, como hoje.
        self.assertEqual(parse_area_br("0"), Decimal("0.0000"))


class AreaViewTest(TestCase):
    """Formulário manual → validação → banco (e re-render com o valor digitado)."""

    def setUp(self):
        self.user = User.objects.create_user(username="issue396", password="segredo396")
        self.client = Client()
        self.client.login(username="issue396", password="segredo396")

        self.tis = TIs.objects.create(nome="TI 396", etnia="Teste", estado="BA")
        atribuir_tis(self.user, self.tis)
        self.cartorio = Cartorios.objects.create(
            nome="Cartório 396", cns="CNS396396", cidade="Itamaraju", estado="BA"
        )
        self.pessoa = Pessoas.objects.create(nome="Proprietário 396")
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_registro = LancamentoTipo.objects.create(tipo="registro")
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo="averbacao")

        self.imovel = Imovel.objects.create(
            nome="Imóvel 396",
            matricula="396",
            terra_indigena_id=self.tis,
            proprietario=self.pessoa,
            tipo_documento_principal="matricula",
            cartorio=self.cartorio,
        )
        self.documento = Documento.objects.create(
            numero="396",
            tipo=self.tipo_matricula,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data="2020-01-01",
            livro="1",
            folha="1",
        )
        self.url = reverse("novo_lancamento", args=[self.tis.id, self.imovel.id])

    def _payload(self, **extra):
        payload = {
            "tipo_lancamento": str(self.tipo_registro.id),
            "numero_lancamento_simples": "1",
            "data": "2020-02-02",
            "forma_transacao": "Compra e Venda",
            "titulo_transacao": "Escritura Pública",
        }
        payload.update(extra)
        return payload

    def test_area_ambigua_nao_cria_lancamento_e_explica(self):
        resposta = self.client.post(self.url, self._payload(area="1.000"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Lancamento.objects.count(), 0)
        mensagens = [str(m) for m in resposta.context["messages"]]
        self.assertTrue(
            any("ambígua" in m.lower() for m in mensagens),
            f"mensagem de área ambígua ausente: {mensagens}",
        )
        # O que foi digitado não se perde no re-render.
        self.assertEqual(resposta.context["form_data"]["area"], "1.000")

    def test_area_milhar_ptbr_persiste_mil_hectares(self):
        resposta = self.client.post(self.url, self._payload(area="1.234,5678"))

        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.content[:500])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.area, Decimal("1234.5678"))

    def test_area_com_ponto_decimal_persiste(self):
        resposta = self.client.post(self.url, self._payload(area="150.5"))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Lancamento.objects.get().area, Decimal("150.5000"))

    def test_post_com_virgula_persiste(self):
        resposta = self.client.post(self.url, self._payload(area="150,5"))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Lancamento.objects.get().area, Decimal("150.5000"))

    def test_post_com_milhar_ptbr_persiste(self):
        resposta = self.client.post(self.url, self._payload(area="1234,5678"))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Lancamento.objects.get().area, Decimal("1234.5678"))

    def test_area_canonica_com_ponto_persiste(self):
        """Canônico do A3 (ponto decimal, 4 casas) grava sem conversão.

        A fiação do prefill (canônico de 3 casas → 4 no input) é provada em
        `ia_ocr/tests/test_revisao_formulario_prefill_area_outra_unidade.py`
        e o codec da revisão em `ia_ocr/tests/test_valores_area_396.py`.
        """
        resposta = self.client.post(self.url, self._payload(area="74.6755"))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Lancamento.objects.get().area, Decimal("74.6755"))

    def test_edicao_aceita_milhar_e_round_trip(self):
        lancamento = Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_averbacao,
            numero_lancamento="AV1",
            data="2020-02-02",
            area=Decimal("10.0000"),
        )
        url = reverse(
            "editar_lancamento",
            args=[self.tis.id, self.imovel.id, lancamento.id],
        )
        payload = {
            "tipo_lancamento": str(self.tipo_averbacao.id),
            "numero_lancamento": "AV1",
            "numero_lancamento_simples": "1",
            "data": "2020-02-02",
            "forma_averbacao": "Averbação",
            "descricao": "Descrição",
            "area": "1.234,5678",
        }

        resposta = self.client.post(url, payload)
        self.assertEqual(
            resposta.status_code, 302,
            [str(m) for m in resposta.context.get("messages", [])]
            if resposta.context else resposta.content[:300],
        )
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.area, Decimal("1234.5678"))

        # Round-trip: a tela de edição devolve o valor exibido e o parser o
        # re-aceita sem mudar a magnitude.
        pagina = self.client.get(url)
        self.assertContains(pagina, "1234.5678")
        payload["area"] = "1234.5678"
        segunda = self.client.post(url, payload)
        self.assertEqual(segunda.status_code, 302)
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.area, Decimal("1234.5678"))

    def test_edicao_rejeita_ambiguo_e_preserva_valor(self):
        lancamento = Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_averbacao,
            numero_lancamento="AV1",
            data="2020-02-02",
            area=Decimal("10.0000"),
        )
        url = reverse(
            "editar_lancamento",
            args=[self.tis.id, self.imovel.id, lancamento.id],
        )

        resposta = self.client.post(
            url,
            {
                "tipo_lancamento": str(self.tipo_averbacao.id),
                "numero_lancamento_simples": "1",
                "data": "2020-02-02",
                "forma_averbacao": "Averbação",
                "descricao": "Descrição",
                "area": "1.000",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.area, Decimal("10.0000"))
        mensagens = [str(m) for m in resposta.context["messages"]]
        self.assertTrue(any("ambígua" in m.lower() for m in mensagens))
