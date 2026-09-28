"""
Issue #144 fase 2 — follow-ups do PR #226 (plano r2).

- O mapeamento origem→cartório/livro/folha sai do cache LocMem (uma hora de
  TTL, um por processo) e vira um atributo temporário da instância do
  lançamento: vive exatamente os uma requisição/um save, não vaza para
  POSTs seguintes nem entre workers (D4).
- Cada entrada do mapeamento ganha `'indice'`: a POSIÇÃO no texto filtrado
  e unido, contando fins de cadeia — o mesmo número de
  `LancamentoOrigem.indice_origem` (D1).
"""
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, SimpleTestCase
from django.urls import reverse

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
    OrigemFimCadeia,
)
from dominial.services.lancamento_campos_service import LancamentoCamposService
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.services.regra_petrea_service import RegraPetreaService
from dominial.tests.test_issue_144_origem_cartorio import Issue144Rodada3Base
from dominial.tests.test_issue_159_162_form_bugs import FormBugsBase

# Atributo temporário da instância (D4), como literal: o RED dos testes não
# pode depender da API nova.
ATRIBUTO = '_mapeamento_origens_post'
# Chave do cache LocMem que o PR #226 gravava — nenhum código de produção
# pode voltar a usá-la.
CHAVE_LEGADA = 'mapeamento_origens_lancamento_{}'


def _mapeamento_indexado(lancamento, itens):
    """Grava o mapeamento no formato novo (D1/D2): (indice, origem, cartório,
    livro, folha)."""
    LancamentoOrigemService.definir_mapeamento(lancamento, [
        {
            'indice': indice,
            'origem': origem,
            'cartorio_id': cartorio.pk,
            'cartorio_nome': cartorio.nome,
            'livro': livro,
            'folha': folha,
        }
        for indice, origem, cartorio, livro, folha in itens
    ])


class Fase2Base(Issue144Rodada3Base):
    def _cenario(self, nome_tipo, matricula="999"):
        """Cópia do helper T11 (test_issue_144_origem_cartorio.py:588-601).

        O documento deriva da matrícula para não colidir na constraint
        (tipo, numero_normalizado, cartorio) quando o helper roda mais de
        uma vez no mesmo teste.
        """
        tipo, _ = LancamentoTipo.objects.get_or_create(tipo=nome_tipo)
        imovel = self.criar_imovel(
            matricula, self.cartorio_a, nome="Atual #144"
        )
        documento = self.criar_documento(
            imovel, self.tipo_matricula, f"M{matricula}", self.cartorio_a
        )
        lancamento = Lancamento(
            documento=documento, tipo=tipo, data=date(2026, 1, 2),
            origem="M100; T366", cartorio_origem=self.cartorio_a,
        )
        Lancamento.objects.bulk_create([lancamento])
        return imovel, Lancamento.objects.get(documento=documento, tipo=tipo)

    def _url_edicao(self, imovel, lancamento):
        return reverse("editar_lancamento", kwargs={
            "tis_id": self.ti.id, "imovel_id": imovel.id,
            "lancamento_id": lancamento.pk,
        })

    def _login(self, rotulo):
        User.objects.create_user(
            username=rotulo, password=f"{rotulo}-f2pass"
        )
        client = Client()
        client.login(username=rotulo, password=f"{rotulo}-f2pass")
        return client

    def _post_edicao(self, lancamento, origens, cartorios_ids,
                     cartorios_nomes=None, livros=None, folhas=None):
        """POST de edição no padrão do T16; registro/averbação levam o número
        simples que `atualizar_lancamento_completo` exige."""
        total = len(origens)
        payload = {
            "tipo_lancamento": str(lancamento.tipo_id),
            "numero_lancamento": "1",
            "data": "2026-01-02",
            "observacoes": "",
            "origem_completa[]": list(origens),
            "cartorio_origem[]": [str(c) for c in cartorios_ids],
            "cartorio_origem_nome[]": (
                cartorios_nomes if cartorios_nomes is not None
                else [""] * total
            ),
            "livro_origem[]": livros if livros is not None else [""] * total,
            "folha_origem[]": folhas if folhas is not None else [""] * total,
        }
        if lancamento.tipo.tipo in ("registro", "averbacao"):
            payload["numero_lancamento_simples"] = "1"
        return payload

    def _estado_completo(self, lancamento):
        """(indice, numero, cartorio_id, livro, folha) na ordem do índice."""
        return [
            (o.indice_origem, o.numero, o.cartorio_id, o.livro, o.folha)
            for o in LancamentoOrigem.objects.filter(lancamento=lancamento)
            .order_by("indice_origem")
        ]


class F2_01IndiceNoTextoUnidoTest(Fase2Base):
    """D1: `indice` é a posição no TEXTO FILTRADO E UNIDO, não a do POST."""

    def test_f2_01_inicio_matricula_grava_indice_da_posicao_no_texto(self):
        casos = [
            (
                "linha em branco não desloca o índice",
                ["T366", "", "T366", "M100"],
                [str(self.cartorio_a.pk), "", str(self.cartorio_b.pk), ""],
                [(0, "T366", self.cartorio_a.pk),
                 (1, "T366", self.cartorio_b.pk)],
            ),
            (
                "fim de cadeia conta para o índice",
                ["Destacamento Público:X:origem_lidima", "T366"],
                ["", str(self.cartorio_a.pk)],
                [(1, "T366", self.cartorio_a.pk)],
            ),
        ]
        for deslocamento, (rotulo, origens, cartorios, esperado) in enumerate(casos):
            with self.subTest(rotulo):
                imovel = self.criar_imovel(
                    f"91{deslocamento}", self.cartorio_a, nome=f"Atual F2-01 {rotulo}"
                )
                documento = self.criar_documento(
                    imovel, self.tipo_matricula,
                    f"M9{deslocamento}1", self.cartorio_a,
                )
                lancamento = Lancamento(
                    documento=documento, tipo=self.tipo_inicio,
                    data=date(2026, 1, 2), origem="",
                )
                Lancamento.objects.bulk_create([lancamento])
                request = RequestFactory().post("/x/", {
                    "origem_completa[]": origens,
                    "cartorio_origem[]": cartorios,
                    "cartorio_origem_nome[]": [
                        self.cartorio_a.nome if c == str(self.cartorio_a.pk)
                        else self.cartorio_b.nome if c == str(self.cartorio_b.pk)
                        else ""
                        for c in cartorios
                    ],
                    "livro_origem[]": ["LA1", "", "LB2", ""][:len(origens)],
                    "folha_origem[]": ["FA1", "", "FB2", ""][:len(origens)],
                })
                LancamentoCamposService._processar_campos_inicio_matricula(
                    request, lancamento
                )

                mapeamento = LancamentoOrigemService.obter_mapeamento(
                    lancamento
                )
                self.assertEqual(
                    [
                        (item["indice"], item["origem"], item["cartorio_id"])
                        for item in mapeamento
                    ],
                    esperado,
                )


