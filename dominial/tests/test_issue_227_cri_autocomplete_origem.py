"""
Issue #227: Autocomplete do cartório da origem deve listar só CRI.

Decisão de design (plano aprovado + co-review):
- Parâmetro `somente_cri=true` enviado pelos campos de origem ao endpoint
  /dominial/cartorio-autocomplete/.
- Filtro por padrão de nome em helper único (q_nome_cri) compartilhado com
  cartorio_imoveis_autocomplete. NÃO mexe em buscar_cartorios/buscar_cidades.
- Campo de transmissão (cartorio_transacao) NÃO é filtrado (tabelionato é
  legítimo).

Co-review (3 ajustes obrigatórios):
- P1: REMOVER o listener sem filtro dos campos de origem (.cartorio-origem-nome)
  — não apenas igualar respostas. O fix deve remover o listener do
  setupCartorioAutocomplete dos campos de origem, não apenas confiar que as
  duas respostas são iguais.
- P2: Busca deve ser insensível a acento (q=Imoveis deve achar 'Imóveis' e
  vice-versa). Implementado via strip de acentos no query + OR.

Revisão r1 (fix-brief-227-r1.md):
- P0/P1: clonagem (desativarSugestoes + adicionarOrigemSimples) remove o
  listener `input` → helper `ligarBuscaCartorioOrigem` (WeakSet) chamado em
  setupOrigemAutocomplete, ativarSugestoesCartorioOrigem e adicionarOrigemSimples.
- P2 'mais usados': campo vazio recarrega histórico com somente_cri=true.
- P2 cidade/UF: renderizador único mostra formatarLocalizacaoCartorio().
- P1 pré-existente: mostrarSugestoesCartorioOrigem chama
  suggestions._setCurrentSuggestions() para sincronizar o estado de teclado.
- P2 'ç': mapa de acentos inclui c/[cçCÇ].
- P2 testes: metacaracteres regex (200 OK), Iguacu → Iguaçu, remover teste 14
  (código morto buscarCartoriosOrigem).

Fixtures (plano seção 5):
  A: "Registro de Imóveis de Guaíra"
  B: "Registro de Imoveis de Terra Roxa"
  C: "Serviço de Registro de Imóveis, Títulos e Documentos e Tabelionato de Protestos de Guaíra"
  D: "Registro Imobiliario de Tacuru"
  T: "1º Tabelionato de Notas de Guaíra"
  N: "Ofício de Notas e Protestos de Guaíra"
  RC: "Registro Civil das Pessoas Naturais de Guaíra"
  O: "Registro de Imóveis de Iguatemi" (tipo='OUTRO')
  Dois "Registro de Imóveis de Autazes" (para testar order_by nome,id)
"""
import os
import re

from django.test import TestCase
from django.urls import reverse

from dominial.models import Cartorios, TIs, Pessoas, Imovel, Lancamento, LancamentoTipo, Documento


class QNomeCRIHelperTest(TestCase):
    """Testa o helper q_nome_cri() que filtra cartórios CRI por padrão de nome."""

    @classmethod
    def setUpTestData(cls):
        cls.A = Cartorios.objects.create(
            nome="Registro de Imóveis de Guaíra", cns="227001",
            cidade="Guaíra", estado="PR",
        )
        cls.B = Cartorios.objects.create(
            nome="Registro de Imoveis de Terra Roxa", cns="227002",
            cidade="Terra Roxa", estado="PR",
        )
        cls.C = Cartorios.objects.create(
            nome="Serviço de Registro de Imóveis, Títulos e Documentos e Tabelionato de Protestos de Guaíra",
            cns="227003", cidade="Guaíra", estado="PR",
        )
        cls.D = Cartorios.objects.create(
            nome="Registro Imobiliario de Tacuru", cns="227004",
            cidade="Tacuru", estado="MS",
        )
        cls.T = Cartorios.objects.create(
            nome="1º Tabelionato de Notas de Guaíra", cns="227005",
            cidade="Guaíra", estado="PR",
        )
        cls.N = Cartorios.objects.create(
            nome="Ofício de Notas e Protestos de Guaíra", cns="227006",
            cidade="Guaíra", estado="PR",
        )
        cls.RC = Cartorios.objects.create(
            nome="Registro Civil das Pessoas Naturais de Guaíra", cns="227007",
            cidade="Guaíra", estado="PR",
        )
        # O: tipo='OUTRO' — deve ser incluído pelo filtro de nome (#150 pendente)
        cls.O = Cartorios.objects.create(
            nome="Registro de Imóveis de Iguatemi", cns="227008",
            cidade="Iguatemi", estado="MS", tipo="OUTRO",
        )

    def test_q_nome_cri_inclui_cartorios_com_imoveis_no_nome(self):
        """Helper deve incluir A, B, C, D e O (todos têm padrão de imóvel no nome)."""
        from dominial.utils.cartorio_utils import q_nome_cri

        resultados = set(Cartorios.objects.filter(q_nome_cri()))
        for expected in [self.A, self.B, self.C, self.D, self.O]:
            self.assertIn(expected, resultados, f"{expected.nome} deveria estar no resultado")

    def test_q_nome_cri_exclui_tabelionato_e_registro_civil(self):
        """Helper deve excluir T (tabelionato), N (notas) e RC (registro civil)."""
        from dominial.utils.cartorio_utils import q_nome_cri

        resultados = set(Cartorios.objects.filter(q_nome_cri()))
        self.assertNotIn(self.T, resultados)
        self.assertNotIn(self.N, resultados)
        self.assertNotIn(self.RC, resultados)


