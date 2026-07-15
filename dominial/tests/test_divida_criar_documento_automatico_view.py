"""
Dívida pré-T28 — `documento_views.py:199` (`criar_documento_automatico`)
verificava existência apenas por `imovel + numero` bruto (sem tipo/cartório
canônicos) e caía em `Cartorios.objects.first()` (cartório arbitrário) em
dois pontos quando não conseguia determinar o cartório de origem. Registrada
no checkpoint em 2026-07-14, corrigida nesta sessão:

- a checagem de existência agora usa tipo + número normalizado;
- sem um cartório resolvido pelo contexto, a criação é recusada (erro),
  nunca adivinha um cartório.

Esta view não está referenciada em nenhum template/JS ativo (endpoint
alcançável apenas por URL direta), mas segue coberta porque está registrada
como rota nomeada (`criar_documento_automatico`) e pode ser chamada
manualmente ou por integrações futuras.

Nenhuma migração é aplicada; os testes rodam no banco de testes.
"""

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from dominial.models import Documento, Lancamento, LancamentoTipo
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


class CriarDocumentoAutomaticoViewTest(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(username="docauto", password="docautopass")
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(username="docauto", password="docautopass")

    def _url(self, imovel, codigo_origem):
        return reverse('criar_documento_automatico', kwargs={
            'tis_id': self.ti.id, 'imovel_id': imovel.id, 'codigo_origem': codigo_origem,
        })

    def test_existencia_verifica_identidade_normalizada_nao_texto_bruto(self):
        """Um documento "123" (sem prefixo, tipo matrícula) já existente deve
        bloquear a criação de "M123" no mesmo imóvel/cartório, mesmo com
        formatação de número diferente. Precisa de um lançamento com
        cartorio_origem definido para a view conseguir resolver o cartório
        (mesmo critério de identidade completa usado na checagem)."""
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        self.criar_documento(imovel, self.tipo_matricula, "123", self.cartorio_a)
        documento_atual = self.criar_documento(imovel, self.tipo_matricula, "M999", self.cartorio_a)
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento_atual,
                tipo=self.tipo_inicio,
                data="2026-01-02",
                origem="M123",
                cartorio_origem=self.cartorio_a,
            ),
        ])

        response = self.client.get(self._url(imovel, "M123"), HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 400)
        self.assertIn("já existe", response.json()['error'])
        self.assertEqual(
            Documento.objects.filter(imovel=imovel, numero_normalizado="123").count(), 1,
            "não deve ter criado um segundo documento para a mesma identidade",
        )

    def test_sem_cartorio_resolvivel_recusa_criacao_em_vez_de_adivinhar(self):
        """Sem lançamento algum com cartório de origem no imóvel, e o código
        não sendo a matrícula do imóvel, a view deve recusar a criação em vez
        de usar Cartorios.objects.first()."""
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Atual")

        response = self.client.get(self._url(imovel, "M321"), HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 400)
        self.assertIn("Não foi possível determinar o cartório", response.json()['error'])
        self.assertFalse(Documento.objects.filter(numero_normalizado="321").exists())

    def test_homonimo_em_outro_cartorio_nao_bloqueia_criacao(self):
        """Um documento "123"/cartorio_a existente no mesmo imóvel não pode
        bloquear a criação de "M123" quando o cartório resolvido pelo
        contexto é cartorio_b: são identidades diferentes (achado da revisão
        automatizada do PR — Greptile/Qodo, 2026-07-14: a checagem de
        existência precisa incluir o cartório resolvido, não só tipo+número)."""
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        self.criar_documento(imovel, self.tipo_matricula, "123", self.cartorio_a)
        documento_atual = self.criar_documento(imovel, self.tipo_matricula, "M999", self.cartorio_a)
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento_atual,
                tipo=self.tipo_inicio,
                data="2026-01-02",
                origem="M123",
                cartorio_origem=self.cartorio_b,
            ),
        ])

        response = self.client.get(self._url(imovel, "M123"), HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            Documento.objects.filter(imovel=imovel, numero_normalizado="123").count(), 2,
            "deve existir um documento por cartório para a mesma identidade de número",
        )
        criado = Documento.objects.get(imovel=imovel, numero_normalizado="123", cartorio=self.cartorio_b)
        self.assertIsNotNone(criado)

    def test_com_cartorio_de_origem_no_lancamento_usa_esse_cartorio(self):
        """Quando existe um lançamento com cartorio_origem definido para a
        origem, o documento criado deve usar exatamente esse cartório - não
        Cartorios.objects.first(). bulk_create evita que o sinal de criação
        automática (T11/T12, já correto) crie o documento antes da view ser
        chamada, isolando o caminho sob teste."""
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        documento_atual = self.criar_documento(imovel, self.tipo_matricula, "M999", self.cartorio_a)
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento_atual,
                tipo=self.tipo_inicio,
                data="2026-01-02",
                origem="M321",
                cartorio_origem=self.cartorio_b,
            ),
        ])

        response = self.client.get(self._url(imovel, "M321"), HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        criado = Documento.objects.get(numero_normalizado="321", imovel=imovel)
        self.assertEqual(criado.cartorio_id, self.cartorio_b.id)