class F2_02RegistroAverbacaoIndiceTest(Fase2Base):
    """D1 no caminho de registro/averbação (`_registrar_mapeamento_origens`)."""

    def test_f2_02_registro_e_averbacao_gravam_indice_da_posicao_no_texto(self):
        for deslocamento, nome_tipo in enumerate(("registro", "averbacao")):
            with self.subTest(nome_tipo):
                _, lancamento = self._cenario(nome_tipo, matricula=f"92{deslocamento}")
                request = RequestFactory().post("/x/", {
                    "origem_completa[]": ["T366", "", "T366", "M100"],
                    "cartorio_origem[]": [
                        str(self.cartorio_a.pk), "", str(self.cartorio_b.pk), "",
                    ],
                    "cartorio_origem_nome[]": [
                        self.cartorio_a.nome, "", self.cartorio_b.nome, "",
                    ],
                    "livro_origem[]": ["LA1", "", "LB2", ""],
                    "folha_origem[]": ["FA1", "", "FB2", ""],
                    "area": "",
                })
                LancamentoCamposService.processar_campos_por_tipo(
                    request, lancamento
                )

                mapeamento = LancamentoOrigemService.obter_mapeamento(
                    lancamento
                )
                self.assertEqual(
                    [
                        (item["indice"], item["origem"], item["cartorio_id"])
                        for item in mapeamento
                    ],
                    [(0, "T366", self.cartorio_a.pk),
                     (1, "T366", self.cartorio_b.pk)],
                )


