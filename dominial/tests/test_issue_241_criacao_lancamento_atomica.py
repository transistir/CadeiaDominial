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
from dominial.tests.segregacao_fixtures import usuario_com_tis
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
            "apos_importacao": "true",  # flag POST não é mais lida (#132); kwarg interno apos_importacao=True
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
        request.user = usuario_com_tis('t241', self.ti)

        lanc_count_before = Lancamento.objects.count()
        origem_count_before = LancamentoOrigem.objects.count()
        pessoa_count_before = LancamentoPessoa.objects.count()
        doc_count_before = Documento.objects.count()

        result, msg = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.ti, imovel, documento
        )

        # O erro deve ser retornado ao caller
        self.assertIsNone(result)
        self.assertIn("Criação cancelada", msg)
        self.assertIn("Cartório obrigatório para a origem 1", msg)
        self.assertIn("Nenhum lançamento foi salvo", msg)

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
        request.user = usuario_com_tis('t241', self.ti)

        lanc_count_before = Lancamento.objects.count()

        result, msg = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.ti, imovel, documento, apos_importacao=True
        )

        # Sucesso: lançamento criado
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Lancamento)
        self.assertEqual(Lancamento.objects.count(), lanc_count_before + 1)

        # Origens estruturadas persistidas: exatamente 2 (M500 + T600),
        # com cartórios corretos nas posições 0/1, e mensagem de origens
        # não vazia (o service sempre retorna uma string descritiva).
        origens = list(
            LancamentoOrigem.objects.filter(lancamento=result).order_by('id')
        )
        self.assertEqual(len(origens), 2)
        self.assertEqual(origens[0].cartorio_id, self.cartorio_a.pk)
        self.assertEqual(origens[1].cartorio_id, self.cartorio_b.pk)


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
        request.user = usuario_com_tis('t241', self.ti)

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
        self.assertIn("Criação cancelada", msg)
        # S8 (#132): erro interno não vaza para a mensagem do usuário
        self.assertNotIn("falha simulada", msg)
        self.assertIn("Nenhum lançamento foi salvo", msg)
        self.assertEqual(
            Lancamento.objects.count(), lanc_count_before,
            "Lançamento órfão persistido após falha simulada"
        )


class T4DocumentoMemoriaRollbackTest(Issue241Base):
    """T4 (BLOCKER Opus): rollback do atomic desfaz o banco, mas a instância
    ``documento_ativo`` passada ao service fica com livro/folha SUJOS em
    memória (escritos por ``_aplicar_campos_documento`` e
    ``RegraPetreaService.aplicar_regra_petrea`` ANTES da falha). A view
    re-renderiza com essa instância → ``doc_livro_definido=True`` → campo
    Livro disabled com valor não salvo → no reenvio o campo disabled não
    vai no POST e o livro se perde em silêncio.

    FIX: ``documento_ativo.refresh_from_db()`` no except, depois do
    rollback automático do atomic."""

    def test_t4_documento_em_memoria_limpo_apos_rollback(self):
        """Documento SEM livro/folha + POST com livro_documento='7' e 2
        origens sem cartório → após erro, documento_ativo.livro deve
        estar vazio NA INSTÂNCIA EM MEMÓRIA (não só no banco)."""
        # Documento sem livro/folha (fixture padrão cria com livro="1")
        imovel = self.criar_imovel(
            "24104", self.cartorio_a, nome="Imóvel #24104"
        )
        documento = Documento.objects.create(
            imovel=imovel,
            tipo=self.tipo_transcricao,  # transcrição tem folha
            numero="T24104",
            data="2026-01-01",
            cartorio=self.cartorio_a,
            livro="",
            folha="",
        )

        post_data = self._post_base(
            origens=["M500", "T600"],
            cartorios_ids=["", ""],
            cartorios_nomes=["", ""],
            sigla="T24104",
        )
        post_data["livro_documento"] = "7"
        post_data["folha_documento"] = "42"
        request = RequestFactory().post("/x/", post_data)
        request.user = usuario_com_tis('t241', self.ti)

        result, msg = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.ti, imovel, documento
        )

        # Erro retornado
        self.assertIsNone(result)
        self.assertIn("Criação cancelada", msg)
        self.assertIn("Cartório obrigatório para a origem 1", msg)
        self.assertIn("Nenhum lançamento foi salvo", msg)

        # (a) BLOCKER: instância em memória deve estar LIMPA após o rollback
        #     (ANTES do fix esta asserção falha com livro='7' / folha='42')
        self.assertFalse(
            documento.livro and documento.livro != '0',
            f"documento_ativo.livro sujo em memória após rollback: "
            f"'{documento.livro}' — view re-renderizaria com campo disabled "
            f"e o livro se perderia no reenvio"
        )
        self.assertFalse(
            documento.folha and documento.folha != '0',
            f"documento_ativo.folha suja em memória após rollback: "
            f"'{documento.folha}'"
        )

        # (b) Banco também limpo (rollback funcionou)
        doc_db = Documento.objects.get(pk=documento.pk)
        self.assertIn(doc_db.livro, ("", None, "0"))
        self.assertIn(doc_db.folha, ("", None, "0"))
