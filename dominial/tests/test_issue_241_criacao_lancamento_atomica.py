"""
Issue #241 — atomicidade de criar_lancamento_completo.

Bug: ``criar_lancamento_completo`` commita o Lancamento básico (``_criar_lancamento_basico``)
antes de processar origens/pessoas. Se uma etapa posterior levanta exceção
(ex.: ValidationError "Cartório obrigatório para a origem 1." vinda de
``lancamento_origem_service._sincronizar_origens_estruturadas`` com múltiplas
origens sem cartório), o except captura sem rollback → lançamento órfão
persistido (sem pessoas, sem LancamentoOrigem).

Fix: envolver o corpo da criação em ``transaction.atomic()``, espelhando
``atualizar_lancamento_completo`` que já usa esse padrão desde o #144.

T1 (o bug): criação com 2 origens documentais sem cartório → erro retornado
   E nenhum Lancamento/LancamentoOrigem/LancamentoPessoa persistido.
T2 (sucesso preservado): criação com cartórios válidos → tudo criado.
T3 (regressão genérica): falha simulada em etapa posterior → nada persistido.
"""
from datetime import date
from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase

from dominial.models import (
    Documento,
    Lancamento,
    LancamentoOrigem,
    LancamentoPessoa,
    LancamentoTipo,
)
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


class Issue241Base(IdentidadeDocumentoFixture):
    """Fixture mínima: TI, cartórios A/B, tipos de documento e lançamento."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tipo_inicio, _ = LancamentoTipo.objects.get_or_create(
            tipo="inicio_matricula"
        )

    def setUp(self):
        cache.clear()

    def _criar_cenario(self, matricula="241"):
        """Cria TI/Imovel/Documento para o teste. Cada teste usa matrícula
        distinta para não colidir na constraint de número de lançamento."""
        imovel = self.criar_imovel(
            matricula, self.cartorio_a, nome=f"Imóvel #{matricula}"
        )
        documento = self.criar_documento(
            imovel, self.tipo_matricula, f"M{matricula}", self.cartorio_a
        )
        return imovel, documento

    def _post_base(self, origens, cartorios_ids, cartorios_nomes,
                   sigla="M241"):
        """Monta POST para ``criar_lancamento_completo`` (inicio_matricula)."""
        total = len(origens)
        return {
            "tipo_lancamento": str(self.tipo_inicio.pk),
            "sigla_matricula": sigla,
            "numero_lancamento_simples": "1",
            "numero_lancamento": "",
            "data": "2026-01-02",
            "observacoes": "",
            "origem_completa[]": list(origens),
            "cartorio_origem[]": [str(c) if c else "" for c in cartorios_ids],
            "cartorio_origem_nome[]": list(cartorios_nomes),
            "livro_origem[]": [""] * total,
            "folha_origem[]": [""] * total,
            "apos_importacao": "true",  # pula verificação de duplicata
            "transmitente_nome[]": [],
            "transmitente[]": [],
            "adquirente_nome[]": [],
            "adquirente[]": [],
        }


class T1OrfaoCountTest(Issue241Base):
    """T1 (o bug): erro pós-criação não pode deixar lançamento órfão."""

    def test_t1_erro_cartorio_obrigatorio_nao_deixa_lancamento_orfao(self):
        """2 origens documentais sem cartório → ValidationError em
        processar_origens_automaticas. O lançamento NÃO deve persistir."""
        imovel, documento = self._criar_cenario(matricula="24101")
        post_data = self._post_base(
            origens=["M500", "T600"],
            cartorios_ids=["", ""],
            cartorios_nomes=["", ""],
            sigla="M24101",
        )
        request = RequestFactory().post("/x/", post_data)

        lanc_count_before = Lancamento.objects.count()
        origem_count_before = LancamentoOrigem.objects.count()
        pessoa_count_before = LancamentoPessoa.objects.count()
        doc_count_before = Documento.objects.count()

        result, msg = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.ti, imovel, documento
        )

        # O erro deve ser retornado ao caller
        self.assertIsNone(result)
        self.assertIn("Erro ao criar lançamento", msg)

        # Nenhum órfão: tudo que foi criado dentro do atomic deve ser desfeito
        self.assertEqual(
            Lancamento.objects.count(), lanc_count_before,
            "Lançamento órfão persistido — atomicidade falhou"
        )
        self.assertEqual(
            LancamentoOrigem.objects.count(), origem_count_before,
            "LancamentoOrigem órfã persistida"
        )
        self.assertEqual(
            LancamentoPessoa.objects.count(), pessoa_count_before,
            "LancamentoPessoa órfão persistido"
        )
        # Nenhum documento novo criado além dos da fixture
        self.assertEqual(
            Documento.objects.count(), doc_count_before,
            "Documento automático órfão persistido"
        )


class T2SucessoPreservadoTest(Issue241Base):
    """T2: caminho de sucesso inalterado — contrato (lancamento, mensagem)."""

    def test_t2_criacao_com_cartorio_valido_persiste_tudo(self):
        """2 origens COM cartório válido → lançamento + origens criados."""
        imovel, documento = self._criar_cenario(matricula="24102")

        # Criar documentos de origem pré-existentes para M500 e T600
        self.criar_documento(
            self.criar_imovel("500", self.cartorio_a, nome="Origem M500"),
            self.tipo_matricula, "M500", self.cartorio_a
        )
        self.criar_documento(
            self.criar_imovel("600", self.cartorio_b, nome="Origem T600"),
            self.tipo_transcricao, "T600", self.cartorio_b
        )

        post_data = self._post_base(
            origens=["M500", "T600"],
            cartorios_ids=[self.cartorio_a.pk, self.cartorio_b.pk],
            cartorios_nomes=[self.cartorio_a.nome, self.cartorio_b.nome],
            sigla="M24102",
        )
        request = RequestFactory().post("/x/", post_data)

        lanc_count_before = Lancamento.objects.count()

        result, msg = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.ti, imovel, documento
        )

        # Sucesso: lançamento criado
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Lancamento)
        self.assertEqual(Lancamento.objects.count(), lanc_count_before + 1)

        # Origens estruturadas persistidas
        origens = LancamentoOrigem.objects.filter(lancamento=result)
        self.assertGreaterEqual(origens.count(), 1)


class T3RegressaoAtomicidadeTest(Issue241Base):
    """T3: falha genérica em etapa posterior → nada persistido."""

    def test_t3_falha_em_processar_origens_desfaz_tudo(self):
        """Mock de processar_origens_automaticas levantando Exception →
        nenhum lançamento persistido."""
        imovel, documento = self._criar_cenario(matricula="24103")
        post_data = self._post_base(
            origens=["M500"],
            cartorios_ids=[self.cartorio_a.pk],
            cartorios_nomes=[self.cartorio_a.nome],
            sigla="M24103",
        )
        request = RequestFactory().post("/x/", post_data)

        lanc_count_before = Lancamento.objects.count()

        with patch(
            "dominial.services.lancamento_criacao_service."
            "LancamentoOrigemService.processar_origens_automaticas",
            side_effect=RuntimeError("falha simulada #241"),
        ):
            result, msg = LancamentoCriacaoService.criar_lancamento_completo(
                request, self.ti, imovel, documento
            )

        self.assertIsNone(result)
        self.assertIn("Erro ao criar lançamento", msg)
        self.assertEqual(
            Lancamento.objects.count(), lanc_count_before,
            "Lançamento órfão persistido após falha simulada"
        )