class F2_12MapeamentoAposEdicaoTest(Fase2Base):
    """Item 4: nenhum mapeamento sobrevive à edição (sucesso OU falha)."""

    def test_f2_12a_edicao_com_sucesso_nao_deixa_mapeamento(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        client = self._login("f2_12a")
        url = self._url_edicao(imovel, lancamento)
        origens = client.get(url).context["origens_separadas"]

        response = client.post(url, self._post_edicao(
            lancamento,
            [o["texto"] for o in origens],
            [o["cartorio_id"] for o in origens],
            cartorios_nomes=[o["cartorio_nome"] for o in origens],
            livros=[o["livro"] for o in origens],
            folhas=[o["folha"] for o in origens],
        ))

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(cache.get(CHAVE_LEGADA.format(lancamento.pk)))

    def test_f2_12b_edicao_com_falha_nao_deixa_mapeamento(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        client = self._login("f2_12b")
        url = self._url_edicao(imovel, lancamento)

        response = client.post(url, self._post_edicao(
            lancamento,
            ["M100", "M999"],
            [str(self.cartorio_a.pk), ""],
            cartorios_nomes=[self.cartorio_a.nome, ""],
            livros=["L1", ""],
            folhas=["F1", ""],
        ))

        self.assertEqual(response.status_code, 200)
        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("Nenhuma alteração foi salva" in m for m in mensagens),
            mensagens,
        )
        self.assertIsNone(cache.get(CHAVE_LEGADA.format(lancamento.pk)))

    def test_f2_12c_reenvio_apos_falha_nao_reaproveita_dados_rejeitados(self):
        imovel, lancamento = self._cenario("registro")
        self.criar_origens_persistidas(lancamento)
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        antes = self.estado_origens(lancamento)
        cartorio_c = Cartorios.objects.create(
            nome="Cartório C F2", cns="CNS-C-F2", cidade="Cidade C",
            estado="SP",
        )
        client = self._login("f2_12c")
        url = self._url_edicao(imovel, lancamento)

        # POST 1 rejeitado: M999 (posição 3) sem cartório.
        resposta1 = client.post(url, self._post_edicao(
            lancamento,
            ["M100", "T400", "M999"],
            [str(self.cartorio_a.pk), str(cartorio_c.pk), ""],
            cartorios_nomes=[self.cartorio_a.nome, cartorio_c.nome, ""],
        ))
        self.assertEqual(resposta1.status_code, 200)

        # POST 2 sem cartórios: o reenvio não pode herdar T400→C do POST 1.
        resposta2 = client.post(url, self._post_edicao(
            lancamento, ["M100", "T400"], ["", ""],
        ))
        self.assertEqual(resposta2.status_code, 200)
        mensagens = [str(m) for m in resposta2.context["messages"]]
        self.assertTrue(
            any("Cartório obrigatório para a origem 2" in m for m in mensagens),
            mensagens,
        )
        self.assertEqual(self.estado_origens(lancamento), antes)


class F2_14WriterSemOrigensTest(Fase2Base):
    """Item 4: o writer sem origens não pode deixar mapeamento anterior."""

    def test_f2_14_writer_sem_origens_nao_deixa_mapeamento_anterior(self):
        residuo = [{
            'indice': 0, 'origem': 'M100',
            'cartorio_id': self.cartorio_b.pk,
            'cartorio_nome': self.cartorio_b.nome,
            'livro': 'LR', 'folha': 'FR',
        }]
        sequencia = enumerate(
            (nome_tipo, rotulo, extra)
            for nome_tipo in ("inicio_matricula", "registro", "averbacao")
            for rotulo, extra in (
                ("arrays ausentes", {}),
                ("só espaços", {"origem_completa[]": ["  ", " "]}),
                ("campo singular", {"origem_completa": "M100"}),
            )
        )
        for numero, (nome_tipo, rotulo, extra) in sequencia:
            with self.subTest(tipo=nome_tipo, payload=rotulo):
                tipo, _ = LancamentoTipo.objects.get_or_create(
                    tipo=nome_tipo
                )
                imovel = self.criar_imovel(
                    f"93{numero:02d}", self.cartorio_a,
                    nome=f"Imóvel F2-14 {nome_tipo} {rotulo}",
                )
                documento = self.criar_documento(
                    imovel, self.tipo_matricula,
                    f"M9{numero:02d}", self.cartorio_a,
                )
                lancamento = Lancamento(
                    documento=documento, tipo=tipo, data=date(2026, 1, 2),
                    origem="M100", cartorio_origem=self.cartorio_a,
                )
                Lancamento.objects.bulk_create([lancamento])

                # Resíduo de um POST anterior: cache legado + atributo.
                cache.set(CHAVE_LEGADA.format(lancamento.pk), residuo)
                setattr(lancamento, ATRIBUTO, residuo)

                request = RequestFactory().post("/x/", extra)
                LancamentoCamposService.processar_campos_por_tipo(
                    request, lancamento
                )

                self.assertIsNone(getattr(lancamento, ATRIBUTO, None))
                dados = LancamentoOrigemService._buscar_dados_origem(
                    lancamento, "M100", indice_origem=0, total_origens=1
                )
                self.assertEqual(dados["cartorio"], self.cartorio_a)

    def test_f2_14b_retorno_antecipado_limpa_mapeamento(self):
        """Cobre o `return` antecipado de `_registrar_mapeamento_origens`
        quando não há `origem_completa[]` no POST."""
        _, _, lancamento = self.criar_cenario_atual("M100", self.cartorio_a)
        setattr(lancamento, ATRIBUTO, [{
            'indice': 0, 'origem': 'M100',
            'cartorio_id': self.cartorio_b.pk,
            'cartorio_nome': self.cartorio_b.nome, 'livro': None, 'folha': None,
        }])

        request = RequestFactory().post("/x/", {})
        LancamentoCamposService._registrar_mapeamento_origens(
            request, lancamento
        )

        self.assertFalse(hasattr(lancamento, ATRIBUTO))


class F2_16InstanciaCompartilhadaTest(Fase2Base):
    """D4: writer, signal e chamada explícita leem o mapeamento na MESMA
    instância; instância nova resolve pelas linhas persistidas."""

    def test_f2_16_signal_save_e_chamada_explicita_usam_a_mesma_instancia(self):
        imovel, _, lancamento = self.criar_cenario_atual("", None)
        request = RequestFactory().post("/x/", {
            "origem_completa[]": ["T366", "T366"],
            "cartorio_origem[]": [
                str(self.cartorio_a.pk), str(self.cartorio_b.pk),
            ],
            "cartorio_origem_nome[]": [
                self.cartorio_a.nome, self.cartorio_b.nome,
            ],
            "livro_origem[]": ["LA1", "LB2"],
            "folha_origem[]": ["FA1", "FB2"],
        })
        LancamentoCamposService._processar_campos_inicio_matricula(
            request, lancamento
        )
        self.assertIsNone(cache.get(CHAVE_LEGADA.format(lancamento.pk)))

        esperado = [
            (0, "T366", self.cartorio_a.pk, "LA1", "FA1"),
            (1, "T366", self.cartorio_b.pk, "LB2", "FB2"),
        ]

        # 1) save() com o signal post_save ativo, na mesma instância.
        lancamento.save()
        self.assertEqual(self._estado_completo(lancamento), esperado)
        ids = list(
            LancamentoOrigem.objects.filter(lancamento=lancamento)
            .order_by("indice_origem").values_list("pk", flat=True)
        )

        # 2) chamada explícita na mesma instância: atributo ainda presente.
        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem, imovel
        )
        self.assertEqual(self._estado_completo(lancamento), esperado)
        self.assertEqual(
            list(
                LancamentoOrigem.objects.filter(lancamento=lancamento)
                .order_by("indice_origem").values_list("pk", flat=True)
            ),
            ids,
        )

        # 3) instância NOVA (sem atributo e sem cache): as linhas persistidas
        # resolvem por posição.
        novo = Lancamento.objects.get(pk=lancamento.pk)
        novo.save()
        self.assertEqual(self._estado_completo(novo), esperado)
        self.assertEqual(
            list(
                LancamentoOrigem.objects.filter(lancamento=lancamento)
                .order_by("indice_origem").values_list("pk", flat=True)
            ),
            ids,
        )
        self.assertIsNone(cache.get(CHAVE_LEGADA.format(lancamento.pk)))


