"""
Issue #144 (fase 1) — cartório POR ORIGEM + origens não resolvidas visíveis.

Decisões do dono do produto (26/09): nenhuma alteração de dados; o código só
(a) para de criar o problema e (b) torna visível o que não resolve.

- T1 (P0): em lançamento com múltiplas origens, cada origem valida/cria seu
  documento com o cartório DAQUELA origem, comparando a identidade completa
  (tipo + número normalizado + cartório) — nunca o cartório da primeira origem.
- T2: falha na criação automática deixa rastro (logger.exception) e a mensagem
  ao usuário não afirma sucesso.
- T3: a árvore expõe `origens_nao_resolvidas` (nao_encontrado / ambiguo) em vez
  de descartar a aresta em silêncio.
- T4: origem gravada antes do documento passa a resolver quando o documento com
  a mesma identidade é criado depois (ex.: manualmente, em outro imóvel).
- T5: não-regressão do #218 (roda os testes existentes; ver comando na entrega).
"""
import logging
from datetime import date
from unittest.mock import patch

from django.core.cache import cache

from dominial.models import (
    Documento,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
)
from dominial.services.documento_identidade_service import (
    DocumentoIdentidadeService,
    ResultadoResolucaoDocumento,
)
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


def _mapeamento(lancamento, itens):
    """Grava o mapeamento origem→cartório que o formulário deixa em cache."""
    cache.set(
        f"mapeamento_origens_lancamento_{lancamento.pk}",
        [
            {
                "origem": origem,
                "cartorio_id": cartorio.pk,
                "cartorio_nome": cartorio.nome,
                "livro": "1",
                "folha": "1",
            }
            for origem, cartorio in itens
        ],
        timeout=3600,
    )


class Issue144Base(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

    def setUp(self):
        cache.clear()

    def criar_cenario_atual(self, origem, cartorio_origem):
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Atual #144")
        documento = self.criar_documento(
            imovel, self.tipo_matricula, "M999", self.cartorio_a
        )
        lancamento = Lancamento(
            documento=documento,
            tipo=self.tipo_inicio,
            data=date(2026, 1, 2),
            origem=origem,
            cartorio_origem=cartorio_origem,
        )
        # bulk_create não dispara o signal: o processamento é chamado à mão.
        Lancamento.objects.bulk_create([lancamento])
        return imovel, documento, lancamento


class T1CartorioPorOrigemTest(Issue144Base):
    def test_t1_origem2_usa_cartorio_proprio_mesmo_com_homonimo_na_primeira(self):
        # T366 já existe no cartório A, em OUTRO imóvel.
        imovel_outro = self.criar_imovel("500", self.cartorio_a, nome="Outro")
        t366_em_a = self.criar_documento(
            imovel_outro, self.tipo_transcricao, "T366", self.cartorio_a
        )
        imovel, documento_atual, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a  # cartório da PRIMEIRA origem
        )
        _mapeamento(lancamento, [("M100", self.cartorio_a), ("T366", self.cartorio_b)])

        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem, imovel
        )

        t366_em_b = Documento.objects.get(
            tipo=self.tipo_transcricao,
            numero_normalizado="366",
            cartorio=self.cartorio_b,
        )
        self.assertEqual(t366_em_b.imovel_id, imovel.pk)
        self.assertNotEqual(t366_em_b.pk, t366_em_a.pk)
        # O homônimo do cartório A segue intocado no outro imóvel.
        t366_em_a.refresh_from_db()
        self.assertEqual(t366_em_a.imovel_id, imovel_outro.pk)
        self.assertTrue(
            Documento.objects.filter(
                tipo=self.tipo_matricula,
                numero_normalizado="100",
                cartorio=self.cartorio_a,
            ).exists()
        )

        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
        arestas = {(c["from"], c["to"]) for c in arvore["conexoes"]}
        self.assertIn((documento_atual.pk, t366_em_b.pk), arestas)
        self.assertNotIn((documento_atual.pk, t366_em_a.pk), arestas)


