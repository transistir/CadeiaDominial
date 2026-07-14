"""
Dívida adicional pré-T28 (encontrada durante a auditoria final, não estava
no checkpoint original) — `editar_lancamento` (lancamento_views.py) permitia
editar um lançamento de outro imóvel quando seu documento fosse "referenciado
como origem" nesta cadeia. A checagem "direta" usava
`origem__icontains=lancamento.documento.numero`: um match textual de número,
sem checar cartório. Um homônimo (mesmo número, cartório diferente, não
referenciado de fato nesta cadeia) passava no teste só por coincidência de
texto, autorizando edição indevida.

Corrigido: a checagem agora usa `LancamentoOrigemLeituraService.obter_origens`
e compara tipo + número normalizado + cartório (identidade completa) de cada
origem do imóvel contra o documento do lançamento a editar.

Nenhuma migração é aplicada; os testes rodam no banco de testes.
"""

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from dominial.models import Lancamento, LancamentoTipo
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


class EdicaoLancamentoHomonimoTest(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(username="editlanc", password="editlancpass")
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(username="editlanc", password="editlancpass")

    def test_homonimo_em_outro_cartorio_nao_referenciado_e_recusado(self):
        """M123/cartorio_a é a origem real do imóvel atual. M123/cartorio_b é
        um homônimo em outro imóvel, não referenciado por esta cadeia. Editar
        o lançamento do homônimo a partir deste imóvel deve ser recusado."""
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        documento_atual = self.criar_documento(imovel_atual, self.tipo_matricula, "M999", self.cartorio_a)
        # bulk_create evita que o sinal de criação automática (T11/T12, já
        # correto) crie o documento da origem antes deste teste montar o
        # próprio cenário (documento em imóvel separado).
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento_atual,
                tipo=self.tipo_inicio,
                data="2026-01-02",
                origem="M123",
                cartorio_origem=self.cartorio_a,
            ),
        ])

        imovel_b = self.criar_imovel("123", self.cartorio_b, nome="Homônimo B")
        documento_b = self.criar_documento(imovel_b, self.tipo_matricula, "M123", self.cartorio_b)
        lancamento_b = Lancamento.objects.create(
            documento=documento_b,
            tipo=self.tipo_inicio,
            data="2026-01-01",
            origem="",
        )

        url = reverse('editar_lancamento', kwargs={
            'tis_id': self.ti.id, 'imovel_id': imovel_atual.id, 'lancamento_id': lancamento_b.id,
        })
        response = self.client.get(url)

        self.assertRedirects(response, reverse('cadeia_dominial', kwargs={
            'tis_id': self.ti.id, 'imovel_id': imovel_atual.id,
        }))

    def test_documento_realmente_referenciado_e_aceito(self):
        """M123/cartorio_a é a origem real - editar um lançamento desse
        documento deve ser permitido (renderiza o formulário, sem redirect
        de recusa)."""
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        documento_atual = self.criar_documento(imovel_atual, self.tipo_matricula, "M999", self.cartorio_a)
        # bulk_create evita que o sinal de criação automática (T11/T12, já
        # correto) crie o documento da origem antes deste teste montar o
        # próprio cenário (documento em imóvel separado).
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=documento_atual,
                tipo=self.tipo_inicio,
                data="2026-01-02",
                origem="M123",
                cartorio_origem=self.cartorio_a,
            ),
        ])

        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Origem A")
        documento_a = self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)
        lancamento_a = Lancamento.objects.create(
            documento=documento_a,
            tipo=self.tipo_inicio,
            data="2026-01-01",
            origem="",
        )

        url = reverse('editar_lancamento', kwargs={
            'tis_id': self.ti.id, 'imovel_id': imovel_atual.id, 'lancamento_id': lancamento_a.id,
        })
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