class F2_03SeletorIndexadoTest(Fase2Base):
    """D2: o seletor usa o 'indice' de cada entrada; D3: homônima sem entrada
    nunca recebe cartório por texto."""

    def test_f2_03_mapeamento_indexado_parcial_resolve_homonimos_por_posicao(self):
        _, _, lancamento = self.criar_cenario_atual(
            "T366; T366; M100", self.cartorio_a
        )
        # Só a linha da posição 2 (M100/A) existe.
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=2,
            tipo_documento="matricula", numero="M100",
            cartorio=self.cartorio_a, livro="LM", folha="FM",
        )
        _mapeamento_indexado(lancamento, [
            (0, "T366", self.cartorio_a, "LA", "FA"),
            (1, "T366", self.cartorio_b, "LB", "FB"),
        ])

        dados_0 = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "T366", indice_origem=0, total_origens=3
        )
        dados_1 = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "T366", indice_origem=1, total_origens=3
        )
        dados_2 = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "M100", indice_origem=2, total_origens=3
        )

        self.assertEqual(dados_0["cartorio"], self.cartorio_a)
        self.assertEqual(dados_1["cartorio"], self.cartorio_b)
        self.assertEqual(dados_2["cartorio"], self.cartorio_a)
        self.assertEqual((dados_2["livro"], dados_2["folha"]), ("LM", "FM"))

    def test_f2_03b_lista_fora_de_ordem_usa_indice(self):
        _, _, lancamento = self.criar_cenario_atual(
            "T366; T366; M100", self.cartorio_a
        )
        # Ordem física da lista é ignorada: vale o 'indice' de cada entrada.
        _mapeamento_indexado(lancamento, [
            (2, "M100", self.cartorio_b, "LC", "FC"),
            (1, "T366", self.cartorio_b, "LB", "FB"),
            (0, "T366", self.cartorio_a, "LA", "FA"),
        ])

        for posicao, texto, esperado in (
            (0, "T366", self.cartorio_a),
            (1, "T366", self.cartorio_b),
            (2, "M100", self.cartorio_b),
        ):
            with self.subTest(posicao=posicao):
                dados = LancamentoOrigemService._buscar_dados_origem(
                    lancamento, texto, indice_origem=posicao, total_origens=3
                )
                self.assertEqual(dados["cartorio"], esperado)

    def test_f2_03c_indices_esparsos_homonima_sem_entrada_exige_cartorio(self):
        _, _, lancamento = self.criar_cenario_atual(
            "M100; T366; T366", self.cartorio_a
        )
        self.assertFalse(
            LancamentoOrigem.objects.filter(lancamento=lancamento).exists()
        )
        _mapeamento_indexado(lancamento, [
            (0, "M100", self.cartorio_a, "LA", "FA"),
            (2, "T366", self.cartorio_b, "LB", "FB"),
        ])

        dados_1 = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "T366", indice_origem=1, total_origens=3
        )
        dados_2 = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "T366", indice_origem=2, total_origens=3
        )

        # A posição 1 não pode herdar B por texto (P1-1): é homônima sem
        # entrada e sem linha — falha visível.
        self.assertIsNone(dados_1["cartorio"])
        self.assertTrue(dados_1["ambiguo"])
        self.assertEqual(dados_2["cartorio"], self.cartorio_b)


class F2_04PosicaoSemEntradaTest(Fase2Base):
    """Item 5: posição sem entrada não herda entrada homônima de outra
    posição — a linha persistida da PRÓPRIA posição resolve."""

    def test_f2_04_posicao_sem_entrada_nao_herda_entrada_homonima(self):
        _, _, lancamento = self.criar_cenario_atual("T366; T366", self.cartorio_a)
        self.criar_origens_homonimas(lancamento)
        _mapeamento_indexado(lancamento, [
            (0, "T366", self.cartorio_a, "LA1", "FA1"),
        ])

        dados_1 = LancamentoOrigemService._buscar_dados_origem(
            lancamento, "T366", indice_origem=1, total_origens=2
        )

        self.assertEqual(dados_1["cartorio"], self.cartorio_b)
        self.assertEqual((dados_1["livro"], dados_1["folha"]), ("LB2", "FB2"))


class F2_05EdicaoComMapeamentoParcialTest(Fase2Base):
    """Item 6: o POST real com mapeamento parcial (última origem sem cartório)
    usa a linha persistida da posição."""

    def test_f2_05_edicao_com_mapeamento_parcial_usa_linha_persistida_da_posicao(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366; M100", self.cartorio_a
        )
        self.criar_origens_homonimas(lancamento)
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=2,
            tipo_documento="matricula", numero="M100",
            cartorio=self.cartorio_a, livro="L1", folha="F1",
        )
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        antes = self._estado_completo(lancamento)
        client = self._login("f2_05")
        url = self._url_edicao(imovel, lancamento)

        response = client.post(url, self._post_edicao(
            lancamento,
            ["T366", "T366", "M100"],
            [str(self.cartorio_a.pk), str(self.cartorio_b.pk), ""],
            cartorios_nomes=[self.cartorio_a.nome, self.cartorio_b.nome, ""],
            livros=["LA1", "LB2", "L1"],
            folhas=["FA1", "FB2", "F1"],
        ))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._estado_completo(lancamento), antes)


class F2_06ErroCitaPosicaoSemCartorioTest(Fase2Base):
    """Item 3: o erro cita a posição que está SEM cartório, não a primeira."""

    def test_f2_06_erro_cita_a_posicao_sem_cartorio(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366", self.cartorio_a
        )
        self.criar_origens_homonimas(lancamento)
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        antes = self._estado_completo(lancamento)
        client = self._login("f2_06")
        url = self._url_edicao(imovel, lancamento)

        response = client.post(url, self._post_edicao(
            lancamento,
            ["T366", "T366", "M100"],
            [str(self.cartorio_a.pk), str(self.cartorio_b.pk), ""],
            cartorios_nomes=[self.cartorio_a.nome, self.cartorio_b.nome, ""],
            livros=["LA1", "LB2", ""],
            folhas=["FA1", "FB2", ""],
        ))

        self.assertEqual(response.status_code, 200)
        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("Cartório obrigatório para a origem 3" in m for m in mensagens),
            mensagens,
        )
        self.assertFalse(
            any("origem 1" in m for m in mensagens),
            mensagens,
        )
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.origem, "T366; T366")
        self.assertEqual(self._estado_completo(lancamento), antes)


class F2_07FormEdicaoHomonimosSemLinhaTest(Fase2Base):
    """D3 no GET: homônimos sem linha estruturada abrem em branco (nem a
    herança do cartório do lançamento, nem resíduo de cache legado)."""

    def test_f2_07_form_edicao_homonimos_sem_linha_ficam_em_branco(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366", self.cartorio_a
        )
        cartorio_c = Cartorios.objects.create(
            nome="Cartório C F2-07", cns="CNS-C-F207",
            cidade="Cidade C", estado="SP",
        )
        # Resíduo pré-fase-2 no cache legado: a view não pode ler.
        cache.set(CHAVE_LEGADA.format(lancamento.pk), [
            {
                "origem": "T366", "cartorio_id": cartorio_c.pk,
                "cartorio_nome": cartorio_c.nome, "livro": "LC", "folha": "FC",
            },
        ], timeout=3600)
        client = self._login("f2_07")

        response = client.get(self._url_edicao(imovel, lancamento))

        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 2)
        for origem in origens:
            with self.subTest(indice=origem["index"]):
                self.assertEqual(
                    (origem["cartorio_id"], origem["cartorio_nome"],
                     origem["livro"], origem["folha"]),
                    ("", "", "", ""),
                )


