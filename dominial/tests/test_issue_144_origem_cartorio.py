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

Rodada 2 — a `LancamentoOrigem` persistida é a fonte durável do cartório de
cada origem; o cache do formulário é só otimização do POST corrente:
- T6: re-save sem cache preserva cartório/livro/folha das linhas persistidas.
- T7: form de edição pré-preenche o cartório de CADA origem (não o da primeira).
- T8: sem nenhuma fonte de cartório a falha é visível e nada é gravado.
- T9: OrigemAmbiguaError nunca escapa do signal.
- T10: falha na origem 2 de 3 não desfaz a 1 nem impede a 3.
- T11: registro/averbação gravam o cartório próprio de cada origem.

Rodada 3 — a POSIÇÃO (indice_origem) é a chave primária do lookup; origens
textualmente idênticas em cartórios distintos ("T366; T366") deixam de colidir:
- T12: homônimos persistidos resolvem por posição no re-save (documento criado
  em cada cartório).
- T13: cache do formulário com textos idênticos também resolve por posição.
- T14: criação com "T366; T366" e cartórios [A, B] cria DOIS documentos.
- T15: trocar o texto de uma posição não herda o cartório da linha antiga nem
  o de homônimo que não case; troca de ordem re-casa as linhas por identidade.
- T16: edição cuja sync falha reverte TUDO (texto + estruturadas) e a mensagem
  diz que nada foi salvo.
- T17: "T366; T366" em cartórios distintos NÃO é "Origem documental duplicada"
  (a chave de identidade inclui o cartório).