class T2FalhaVisivelTest(Issue144Base):
    def test_t2_falha_na_criacao_loga_excecao_e_nao_afirma_sucesso(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        _mapeamento(lancamento, [("M100", self.cartorio_a), ("T366", self.cartorio_b)])

        with patch(
            "dominial.services.lancamento_origem_service.CRIService."
            "criar_documento_com_cri",
            side_effect=RuntimeError("falha simulada #144"),
        ), self.assertLogs(
            "dominial.services.lancamento_origem_service", level=logging.ERROR
        ) as logs:
            mensagem = LancamentoOrigemService.processar_origens_automaticas(
                lancamento, lancamento.origem, imovel
            )

        self.assertTrue(any(r.exc_info for r in logs.records))
        self.assertIn("falha simulada #144", "\n".join(logs.output))
        self.assertIsNotNone(mensagem)
        self.assertNotIn("Foram criados", mensagem)
        self.assertIn("2 origem(ns)", mensagem)
        self.assertIn("não puderam ser vinculadas", mensagem)
        self.assertIn("avisos na árvore", mensagem)

    def test_t2_falha_em_origem_unica_tambem_e_visivel(self):
        imovel, _, lancamento = self.criar_cenario_atual("M100", self.cartorio_a)

        with patch(
            "dominial.services.lancamento_origem_service.CRIService."
            "criar_documento_com_cri",
            side_effect=RuntimeError("falha simulada única"),
        ), self.assertLogs(
            "dominial.services.lancamento_origem_service", level=logging.ERROR
        ):
            mensagem = LancamentoOrigemService.processar_origens_automaticas(
                lancamento, lancamento.origem, imovel
            )

        self.assertNotIn("Foram criados", mensagem)
        self.assertIn("1 origem(ns)", mensagem)
        self.assertIn("não puderam ser vinculadas", mensagem)

    def test_t2_sucesso_parcial_informa_criados_e_falhas(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        _mapeamento(lancamento, [("M100", self.cartorio_a), ("T366", self.cartorio_b)])

        from dominial.services.cri_service import CRIService
        original = CRIService.criar_documento_com_cri

        def falha_na_transcricao(imovel_arg, dados, cri_origem=None):
            if dados["numero"] == "T366":
                raise RuntimeError("falha só na T366")
            return original(imovel_arg, dados, cri_origem=cri_origem)

        with patch(
            "dominial.services.lancamento_origem_service.CRIService."
            "criar_documento_com_cri",
            side_effect=falha_na_transcricao,
        ), self.assertLogs(
            "dominial.services.lancamento_origem_service", level=logging.ERROR
        ):
            mensagem = LancamentoOrigemService.processar_origens_automaticas(
                lancamento, lancamento.origem, imovel
            )

        self.assertIn("1 documento(s)", mensagem)
        self.assertIn("1 não puderam ser vinculadas", mensagem)


class T3OrigensNaoResolvidasTest(Issue144Base):
    def _no(self, arvore, documento):
        return next(n for n in arvore["documentos"] if n["id"] == documento.pk)

    def test_t3_origem_inexistente_vira_nao_encontrado(self):
        imovel, documento, lancamento = self.criar_cenario_atual(
            "M888", self.cartorio_b
        )
        LancamentoOrigem.objects.create(
            lancamento=lancamento,
            indice_origem=0,
            tipo_documento="matricula",
            numero="M888",
            cartorio=self.cartorio_b,
        )

        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        no = self._no(arvore, documento)
        self.assertEqual(
            no["origens_nao_resolvidas"],
            [
                {
                    "numero": "M888",
                    "tipo_documento": "matricula",
                    "cartorio_nome": self.cartorio_b.nome,
                    "status": "nao_encontrado",
                    "candidatos": [],
                }
            ],
        )
        self.assertEqual(arvore["conexoes"], [])

    def test_t3_origem_ambigua_lista_candidatos(self):
        imovel, documento, lancamento = self.criar_cenario_atual(
            "T777", self.cartorio_b
        )
        imovel_1 = self.criar_imovel("501", self.cartorio_b, nome="Cand 1")
        imovel_2 = self.criar_imovel("502", self.cartorio_b, nome="Cand 2")
        # A constraint global do banco de teste impede dois documentos com a
        # mesma identidade; a ambiguidade (que existe em produção, onde a
        # restrição inclui imovel_id) é simulada no resolvedor.
        cand_1 = self.criar_documento(
            imovel_1, self.tipo_transcricao, "T7770", self.cartorio_b
        )
        cand_2 = self.criar_documento(
            imovel_2, self.tipo_transcricao, "T7771", self.cartorio_b
        )
        LancamentoOrigem.objects.create(
            lancamento=lancamento,
            indice_origem=0,
            tipo_documento="transcricao",
            numero="T777",
            cartorio=self.cartorio_b,
        )
        original = DocumentoIdentidadeService.resolver

        def resolver(identidade):
            if identidade.numero_normalizado == "777":
                return ResultadoResolucaoDocumento(
                    status="ambiguo",
                    identidade=identidade,
                    candidatos=(cand_1, cand_2),
                )
            return original(identidade)

        with patch.object(
            DocumentoIdentidadeService, "resolver", side_effect=resolver
        ):
            arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        no = self._no(arvore, documento)
        self.assertEqual(len(no["origens_nao_resolvidas"]), 1)
        entrada = no["origens_nao_resolvidas"][0]
        self.assertEqual(entrada["status"], "ambiguo")
        self.assertEqual(entrada["candidatos"], [cand_1.pk, cand_2.pk])
        self.assertEqual(entrada["numero"], "T777")
        self.assertEqual(entrada["tipo_documento"], "transcricao")
        self.assertEqual(entrada["cartorio_nome"], self.cartorio_b.nome)
        self.assertEqual(arvore["conexoes"], [])

    def test_t3_sem_pendencias_o_campo_existe_e_vem_vazio(self):
        imovel, documento, _ = self.criar_cenario_atual("", None)

        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        self.assertEqual(self._no(arvore, documento)["origens_nao_resolvidas"], [])

    def test_t3_retrocompatibilidade_do_payload(self):
        imovel, documento, _ = self.criar_cenario_atual("", None)

        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        for chave in ("imovel", "documentos", "origens_identificadas", "conexoes"):
            self.assertIn(chave, arvore)
        no = self._no(arvore, documento)
        for chave in ("id", "numero", "tipo", "cartorio", "nivel", "total_cadeias"):
            self.assertIn(chave, no)


class T4RegressaoT585Test(Issue144Base):
    def test_t4_origem_gravada_antes_do_documento_resolve_apos_criacao(self):
        imovel, documento, lancamento = self.criar_cenario_atual(
            "T585", self.cartorio_b
        )
        LancamentoOrigem.objects.create(
            lancamento=lancamento,
            indice_origem=0,
            tipo_documento="transcricao",
            numero="T585",
            cartorio=self.cartorio_b,
        )

        antes = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
        self.assertEqual(antes["conexoes"], [])
        no_antes = next(n for n in antes["documentos"] if n["id"] == documento.pk)
        self.assertEqual(
            [o["status"] for o in no_antes["origens_nao_resolvidas"]],
            ["nao_encontrado"],
        )

        # Usuário cria o documento à mão, em outro imóvel, com a mesma identidade.
        outro_imovel = self.criar_imovel("585", self.cartorio_b, nome="Dono da T585")
        t585 = self.criar_documento(
            outro_imovel, self.tipo_transcricao, "T585", self.cartorio_b
        )

        depois = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
        self.assertEqual(
            {(c["from"], c["to"]) for c in depois["conexoes"]},
            {(documento.pk, t585.pk)},
        )
        no_depois = next(n for n in depois["documentos"] if n["id"] == documento.pk)
        self.assertEqual(no_depois["origens_nao_resolvidas"], [])