class F2_10bBDiferenteDeATest(Fase2Base):
    """P1-1: homônima nova sem cartório, com cartório DIFERENTE do persistido
    na posição 0.

    Contra bfc6c3de, este cenário falha com `duplicada na posição 2`. Se a
    leitura por posição fosse aplicada **sem** a regra D3, nenhum
    `ValidationError` seria levantado e as linhas virariam
    `[(T366,B),(T366,A)]`: gravação silenciosa (P1-1). Por isso o D3 entra
    no mesmo commit.
    """

    def test_f2_10b_b_diferente_de_a_exige_cartorio(self):
        imovel, _, lancamento = self.criar_cenario_atual("T366", self.cartorio_a)
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=0,
            tipo_documento="transcricao", numero="T366",
            cartorio=self.cartorio_a, livro="LA", folha="FA",
        )
        # O POST inverte: posição 0 com B, posição 1 sem cartório.
        request = RequestFactory().post("/x/", {
            "origem_completa[]": ["T366", "T366"],
            "cartorio_origem[]": [str(self.cartorio_b.pk), ""],
            "cartorio_origem_nome[]": [self.cartorio_b.nome, ""],
            "livro_origem[]": ["LB", ""],
            "folha_origem[]": ["FB", ""],
        })
        LancamentoCamposService._processar_campos_inicio_matricula(
            request, lancamento
        )

        with self.assertRaises(ValidationError) as ctx:
            LancamentoOrigemService._sincronizar_origens_estruturadas(
                lancamento, ["T366", "T366"], imovel
            )

        self.assertIn("Cartório obrigatório para a origem 2", str(ctx.exception))
        self.assertEqual(self.estado_origens(lancamento), [
            ("T366", self.cartorio_a.pk, "LA", "FA"),
        ])


class F2_17FimDeCadeiaAntesDeOrigemTest(Fase2Base):
    """D1/F2-17: fim de cadeia conta para o índice; origens seguintes
    resolvem pelas suas entradas indexadas."""

    def test_f2_17_fluxo_com_fim_de_cadeia_antes_de_origem_documental(self):
        imovel, _, lancamento = self.criar_cenario_atual("", None)
        request = RequestFactory().post("/x/", {
            "origem_completa[]": [
                "Destacamento Público:SIGLA:origem_lidima", "T366", "T366",
            ],
            "cartorio_origem[]": ["", str(self.cartorio_a.pk), str(self.cartorio_b.pk)],
            "cartorio_origem_nome[]": [
                "", self.cartorio_a.nome, self.cartorio_b.nome,
            ],
            "livro_origem[]": ["", "LA1", "LB2"],
            "folha_origem[]": ["", "FA1", "FB2"],
            "fim_cadeia[]": ["0"],
            "tipo_fim_cadeia[]": ["destacamento_publico"],
            "classificacao_fim_cadeia[]": ["origem_lidima"],
        })
        LancamentoCamposService._processar_campos_inicio_matricula(
            request, lancamento
        )
        self.assertEqual(lancamento.origem, (
            "Destacamento Público:SIGLA:origem_lidima; T366; T366"
        ))

        # save() com o signal e a chamada explícita: ambos processam.
        lancamento.save()
        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem, imovel
        )

        self.assertEqual(self._estado_completo(lancamento), [
            (1, "T366", self.cartorio_a.pk, "LA1", "FA1"),
            (2, "T366", self.cartorio_b.pk, "LB2", "FB2"),
        ])
        fim_cadeia = OrigemFimCadeia.objects.get(lancamento=lancamento)
        self.assertEqual(fim_cadeia.indice_origem, 0)
        self.assertEqual(fim_cadeia.tipo_fim_cadeia, "destacamento_publico")
        self.assert_documento_t366_no_cartorio(self.cartorio_a)
        self.assert_documento_t366_no_cartorio(self.cartorio_b)


class F2_20ContratoDoSeletorTest(SimpleTestCase):
    """P2-5: contrato completo de `item_do_mapeamento` (D2)."""

    @staticmethod
    def _item(indice=None, origem="T366", cartorio_id=1):
        entrada = {"origem": origem, "cartorio_id": cartorio_id,
                   "cartorio_nome": f"C{cartorio_id}", "livro": "L", "folha": "F"}
        if indice is not None:
            entrada["indice"] = indice
        return entrada

    def test_f2_20_contrato_do_seletor(self):
        item_do_mapeamento = LancamentoOrigemService.item_do_mapeamento

        # (a) formato novo por índice
        mapeamento = [self._item(0, "T366", 1), self._item(1, "M100", 2)]
        with self.subTest("formato novo por índice"):
            item, ambiguo = item_do_mapeamento(mapeamento, "T366", 0, 2)
            self.assertFalse(ambiguo)
            self.assertEqual(item["cartorio_id"], 1)

        # (b) lista fora de ordem física
        mapeamento = [self._item(1, "M100", 2), self._item(0, "T366", 1)]
        with self.subTest("lista fora de ordem"):
            item, ambiguo = item_do_mapeamento(mapeamento, "T366", 0, 2)
            self.assertFalse(ambiguo)
            self.assertEqual(item["cartorio_id"], 1)

        # (c) índice duplicado
        mapeamento = [self._item(0, "T366", 1), self._item(0, "T366", 2)]
        with self.subTest("índice duplicado"):
            self.assertEqual(
                item_do_mapeamento(mapeamento, "T366", 0, 2), (None, True)
            )

        # (d) chamada sem posição
        with self.subTest("indice_origem None no formato novo"):
            mapeamento = [self._item(0, "T366", 1)]
            self.assertEqual(
                item_do_mapeamento(mapeamento, "T366", None, 1), (None, False)
            )

        # (e) mapeamento misto: só a entrada indexada conta (nunca legado)
        mapeamento = [self._item(0, "T366", 1), self._item(None, "T366", 9)]
        with self.subTest("mapeamento misto"):
            item, ambiguo = item_do_mapeamento(mapeamento, "T366", 0, 2)
            self.assertFalse(ambiguo)
            self.assertEqual(item["cartorio_id"], 1)
            self.assertEqual(
                item_do_mapeamento(mapeamento, "T366", 1, 2), (None, False)
            )

        # (f) 'indice' não-int (str e bool) — entrada descartada
        mapeamento = [
            {"indice": "1", "origem": "T366", "cartorio_id": 1},
            {"indice": True, "origem": "T366", "cartorio_id": 2},
        ]
        with self.subTest("indice não-int"):
            for posicao in (0, 1):
                self.assertEqual(
                    item_do_mapeamento(mapeamento, "T366", posicao, 2),
                    (None, False),
                )

        # (g) texto divergente na posição: a entrada é de outra origem
        mapeamento = [self._item(0, "M100", 1), self._item(1, "T366", 2)]
        with self.subTest("texto divergente na posição"):
            self.assertEqual(
                item_do_mapeamento(mapeamento, "T366", 0, 2), (None, False)
            )

        # (h) legado (sem 'indice' em nenhuma entrada): regra da fase 1
        with self.subTest("legado completo posicional"):
            mapeamento = [self._item(None, "T366", 1), self._item(None, "M100", 2)]
            item, ambiguo = item_do_mapeamento(mapeamento, "T366", 0, 2)
            self.assertFalse(ambiguo)
            self.assertEqual(item["cartorio_id"], 1)
        with self.subTest("legado parcial com 1 candidato"):
            mapeamento = [self._item(None, "T366", 5)]
            item, ambiguo = item_do_mapeamento(mapeamento, "T366", 1, 3)
            self.assertFalse(ambiguo)
            self.assertEqual(item["cartorio_id"], 5)
        with self.subTest("legado parcial com 2 candidatos"):
            mapeamento = [self._item(None, "T366", 1), self._item(None, "T366", 2)]
            self.assertEqual(
                item_do_mapeamento(mapeamento, "T366", 0, 3), (None, True)
            )
        with self.subTest("legado sem posição, candidato único"):
            mapeamento = [self._item(None, "T366", 5)]
            item, ambiguo = item_do_mapeamento(mapeamento, "T366", None, None)
            self.assertFalse(ambiguo)
            self.assertEqual(item["cartorio_id"], 5)