class CartorioAutocompleteSomenteCriTest(TestCase):
    """Testa o parâmetro somente_cri=true no endpoint cartorio-autocomplete."""

    @classmethod
    def setUpTestData(cls):
        cls.A = Cartorios.objects.create(
            nome="Registro de Imóveis de Guaíra", cns="227101",
            cidade="Guaíra", estado="PR",
        )
        cls.B = Cartorios.objects.create(
            nome="Registro de Imoveis de Terra Roxa", cns="227102",
            cidade="Terra Roxa", estado="PR",
        )
        cls.C = Cartorios.objects.create(
            nome="Serviço de Registro de Imóveis, Títulos e Documentos e Tabelionato de Protestos de Guaíra",
            cns="227103", cidade="Guaíra", estado="PR",
        )
        cls.D = Cartorios.objects.create(
            nome="Registro Imobiliario de Tacuru", cns="227104",
            cidade="Tacuru", estado="MS",
        )
        cls.T = Cartorios.objects.create(
            nome="1º Tabelionato de Notas de Guaíra", cns="227105",
            cidade="Guaíra", estado="PR",
        )
        cls.N = Cartorios.objects.create(
            nome="Ofício de Notas e Protestos de Guaíra", cns="227106",
            cidade="Guaíra", estado="PR",
        )
        cls.RC = Cartorios.objects.create(
            nome="Registro Civil das Pessoas Naturais de Guaíra", cns="227107",
            cidade="Guaíra", estado="PR",
        )
        cls.O = Cartorios.objects.create(
            nome="Registro de Imóveis de Iguatemi", cns="227108",
            cidade="Iguatemi", estado="MS", tipo="OUTRO",
        )
        # Dois Autazes para testar order_by('nome', 'id')
        cls.aut1 = Cartorios.objects.create(
            nome="Registro de Imóveis de Autazes", cns="227109",
            cidade="Autazes", estado="AM",
        )
        cls.aut2 = Cartorios.objects.create(
            nome="Registro de Imóveis de Autazes", cns="227110",
            cidade="Autazes", estado="AM",
        )

    # RED 1
    def test_somente_cri_exclui_tabelionato_notas_e_registro_civil(self):
        """q=Guaíra com somente_cri=true → contém A e C; não contém T, N nem RC."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "Guaíra", "somente_cri": "true"},
        )
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        nomes = {r["nome"] for r in results}

        self.assertIn(self.A.nome, nomes)
        self.assertIn(self.C.nome, nomes)
        self.assertNotIn(self.T.nome, nomes)
        self.assertNotIn(self.N.nome, nomes)
        self.assertNotIn(self.RC.nome, nomes)

    # RED 2
    def test_somente_cri_aceita_grafia_com_e_sem_acento(self):
        """q=Registro → contém A, B, D; RC fica fora (não tem padrão imóvel)."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "Registro", "somente_cri": "true"},
        )
        results = response.json()["results"]
        nomes = {r["nome"] for r in results}

        self.assertIn(self.A.nome, nomes)
        self.assertIn(self.B.nome, nomes)
        self.assertIn(self.D.nome, nomes)
        # RC tem "Registro" no nome mas não tem padrão de imóvel
        self.assertNotIn(self.RC.nome, nomes)

    # RED 3
    def test_somente_cri_mantem_serventia_mista(self):
        """q=Tabelionato com somente_cri=true → devolve só C (serventia mista com 'imóveis')."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "Tabelionato", "somente_cri": "true"},
        )
        results = response.json()["results"]
        nomes = {r["nome"] for r in results}

        self.assertIn(self.C.nome, nomes)
        # T é tabelionato puro, não deve aparecer
        self.assertNotIn(self.T.nome, nomes)

    # RED 4
    def test_somente_cri_ignora_campo_tipo_ate_150(self):
        """
        T/N/RC têm tipo='CRI' (default) e ficam fora; O tem tipo='OUTRO' e fica
        dentro (porque o filtro é por nome, não por tipo).
        Este teste muda quando a #150 tornar o campo tipo confiável.
        """
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "Iguatemi", "somente_cri": "true"},
        )
        results = response.json()["results"]
        nomes = {r["nome"] for r in results}

        # O tem tipo='OUTRO' mas nome com 'Imóveis' → incluído
        self.assertIn(self.O.nome, nomes)

    # Guarda 5
    def test_sem_parametro_mantem_busca_ampla(self):
        """Transmissão: sem somente_cri, todos aparecem (incluindo tabelionato)."""
        # Sem parâmetro
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "Guaíra"},
        )
        nomes = {r["nome"] for r in response.json()["results"]}
        self.assertIn(self.T.nome, nomes)
        self.assertIn(self.N.nome, nomes)
        self.assertIn(self.RC.nome, nomes)
        self.assertIn(self.A.nome, nomes)

        # Com somente_cri=false
        with self.subTest("somente_cri=false"):
            response = self.client.get(
                reverse("cartorio-autocomplete"),
                {"q": "Guaíra", "somente_cri": "false"},
            )
            nomes = {r["nome"] for r in response.json()["results"]}
            self.assertIn(self.T.nome, nomes)

    # Guarda 6
    def test_somente_cri_query_curta_retorna_vazio(self):
        """q=R (1 char) → results == []."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "R", "somente_cri": "true"},
        )
        self.assertEqual(response.json()["results"], [])

    # Guarda 7
    def test_resposta_mantem_formato_results(self):
        """Resposta tem chaves id, nome, cidade, estado."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "Guaíra", "somente_cri": "true"},
        )
        results = response.json()["results"]
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("id", r)
            self.assertIn("nome", r)
            self.assertIn("cidade", r)
            self.assertIn("estado", r)

    # Guarda 8
    def test_sugestoes_mais_usados_inalteradas(self):
        """?imovel_id=…&sugestoes=true ainda devolve tabelionato (sem filtro CRI)."""
        from datetime import date
        ti = TIs.objects.create(nome="TI 227", codigo="TI-227", etnia="Teste")
        pessoa = Pessoas.objects.create(nome="Pessoa 227", cpf="22722722727")
        imovel = Imovel.objects.create(
            terra_indigena_id=ti, nome="Imóvel 227", proprietario=pessoa,
            matricula="227-1", tipo_documento_principal="matricula",
            cartorio=self.A,
        )
        from dominial.models import DocumentoTipo
        doc_tipo = DocumentoTipo.objects.create(tipo="matricula")
        lt = LancamentoTipo.objects.create(tipo="inicio_matricula")
        doc = Documento.objects.create(
            imovel=imovel, tipo=doc_tipo, numero="M227", data=date(2026, 1, 1),
            cartorio=self.A,
        )
        Lancamento.objects.create(
            documento=doc, cartorio_origem=self.T,
            tipo=lt, numero_lancamento="L-227-1", data=date(2026, 1, 1),
        )

        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"imovel_id": imovel.id, "sugestoes": "true"},
        )
        results = response.json()["results"]
        nomes = {r["nome"] for r in results}
        # Tabelionato aparece nas sugestões (sem filtro CRI)
        self.assertIn(self.T.nome, nomes)


class MesmoCriterioQueCartorioImoveisTest(TestCase):
    """
    RED 9: Os dois endpoints de autocomplete de CRI devem devolver o mesmo
    conjunto, na mesma ordem, para qualquer query.
    """

    @classmethod
    def setUpTestData(cls):
        Cartorios.objects.create(
            nome="Registro de Imóveis de Guaíra", cns="227201",
            cidade="Guaíra", estado="PR",
        )
        Cartorios.objects.create(
            nome="1º Tabelionato de Notas de Guaíra", cns="227202",
            cidade="Guaíra", estado="PR",
        )
        Cartorios.objects.create(
            nome="Registro de Imoveis de Terra Roxa", cns="227203",
            cidade="Terra Roxa", estado="PR",
        )
        Cartorios.objects.create(
            nome="Registro Imobiliario de Tacuru", cns="227204",
            cidade="Tacuru", estado="MS",
        )
        Cartorios.objects.create(
            nome="Registro Civil das Pessoas Naturais de Guaíra", cns="227205",
            cidade="Guaíra", estado="PR",
        )
        # Dois Autazes
        Cartorios.objects.create(
            nome="Registro de Imóveis de Autazes", cns="227206",
            cidade="Autazes", estado="AM",
        )
        Cartorios.objects.create(
            nome="Registro de Imóveis de Autazes", cns="227207",
            cidade="Autazes", estado="AM",
        )
        Cartorios.objects.create(
            nome="Ofício de Registro de Imóveis de Autazes", cns="227208",
            cidade="Autazes", estado="AM",
        )

    def test_mesmo_conjunto_e_ordem_que_cartorio_imoveis_autocomplete(self):
        """Para q em Guaíra, Registro e Autazes, os ids são iguais e na mesma ordem."""
        for q in ["Guaíra", "Registro", "Autazes"]:
            with self.subTest(q=q):
                # cartorio-autocomplete com somente_cri
                resp1 = self.client.get(
                    reverse("cartorio-autocomplete"),
                    {"q": q, "somente_cri": "true"},
                )
                ids_autocomplete = [r["id"] for r in resp1.json()["results"]]

                # cartorio-imoveis-autocomplete
                resp2 = self.client.get(
                    reverse("cartorio-imoveis-autocomplete"),
                    {"q": q},
                )
                ids_imoveis = [r["id"] for r in resp2.json()]

                self.assertEqual(
                    ids_autocomplete, ids_imoveis,
                    f"Para q={q!r}, os ids diferem: {ids_autocomplete} vs {ids_imoveis}",
                )


class BuscaInsensivelAAcentoTest(TestCase):
    """
    Co-review P2: q=Imoveis deve achar 'Imóveis' e q=Imóveis deve achar 'Imoveis'.
    """

    @classmethod
    def setUpTestData(cls):
        cls.cri_acento = Cartorios.objects.create(
            nome="Registro de Imóveis de Guaíra", cns="227301",
            cidade="Guaíra", estado="PR",
        )
        cls.cri_sem_acento = Cartorios.objects.create(
            nome="Registro de Imoveis de Maringá", cns="227302",
            cidade="Maringá", estado="PR",
        )

    def test_busca_com_acento_encontra_sem_acento(self):
        """q=Imóveis deve encontrar 'Registro de Imoveis' (sem acento)."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "Imóveis", "somente_cri": "true"},
        )
        nomes = {r["nome"] for r in response.json()["results"]}
        self.assertIn(self.cri_sem_acento.nome, nomes)

    def test_busca_sem_acento_encontra_com_acento(self):
        """q=Imoveis deve encontrar 'Registro de Imóveis' (com acento)."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "Imoveis", "somente_cri": "true"},
        )
        nomes = {r["nome"] for r in response.json()["results"]}
        self.assertIn(self.cri_acento.nome, nomes)


class SetupCartorioAutocompleteSomenteCriJsTest(TestCase):
    """
    Testes estáticos sobre lancamento_form.js (regex).
    Segue o padrão de test_issue_187 (ReanexaListenersAposCloneNodeTest).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'static', 'dominial', 'js', 'lancamento_form.js',
        )
        with open(js_path, 'r', encoding='utf-8') as f:
            cls.js_content = f.read()

    # RED 10
    def test_setupCartorioAutocomplete_tem_parametro_opcoes(self):
        """A assinatura de setupCartorioAutocomplete tem o 4º parâmetro opcoes."""
        self.assertRegex(
            self.js_content,
            r'function\s+setupCartorioAutocomplete\s*\(\s*input\s*,\s*hidden\s*,\s*suggestions\s*,\s*opcoes',
        )

    # RED 11
    def test_somente_cri_true_so_sob_opcoes_somenteCri(self):
        """somente_cri=true só entra na URL sob opcoes.somenteCri."""
        # A URL base continua com ?q=...
        self.assertIn('cartorio-autocomplete/?q=', self.js_content)
        # somente_cri=true aparece concatenado condicionalmente
        self.assertIn('somente_cri=true', self.js_content)
        # E está dentro de uma condição sobre opcoes.somenteCri
        self.assertRegex(
            self.js_content,
            r'opcoes\.somenteCri',
        )

    # RED 12
    def test_setupOrigemAutocomplete_e_adicionarOrigem_passam_somenteCri(self):
        """Os corpos de setupOrigemAutocomplete e adicionarOrigem passam {somenteCri: true}."""
        # Extrair o corpo de setupOrigemAutocomplete
        match_setup = re.search(
            r'function\s+setupOrigemAutocomplete\s*\(\s*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match_setup, "setupOrigemAutocomplete não encontrada")
        setup_body = match_setup.group(1)
        # Após r1: setupOrigemAutocomplete delega a ligarBuscaCartorioOrigem
        # que internamente passa {somenteCri: true}
        has_somenteCri = 'somenteCri' in setup_body
        has_ligar = 'ligarBuscaCartorioOrigem' in setup_body
        self.assertTrue(
            has_somenteCri or has_ligar,
            "setupOrigemAutocomplete deve ter somenteCri ou chamar ligarBuscaCartorioOrigem"
        )

        # Extrair o corpo de adicionarOrigem
        match_add = re.search(
            r'function\s+adicionarOrigem\s*\(\s*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match_add, "adicionarOrigem não encontrada")
        add_body = match_add.group(1)
        self.assertIn('somenteCri', add_body)

    # Guarda 13
    def test_cartorio_nome_e_transacao_sem_opcoes(self):
        """
        As chamadas de setupCartorioAutocomplete para cartorio_nome (:232) e
        cartorio_transmissao (:241) continuam com 3 argumentos (sem opcoes).
        """
        # Encontrar chamadas com 3 args (sem 4º argumento)
        # Padrão: setupCartorioAutocomplete(var1, var2, var3);
        # NÃO deve ter setupCartorioAutocomplete(cartorioInput, cartorioHidden, cartorioSuggestions, ...)
        lines = self.js_content.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if 'setupCartorioAutocomplete(' in stripped and 'cartorioTransacao' in stripped:
                # Não deve ter 4º argumento
                self.assertNotIn('somenteCri', stripped,
                    f"Linha {i+1}: cartorio_transmissao não deve ter somenteCri")
            if 'setupCartorioAutocomplete(' in stripped and 'cartorioInput' in stripped:
                self.assertNotIn('somenteCri', stripped,
                    f"Linha {i+1}: cartorio_nome não deve ter somenteCri")

    # Teste 15 (r1): ligarBuscaCartorioOrigem em ativarSugestoesCartorioOrigem
    def test_ativarSugestoesCartorioOrigem_chama_ligarBuscaCartorioOrigem(self):
        """ativarSugestoesCartorioOrigem deve chamar ligarBuscaCartorioOrigem (sem addEventListener('input')."""
        match_ativar = re.search(
            r'function\s+ativarSugestoesCartorioOrigem\s*\(\s*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match_ativar, "ativarSugestoesCartorioOrigem não encontrada")
        ativar_body = match_ativar.group(1)
        self.assertIn('ligarBuscaCartorioOrigem', ativar_body)
        # NÃO deve ter addEventListener('input' (busca é feita pelo helper)
        self.assertNotIn("addEventListener('input'", ativar_body)

    # Teste 16 (r1): origem_simples.js referencia ligarBuscaCartorioOrigem
    def test_origem_simples_referencia_ligarBuscaCartorioOrigem(self):
        """origem_simples.js deve chamar ligarBuscaCartorioOrigem após clonar."""
        js_origem_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'static', 'dominial', 'js', 'origem_simples.js',
        )
        with open(js_origem_path, 'r', encoding='utf-8') as f:
            origem_content = f.read()
        self.assertIn('ligarBuscaCartorioOrigem', origem_content)


class BuscaCedilhaTest(TestCase):
    """Teste r1: 'ç' no mapa de acentos (Iguacu → Iguaçu)."""

    @classmethod
    def setUpTestData(cls):
        cls.cri_com_cedilha = Cartorios.objects.create(
            nome="Foz do Iguaçu - Serviço de Registro de Imóveis", cns="227401",
            cidade="Foz do Iguaçu", estado="PR",
        )

    def test_busca_sem_cedilha_encontra_com_cedilha(self):
        """q=Iguacu deve encontrar 'Foz do Iguaçu'."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"q": "Iguacu", "somente_cri": "true"},
        )
        nomes = {r["nome"] for r in response.json()["results"]}
        self.assertIn(self.cri_com_cedilha.nome, nomes)


class MetacaracteresRegexTest(TestCase):
    """Teste r1: q com metacaracteres regex deve retornar 200 (sem 500)."""

    @classmethod
    def setUpTestData(cls):
        Cartorios.objects.create(
            nome="Registro de Imóveis de Teste", cns="227501",
            cidade="Teste", estado="TE",
        )

    def test_metacaracteres_nao_causam_erro_500(self):
        r"""q com metacaracteres regex (R(, [a, a\) deve retornar 200."""
        for q in ["R(", "[a", "a\\", ".*", "^test"]:
            with self.subTest(q=q):
                response = self.client.get(
                    reverse("cartorio-autocomplete"),
                    {"q": q, "somente_cri": "true"},
                )
                self.assertEqual(response.status_code, 200, f"q={q!r} retornou {response.status_code}")

