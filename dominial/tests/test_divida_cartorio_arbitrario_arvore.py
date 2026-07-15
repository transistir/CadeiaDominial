"""
Dívida pré-T28 — `hierarquia_arvore_service.py:237` criava documento
automático com `Cartorios.objects.first()` (cartório arbitrário) quando uma
origem não resolvia, ao renderizar a árvore D3 com
`criar_documentos_automaticos=True` (write-on-read, acionado por
`cadeia_dominial_views.py:64`). Registrada no checkpoint em 2026-07-14,
corrigida nesta sessão: o cartório da própria origem passa a ser usado, ou o
documento simplesmente não é criado — nunca um cartório escolhido ao acaso.

Nenhuma migração é aplicada; os testes rodam no banco de testes.
"""

from datetime import date

from dominial.models import Documento, Lancamento, LancamentoTipo
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


class CartorioArbitrarioNaCriacaoAutomaticaTest(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # cartorio_a é criado antes de cartorio_b em IdentidadeDocumentoFixture,
        # logo tem pk menor: se o código usasse Cartorios.objects.first(),
        # devolveria cartorio_a mesmo quando a origem real é do cartorio_b.
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

    def test_criacao_automatica_usa_cartorio_da_origem_nao_o_primeiro(self):
        imovel_atual = self.criar_imovel("999", self.cartorio_a, nome="Atual")
        documento_atual = self.criar_documento(imovel_atual, self.tipo_matricula, "M999", self.cartorio_a)

        imovel_a = self.criar_imovel("123", self.cartorio_a, nome="Origem A")
        documento_a = self.criar_documento(imovel_a, self.tipo_matricula, "M123", self.cartorio_a)

        # bulk_create não dispara o sinal de criação automática (T11/T12),
        # isolando o caminho de fallback de hierarquia_arvore_service.py que
        # está sendo corrigido aqui - igual ao teste CR-06 já faz.
        Lancamento.objects.bulk_create([
            # Nível 1: documento principal -> documento_a (resolve normalmente).
            Lancamento(
                documento=documento_atual,
                tipo=self.tipo_inicio,
                data=date(2026, 1, 2),
                origem="M123",
                cartorio_origem=self.cartorio_a,
            ),
            # Nível 2: documento_a cita uma origem M321/cartorio_b que ainda
            # não existe como Documento em lugar nenhum - dispara a criação
            # automática (criar_documentos_automaticos=True).
            Lancamento(
                documento=documento_a,
                tipo=self.tipo_inicio,
                data=date(2026, 1, 3),
                origem="M321",
                cartorio_origem=self.cartorio_b,
            ),
        ])

        self.assertFalse(
            Documento.objects.filter(numero_normalizado="321", cartorio=self.cartorio_b).exists()
        )

        HierarquiaArvoreService.construir_arvore_cadeia_dominial(
            imovel_atual, criar_documentos_automaticos=True,
        )

        criado = Documento.objects.get(numero_normalizado="321")
        self.assertEqual(
            criado.cartorio_id, self.cartorio_b.id,
            "documento criado automaticamente deve usar o cartório da própria origem, não Cartorios.objects.first()",
        )

    def test_sem_cartorio_na_origem_nao_cria_documento_arbitrario(self):
        """Se a origem estruturada não tiver cartório, a criação automática
        deve ser recusada (retornar None), nunca cair em Cartorios.objects.first()."""
        cartorio = self.cartorio_a
        criado = HierarquiaArvoreService._criar_documento_automatico(
            "M555", None, self.criar_imovel("111", cartorio, nome="Qualquer"),
        )
        self.assertIsNone(criado)