class F2_08HomonimosAmbiguosMensagemTest(Fase2Base):
    """D6: homônimas ambíguas têm mensagem que explica o motivo e cita o
    número da origem."""

    def test_f2_08_homonimos_ambiguos_tem_mensagem_especifica(self):
        # (a) fixture do T18: linhas homônimas com índices legados (5/A, 6/B)
        # que não casam as posições do texto.
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366", self.cartorio_a
        )
        for indice, cartorio in ((5, self.cartorio_a), (6, self.cartorio_b)):
            LancamentoOrigem.objects.create(
                lancamento=lancamento, indice_origem=indice,
                tipo_documento="transcricao", numero="T366",
                cartorio=cartorio, livro=f"L{indice}", folha=f"F{indice}",
            )

        with self.subTest("indices_legados"):
            with self.assertRaises(ValidationError) as ctx:
                LancamentoOrigemService._sincronizar_origens_estruturadas(
                    lancamento, ["T366", "T366"], imovel
                )
            self.assertIn(
                "Cartório obrigatório para a origem 1 (T366): há mais de uma "
                "origem com esse número e não foi possível identificar o "
                "cartório desta posição. Selecione o cartório.",
                str(ctx.exception),
            )

        # (b) cenário do F2-10b: cartório DIFERENTE do persistido na
        # posição 0 — a ambígua é a posição 2. Imóvel/documento próprios
        # (matrícula distinta) para não colidir na constraint de identidade.
        imovel_b = self.criar_imovel("998", self.cartorio_a, nome="Atual F2-08b")
        documento_b = self.criar_documento(
            imovel_b, self.tipo_matricula, "M998", self.cartorio_a
        )
        lancamento_b = Lancamento(
            documento=documento_b, tipo=self.tipo_inicio,
            data=date(2026, 1, 2), origem="T366",
            cartorio_origem=self.cartorio_a,
        )
        Lancamento.objects.bulk_create([lancamento_b])
        LancamentoOrigem.objects.create(
            lancamento=lancamento_b, indice_origem=0,
            tipo_documento="transcricao", numero="T366",
            cartorio=self.cartorio_a, livro="LA", folha="FA",
        )
        request = RequestFactory().post("/x/", {
            "origem_completa[]": ["T366", "T366"],
            "cartorio_origem[]": [str(self.cartorio_b.pk), ""],
            "cartorio_origem_nome[]": [self.cartorio_b.nome, ""],
            "livro_origem[]": ["LB", ""],
            "folha_origem[]": ["FB", ""],
        })
        LancamentoCamposService._processar_campos_inicio_matricula(
            request, lancamento_b
        )

        with self.subTest("b_diferente_de_a"):
            with self.assertRaises(ValidationError) as ctx:
                LancamentoOrigemService._sincronizar_origens_estruturadas(
                    lancamento_b, ["T366", "T366"], imovel_b
                )
            self.assertIn(
                "Cartório obrigatório para a origem 2 (T366): há mais de uma "
                "origem com esse número e não foi possível identificar o "
                "cartório desta posição. Selecione o cartório.",
                str(ctx.exception),
            )


class F2_09MapeamentoLegadoAmbiguoMensagemTest(Fase2Base):
    """D6 no mapeamento LEGADO (sem 'indice'): ambiguidade da fase 1 também
    tem a mensagem específica (cenário do T19a)."""

    def test_f2_09_mapeamento_legado_ambiguo_tem_mensagem_especifica(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366; M100", self.cartorio_a
        )
        # Mapeamento legado (sem 'indice') parcial: 2 entradas para 3 origens.
        LancamentoOrigemService.definir_mapeamento(lancamento, [
            {"origem": "T366", "cartorio_id": self.cartorio_a.pk,
             "cartorio_nome": self.cartorio_a.nome, "livro": "LA", "folha": "FA"},
            {"origem": "T366", "cartorio_id": self.cartorio_b.pk,
             "cartorio_nome": self.cartorio_b.nome, "livro": "LB", "folha": "FB"},
        ])
        self.assertFalse(
            LancamentoOrigem.objects.filter(lancamento=lancamento).exists()
        )

        with self.assertRaises(ValidationError) as ctx:
            LancamentoOrigemService._sincronizar_origens_estruturadas(
                lancamento, ["T366", "T366", "M100"], imovel
            )
        self.assertIn(
            "Cartório obrigatório para a origem 1 (T366): há mais de uma "
            "origem com esse número e não foi possível identificar o "
            "cartório desta posição. Selecione o cartório.",
            str(ctx.exception),
        )