"""
import logging
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory
from django.urls import reverse

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
from dominial.services.lancamento_campos_service import LancamentoCamposService
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


class Issue144Rodada2Base(Issue144Base):
    def criar_origens_persistidas(self, lancamento):
        """M100/A (L1, F1) e T366/B (L2, F2) já gravadas, como após um save."""
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=0, tipo_documento="matricula",
            numero="M100", cartorio=self.cartorio_a, livro="L1", folha="F1",
        )
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=1, tipo_documento="transcricao",
            numero="T366", cartorio=self.cartorio_b, livro="L2", folha="F2",
        )

    def estado_origens(self, lancamento):
        return [
            (o.numero, o.cartorio_id, o.livro, o.folha)
            for o in LancamentoOrigem.objects.filter(lancamento=lancamento)
            .order_by("indice_origem")
        ]


class T6ResaveSemCacheTest(Issue144Rodada2Base):
    def test_t6_resave_sem_cache_preserva_cartorio_livro_folha(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)
        antes = self.estado_origens(lancamento)
        ids_antes = list(
            LancamentoOrigem.objects.filter(lancamento=lancamento)
            .order_by("indice_origem").values_list("pk", flat=True)
        )
        cache.clear()

        LancamentoOrigemService._sincronizar_origens_estruturadas(
            lancamento, ["M100", "T366"], imovel
        )

        self.assertEqual(self.estado_origens(lancamento), antes)
        self.assertEqual(
            list(
                LancamentoOrigem.objects.filter(lancamento=lancamento)
                .order_by("indice_origem").values_list("pk", flat=True)
            ),
            ids_antes,
        )


class T7FormEdicaoTest(Issue144Rodada2Base):
    def test_t7_form_de_edicao_traz_cartorio_de_cada_origem_sem_cache(self):
        User.objects.create_user(username="t7", password="t7pass")
        client = Client()
        client.login(username="t7", password="t7pass")
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)
        cache.clear()

        response = client.get(reverse("editar_lancamento", kwargs={
            "tis_id": self.ti.id, "imovel_id": imovel.id,
            "lancamento_id": lancamento.pk,
        }))

        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(
            [(o["texto"], o["cartorio_id"], o["livro"], o["folha"]) for o in origens],
            [
                ("M100", self.cartorio_a.pk, "L1", "F1"),
                ("T366", self.cartorio_b.pk, "L2", "F2"),
            ],
        )
        html = response.content.decode()
        self.assertIn(f'value="{self.cartorio_b.nome}"', html)

    def test_t7_repost_do_form_de_edicao_nao_troca_cartorio_persistido(self):
        """Ciclo completo: o que o form pré-preenche, volta no POST e o
        re-save mantém as linhas corretas."""
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)
        antes = self.estado_origens(lancamento)
        cache.clear()
        User.objects.create_user(username="t7b", password="t7pass")
        client = Client()
        client.login(username="t7b", password="t7pass")
        url = reverse("editar_lancamento", kwargs={
            "tis_id": self.ti.id, "imovel_id": imovel.id,
            "lancamento_id": lancamento.pk,
        })
        origens = client.get(url).context["origens_separadas"]

        request = RequestFactory().post(url, {
            "origem_completa[]": [o["texto"] for o in origens],
            "cartorio_origem[]": [str(o["cartorio_id"]) for o in origens],
            "cartorio_origem_nome[]": [o["cartorio_nome"] for o in origens],
            "livro_origem[]": [o["livro"] for o in origens],
            "folha_origem[]": [o["folha"] for o in origens],
        })
        LancamentoCamposService._processar_campos_inicio_matricula(request, lancamento)
        LancamentoOrigemService._sincronizar_origens_estruturadas(
            lancamento, ["M100", "T366"], imovel
        )

        self.assertEqual(self.estado_origens(lancamento), antes)


class T8SemFonteDeCartorioTest(Issue144Rodada2Base):
    def test_t8_sem_cache_sem_linha_e_sem_cartorio_origem_falha_visivel(self):
        imovel, _, lancamento = self.criar_cenario_atual("M100; T366", None)
        cache.clear()

        with self.assertRaises(ValidationError):
            LancamentoOrigemService.processar_origens_automaticas(
                lancamento, lancamento.origem, imovel
            )

        self.assertFalse(LancamentoOrigem.objects.filter(lancamento=lancamento).exists())

    def test_t8_edicao_sem_linha_que_case_nao_recai_no_cartorio_da_primeira(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T400", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)  # M100 e T366; T400 é nova
        antes = self.estado_origens(lancamento)
        cache.clear()

        with self.assertRaises(ValidationError):
            LancamentoOrigemService._sincronizar_origens_estruturadas(
                lancamento, ["M100", "T400"], imovel
            )

        self.assertEqual(self.estado_origens(lancamento), antes)


class T9SignalOrigemAmbiguaTest(Issue144Rodada2Base):
    def test_t9_post_save_com_origem_ambigua_nao_propaga_e_loga_excecao(self):
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Atual #144")
        documento = self.criar_documento(
            imovel, self.tipo_matricula, "M999", self.cartorio_a
        )
        cand_1 = self.criar_documento(
            self.criar_imovel("501", self.cartorio_b, nome="C1"),
            self.tipo_transcricao, "T7770", self.cartorio_b,
        )
        cand_2 = self.criar_documento(
            self.criar_imovel("502", self.cartorio_b, nome="C2"),
            self.tipo_transcricao, "T7771", self.cartorio_b,
        )
        original = DocumentoIdentidadeService.resolver

        def resolver(identidade):
            if identidade.numero_normalizado == "777":
                return ResultadoResolucaoDocumento(
                    status="ambiguo", identidade=identidade,
                    candidatos=(cand_1, cand_2),
                )
            return original(identidade)

        with patch.object(
            DocumentoIdentidadeService, "resolver", side_effect=resolver
        ), self.assertLogs(
            "dominial.services.lancamento_origem_service", level=logging.ERROR
        ) as logs:
            lancamento = Lancamento.objects.create(  # dispara o post_save
                documento=documento, tipo=self.tipo_inicio,
                data=date(2026, 1, 2), origem="T777",
                cartorio_origem=self.cartorio_b,
            )

        self.assertTrue(lancamento.pk)
        self.assertTrue(any(r.exc_info for r in logs.records))
        self.assertIn("OrigemAmbiguaError", "\n".join(logs.output))


class T10RollbackPorOrigemTest(Issue144Rodada2Base):
    def test_t10_falha_na_origem_2_de_3_mantem_1_processa_3_e_conta_falha(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366; M300", self.cartorio_a
        )
        _mapeamento(lancamento, [
            ("M100", self.cartorio_a),
            ("T366", self.cartorio_b),
            ("M300", self.cartorio_a),
        ])
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

        for numero in ("100", "300"):
            self.assertTrue(Documento.objects.filter(
                tipo=self.tipo_matricula, numero_normalizado=numero,
                cartorio=self.cartorio_a,
            ).exists(), numero)
        self.assertFalse(Documento.objects.filter(
            tipo=self.tipo_transcricao, numero_normalizado="366",
        ).exists())
        self.assertIn("2 documento(s)", mensagem)
        self.assertIn("1 não puderam ser vinculadas", mensagem)


class T11RegistroAverbacaoTest(Issue144Rodada2Base):
    def _post(self, origens, cartorios):
        return RequestFactory().post("/x/", {
            "origem_completa[]": origens,
            "cartorio_origem[]": [str(c.pk) for c in cartorios],
            "cartorio_origem_nome[]": [c.nome for c in cartorios],
            "livro_origem[]": ["L1", "L2"],
            "folha_origem[]": ["F1", "F2"],
            "area": "",
        })

    def _cenario(self, nome_tipo):
        tipo = LancamentoTipo.objects.create(tipo=nome_tipo)
        imovel = self.criar_imovel("999", self.cartorio_a, nome="Atual #144")
        documento = self.criar_documento(
            imovel, self.tipo_matricula, "M999", self.cartorio_a
        )
        # cartorio_origem = cartório do documento, como o form de criação grava
        # em registro/averbação (`cartorio` do POST).
        lancamento = Lancamento(
            documento=documento, tipo=tipo, data=date(2026, 1, 2),
            origem="M100; T366", cartorio_origem=self.cartorio_a,
        )
        Lancamento.objects.bulk_create([lancamento])
        return imovel, Lancamento.objects.get(documento=documento, tipo=tipo)

    def test_t11_registro_grava_cartorio_proprio_de_cada_origem_sem_cache(self):
        imovel, lancamento = self._cenario("registro")
        cache.clear()

        LancamentoCamposService.processar_campos_por_tipo(
            self._post(["M100", "T366"], [self.cartorio_a, self.cartorio_b]),
            lancamento,
        )
        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, "M100; T366", imovel
        )

        self.assertEqual(self.estado_origens(lancamento), [
            ("M100", self.cartorio_a.pk, "L1", "F1"),
            ("T366", self.cartorio_b.pk, "L2", "F2"),
        ])

    def test_t11_averbacao_grava_cartorio_proprio_de_cada_origem_sem_cache(self):
        imovel, lancamento = self._cenario("averbacao")
        cache.clear()

        LancamentoCamposService.processar_campos_por_tipo(
            self._post(["M100", "T366"], [self.cartorio_a, self.cartorio_b]),
            lancamento,
        )
        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, "M100; T366", imovel
        )

        self.assertEqual(self.estado_origens(lancamento), [
            ("M100", self.cartorio_a.pk, "L1", "F1"),
            ("T366", self.cartorio_b.pk, "L2", "F2"),
        ])


class Issue144Rodada3Base(Issue144Rodada2Base):
    def criar_origens_homonimas(self, lancamento):
        """"T366; T366": índices 0/A e 1/B, livro/folha distintos."""
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=0, tipo_documento="transcricao",
            numero="T366", cartorio=self.cartorio_a, livro="LA1", folha="FA1",
        )
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=1, tipo_documento="transcricao",
            numero="T366", cartorio=self.cartorio_b, livro="LB2", folha="FB2",
        )

    def assert_documento_t366_no_cartorio(self, cartorio):
        self.assertTrue(
            Documento.objects.filter(
                tipo=self.tipo_transcricao, numero_normalizado="366",
                cartorio=cartorio,
            ).exists(),
            f"documento T366 não criado no cartório {cartorio.nome}",
        )


class T12LookupPosicionalPersistidoTest(Issue144Rodada3Base):
    def test_t12_homonimos_persistidos_resolvem_por_posicao_no_resave(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366", self.cartorio_a
        )
        self.criar_origens_homonimas(lancamento)
        antes = self.estado_origens(lancamento)
        cache.clear()

        # Lookup direto: a posição 1 devolve o cartório B (e seu livro/folha).
        dados = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "T366", indice_origem=1, total_origens=2
        )
        self.assertEqual(dados["cartorio"], self.cartorio_b)
        self.assertEqual((dados["livro"], dados["folha"]), ("LB2", "FB2"))

        # Re-save completo com cache limpo: cada posição re-processa com o
        # cartório PRÓPRIO — documento criado em A E em B, linhas preservadas.
        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem, imovel
        )

        self.assert_documento_t366_no_cartorio(self.cartorio_a)
        self.assert_documento_t366_no_cartorio(self.cartorio_b)
        self.assertEqual(self.estado_origens(lancamento), antes)


class T13LookupPosicionalCacheTest(Issue144Rodada3Base):
    def test_t13_cache_com_textos_iguais_resolve_por_posicao(self):
        _, _, lancamento = self.criar_cenario_atual("T366; T366", self.cartorio_a)
        _mapeamento(lancamento, [
            ("T366", self.cartorio_a), ("T366", self.cartorio_b),
        ])

        dados_pos_0 = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "T366", indice_origem=0, total_origens=2
        )
        dados_pos_1 = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "T366", indice_origem=1, total_origens=2
        )
        self.assertEqual(dados_pos_0["cartorio"], self.cartorio_a)
        self.assertEqual(dados_pos_1["cartorio"], self.cartorio_b)


class T14CriacaoHomominimosTest(Issue144Rodada3Base):
    def test_t14_criacao_com_homonimos_cria_documento_em_ambos_cartorios(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366", self.cartorio_a
        )
        cache.clear()
        request = RequestFactory().post("/x/", {
            "origem_completa[]": ["T366", "T366"],
            "cartorio_origem[]": [str(self.cartorio_a.pk), str(self.cartorio_b.pk)],
            "cartorio_origem_nome[]": [self.cartorio_a.nome, self.cartorio_b.nome],
            "livro_origem[]": ["LA1", "LB2"],
            "folha_origem[]": ["FA1", "FB2"],
        })
        LancamentoCamposService._processar_campos_inicio_matricula(
            request, lancamento
        )

        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem, imovel
        )

        self.assert_documento_t366_no_cartorio(self.cartorio_a)
        self.assert_documento_t366_no_cartorio(self.cartorio_b)
        self.assertEqual(self.estado_origens(lancamento), [
            ("T366", self.cartorio_a.pk, "LA1", "FA1"),
            ("T366", self.cartorio_b.pk, "LB2", "FB2"),
        ])


class T15EdicaoTrocaOrigemTest(Issue144Rodada3Base):
    def test_t15_texto_novo_na_posicao_nao_herda_cartorio_da_linha_antiga(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366", self.cartorio_a
        )
        self.criar_origens_homonimas(lancamento)
        antes = self.estado_origens(lancamento)
        cache.clear()

        # Usuário trocou a posição 1 para M999 sem cartório mapeado: a linha
        # antiga da posição (T366/B) não pode emprestar seu cartório.
        dados = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "M999", indice_origem=1, total_origens=2
        )
        self.assertIsNone(dados["cartorio"])

        with self.assertRaises(ValidationError):
            LancamentoOrigemService._sincronizar_origens_estruturadas(
                lancamento, ["T366", "M999"], imovel
            )
        self.assertEqual(self.estado_origens(lancamento), antes)

    def test_t15_troca_de_ordem_recasa_linhas_por_identidade(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; M999", self.cartorio_a
        )
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=0, tipo_documento="transcricao",
            numero="T366", cartorio=self.cartorio_a, livro="LA1", folha="FA1",
        )
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=1, tipo_documento="matricula",
            numero="M999", cartorio=self.cartorio_b, livro="LB2", folha="FB2",
        )
        cache.clear()

        # "T366; M999" virou "M999; T366": cada identidade leva seu cartório
        # para a nova posição.
        LancamentoOrigemService._sincronizar_origens_estruturadas(
            lancamento, ["M999", "T366"], imovel
        )

        self.assertEqual(self.estado_origens(lancamento), [
            ("M999", self.cartorio_b.pk, "LB2", "FB2"),
            ("T366", self.cartorio_a.pk, "LA1", "FA1"),
        ])


class T16AtomicidadeEdicaoTest(Issue144Rodada3Base):
    def test_t16_edicao_com_origem_sem_cartorio_falha_e_nada_e_salvo(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        Lancamento.objects.filter(pk=lancamento.pk).update(numero_lancamento="1")
        self.criar_origens_persistidas(lancamento)
        antes_origens = self.estado_origens(lancamento)
        cache.clear()
        User.objects.create_user(username="t16", password="t16pass")
        client = Client()
        client.login(username="t16", password="t16pass")

        # Usuário trocou a 2ª origem para M999 sem cartório mapeado.
        response = client.post(reverse("editar_lancamento", kwargs={
            "tis_id": self.ti.id, "imovel_id": imovel.id,
            "lancamento_id": lancamento.pk,
        }), {
            "tipo_lancamento": str(lancamento.tipo_id),
            "numero_lancamento": "1",
            "data": "2026-01-02",
            "observacoes": "",
            "origem_completa[]": ["M100", "M999"],
            "cartorio_origem[]": [str(self.cartorio_a.pk), ""],
            "cartorio_origem_nome[]": [self.cartorio_a.nome, ""],
            "livro_origem[]": ["L1", ""],
            "folha_origem[]": ["F1", ""],
        })

        self.assertEqual(response.status_code, 200)
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.origem, "M100; T366")
        self.assertEqual(
            Lancamento.objects.get(pk=lancamento.pk).numero_lancamento, "1"
        )
        self.assertEqual(self.estado_origens(lancamento), antes_origens)
        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("Nenhuma alteração foi salva" in m for m in mensagens),
            mensagens,
        )


class T17NaoDuplicataTest(Issue144Rodada3Base):
    def test_t17_homonimos_em_cartorios_distintos_nao_sao_duplicados(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366", self.cartorio_a
        )
        self.criar_origens_homonimas(lancamento)
        antes = self.estado_origens(lancamento)
        cache.clear()

        # A chave de identidade inclui o cartório: não é "Origem documental
        # duplicada", e as duas linhas são reaproveitadas nas suas posições.
        LancamentoOrigemService._sincronizar_origens_estruturadas(
            lancamento, ["T366", "T366"], imovel
        )

        self.assertEqual(self.estado_origens(lancamento), antes)
