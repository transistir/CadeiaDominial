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

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, RequestFactory
from django.urls import reverse

from dominial.models import (
    Cartorios,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
)
from dominial.services.lancamento_campos_service import LancamentoCamposService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.tests.test_issue_144_origem_cartorio import Issue144Rodada3Base

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