class F2_10aDuplicataCitaPosicaoColidenteTest(Fase2Base):
    """D6: a duplicata cita a posição colidente, não só a própria."""

    def test_f2_10a_duplicata_cita_a_posicao_colidente(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "T366; T366", self.cartorio_a
        )
        # Cartório informado nas DUAS posições — ambas com A: a posição 2
        # colide com a identidade da posição 1.
        _mapeamento_indexado(lancamento, [
            (0, "T366", self.cartorio_a, "LA", "FA"),
            (1, "T366", self.cartorio_a, "LB", "FB"),
        ])

        with self.assertRaises(ValidationError) as ctx:
            LancamentoOrigemService._sincronizar_origens_estruturadas(
                lancamento, ["T366", "T366"], imovel
            )

        self.assertIn(
            "Origem documental duplicada na posição 2: corresponde à origem "
            "da posição 1, com o mesmo tipo, número e cartório.",
            str(ctx.exception),
        )


class F2_11MensagemSemPontoDuploTest(Fase2Base):
    """D6: a mensagem de erro não termina com ponto antes do ponto da
    frase final (POST do T16/F2-12b)."""

    def test_f2_11_mensagem_de_atualizacao_sem_ponto_duplo(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        client = self._login("f2_11")
        url = self._url_edicao(imovel, lancamento)

        response = client.post(url, self._post_edicao(
            lancamento,
            ["M100", "M999"],
            [str(self.cartorio_a.pk), ""],
            cartorios_nomes=[self.cartorio_a.nome, ""],
            livros=["L1", ""],
            folhas=["F1", ""],
        ))

        self.assertEqual(response.status_code, 200)
        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any(
                "Cartório obrigatório para a origem 2. "
                "Nenhuma alteração foi salva." in m
                for m in mensagens
            ),
            mensagens,
        )
        for mensagem in mensagens:
            self.assertNotIn("..", mensagem, mensagem)


class F2_12dFalhaNaEdicaoRerenderizaPostTest(Fase2Base):
    """P1-2: o re-render de erro da edição mostra as origens do POST, não
    as do banco."""

    def test_f2_12d_falha_na_edicao_rerenderiza_origens_do_post(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        client = self._login("f2_12d")
        url = self._url_edicao(imovel, lancamento)

        response = client.post(url, self._post_edicao(
            lancamento,
            ["M100", "M999"],
            [str(self.cartorio_a.pk), ""],
            cartorios_nomes=[self.cartorio_a.nome, ""],
            livros=["L1X", "L9"],
            folhas=["F1", "F9"],
        ))

        self.assertEqual(response.status_code, 200)
        origens = response.context["origens_separadas"]
        self.assertEqual(len(origens), 2)
        self.assertEqual(
            [
                (o["texto"], str(o["cartorio_id"]), o["livro"], o["folha"])
                for o in origens
            ],
            [
                ("M100", str(self.cartorio_a.pk), "L1X", "F1"),
                ("M999", "", "L9", "F9"),
            ],
        )


class F2_12eFalhaNaEdicaoLimpaAtributoTest(Fase2Base):
    """Item 4: `atualizar_lancamento_completo` limpa o atributo mesmo quando
    a atualização falha (chamada direta, sem a view)."""

    def test_f2_12e_falha_na_edicao_limpa_o_atributo(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        request = RequestFactory().post("/x/", self._post_edicao(
            lancamento,
            ["M100", "M999"],
            [str(self.cartorio_a.pk), ""],
            cartorios_nomes=[self.cartorio_a.nome, ""],
        ))

        sucesso, mensagem = LancamentoCriacaoService.atualizar_lancamento_completo(
            request, lancamento, imovel
        )

        self.assertFalse(sucesso)
        self.assertIn("Nenhuma alteração foi salva", mensagem)
        self.assertFalse(hasattr(lancamento, ATRIBUTO))


class F2_13CriacaoLimpaMapeamentoTest(FormBugsBase):
    """Item 4/P1-2: o mapeamento morre com a requisição de CRIAÇÃO — no
    sucesso e nas falhas, antes ou depois do writer."""

    def setUp(self):
        super().setUp()
        DocumentoTipo.objects.get_or_create(tipo="transcricao")
        self.cartorio_a = Cartorios.objects.create(
            nome="Cartório A F2-13", cns="CNS-A-F213",
            cidade="Cidade A", estado="SP",
        )
        self.cartorio_b = Cartorios.objects.create(
            nome="Cartório B F2-13", cns="CNS-B-F213",
            cidade="Cidade B", estado="SP",
        )

    def _request_criacao(self):
        """Registro nº 2 com origens homônimas em cartórios distintos."""
        return RequestFactory().post("/novo/", {
            "tipo_lancamento": str(self.tipo_registro.id),
            "numero_lancamento": "2",
            "numero_lancamento_simples": "2",
            "data": "2020-03-03",
            "origem_completa[]": ["T366", "T366"],
            "cartorio_origem[]": [
                str(self.cartorio_a.pk), str(self.cartorio_b.pk),
            ],
            "cartorio_origem_nome[]": [
                self.cartorio_a.nome, self.cartorio_b.nome,
            ],
            "livro_origem[]": ["LA", "LB"],
            "folha_origem[]": ["FA", "FB"],
        })

    def _criar_e_capturar(self, capturado):
        original = LancamentoCriacaoService._criar_lancamento_basico

        def criar(documento, dados, tipo):
            inst = original(documento, dados, tipo)
            capturado["lancamento"] = inst
            return inst

        return criar

    def test_f2_13a_criacao_com_sucesso_grava_por_posicao_e_nao_deixa_mapeamento(self):
        capturado = {}
        with patch.object(
            LancamentoCriacaoService, '_criar_lancamento_basico',
            side_effect=self._criar_e_capturar(capturado),
        ):
            criado, _ = LancamentoCriacaoService.criar_lancamento_completo(
                self._request_criacao(), self.tis, self.imovel, self.documento
            )

        self.assertIsNotNone(criado)
        lancamento = capturado["lancamento"]
        self.assertEqual(
            [
                (o.indice_origem, o.numero, o.cartorio_id, o.livro, o.folha)
                for o in LancamentoOrigem.objects.filter(lancamento=lancamento)
                .order_by("indice_origem")
            ],
            [
                (0, "T366", self.cartorio_a.pk, "LA", "FA"),
                (1, "T366", self.cartorio_b.pk, "LB", "FB"),
            ],
        )
        self.assertIsNone(cache.get(CHAVE_LEGADA.format(lancamento.pk)))
        self.assertFalse(hasattr(lancamento, ATRIBUTO))

    def test_f2_13b_criacao_falha_depois_do_writer_limpa_mapeamento(self):
        capturado = {}
        with patch.object(
            LancamentoCriacaoService, '_criar_lancamento_basico',
            side_effect=self._criar_e_capturar(capturado),
        ), patch.object(
            RegraPetreaService, 'aplicar_regra_petrea',
            side_effect=RuntimeError('falha F2-13b'),
        ):
            resultado, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
                self._request_criacao(), self.tis, self.imovel, self.documento
            )

        self.assertIsNone(resultado)
        self.assertIn('Erro ao criar lançamento: falha F2-13b', mensagem)
        lancamento = capturado["lancamento"]
        self.assertFalse(hasattr(lancamento, ATRIBUTO))
        self.assertIsNone(cache.get(CHAVE_LEGADA.format(lancamento.pk)))

    def test_f2_13c_criacao_falha_antes_do_lancamento_nao_mascara_erro(self):
        """Guarda do `finally`: sem `lancamento = None` antes do `try`, a
        falha ANTES da atribuição viraria UnboundLocalError e mascara o erro
        real."""
        with patch.object(
            LancamentoCriacaoService, '_criar_lancamento_basico',
            side_effect=RuntimeError('falha F2-13c'),
        ):
            resultado, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
                self._request_criacao(), self.tis, self.imovel, self.documento
            )

        self.assertIsNone(resultado)
        self.assertIn('falha F2-13c', mensagem)
        self.assertNotIn('UnboundLocalError', mensagem)


class F2_18FalhaNaEdicaoPreservaFimCadeiaTest(Fase2Base):
    """P1-3/D7: o writer da edição (que apaga e recria `OrigemFimCadeia`)
    roda na MESMA transação do restante — a falha desfaz tudo, não só o
    `save()`."""

    def _fim_cadeia(self, lancamento):
        """(pk, indice, tipo, classificacao) de cada OrigemFimCadeia."""
        return [
            (f.pk, f.indice_origem, f.tipo_fim_cadeia,
             f.classificacao_fim_cadeia)
            for f in OrigemFimCadeia.objects.filter(lancamento=lancamento)
            .order_by("indice_origem")
        ]

    def test_f2_18_falha_na_edicao_preserva_origem_fim_cadeia(self):
        fim = "Destacamento Público:SIGLA:origem_lidima"
        texto = f"{fim}; M100"
        imovel, _, lancamento = self.criar_cenario_atual(
            texto, self.cartorio_a
        )
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=1, tipo_documento="matricula",
            numero="M100", cartorio=self.cartorio_a, livro="L1", folha="F1",
        )
        OrigemFimCadeia.objects.create(
            lancamento=lancamento, indice_origem=0, fim_cadeia=True,
            tipo_fim_cadeia="destacamento_publico",
            classificacao_fim_cadeia="origem_lidima",
        )
        linhas_antes = self.estado_origens(lancamento)
        fim_cadeia_antes = self._fim_cadeia(lancamento)
        client = self._login("f2_18")

        # M999 (posição 3) sem cartório derruba a edição; o fim de cadeia do
        # POST traz outra classificação, que NÃO pode ter sido gravada.
        payload = self._post_edicao(
            lancamento,
            [fim, "M100", "M999"],
            ["", str(self.cartorio_a.pk), ""],
            cartorios_nomes=["", self.cartorio_a.nome, ""],
            livros=["", "L1", ""],
            folhas=["", "F1", ""],
        )
        payload.update({
            "fim_cadeia[]": ["0"],
            "tipo_fim_cadeia[]": ["destacamento_publico"],
            "classificacao_fim_cadeia[]": ["sem_origem"],
        })
        response = client.post(self._url_edicao(imovel, lancamento), payload)

        self.assertEqual(response.status_code, 200)
        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("Cartório obrigatório para a origem 3" in m for m in mensagens),
            mensagens,
        )
        self.assertEqual(self._fim_cadeia(lancamento), fim_cadeia_antes)
        self.assertEqual(self.estado_origens(lancamento), linhas_antes)
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.origem, texto)


class F2_19FalhaNaEdicaoNaoDeixaCartorioCriadoTest(Fase2Base):
    """P1-3/D7: cartório criado por nome pelo writer da edição some junto
    com o rollback quando a edição falha."""

    def test_f2_19_falha_na_edicao_nao_deixa_cartorio_criado(self):
        imovel, _, lancamento = self.criar_cenario_atual(
            "M100; T366", self.cartorio_a
        )
        self.criar_origens_persistidas(lancamento)
        Lancamento.objects.filter(pk=lancamento.pk).update(
            numero_lancamento="1"
        )
        client = self._login("f2_19")

        # T400 traz um nome de cartório que não existe (o writer o cria);
        # M999 (posição 3) sem cartório derruba a edição.
        response = client.post(
            self._url_edicao(imovel, lancamento),
            self._post_edicao(
                lancamento,
                ["M100", "T400", "M999"],
                [str(self.cartorio_a.pk), "", ""],
                cartorios_nomes=[self.cartorio_a.nome, "Cartório Novo F2", ""],
            ),
        )

        self.assertEqual(response.status_code, 200)
        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("Cartório obrigatório para a origem 3" in m for m in mensagens),
            mensagens,
        )
        self.assertFalse(
            Cartorios.objects.filter(nome="Cartório Novo F2").exists()
        )
