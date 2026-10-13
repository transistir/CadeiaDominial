"""
Issue #227: Autocomplete do cartório da origem deve listar só CRI.

Decisão de design (plano aprovado + co-review):
- Parâmetro `somente_cri=true` enviado pelos campos de origem ao endpoint
  /dominial/cartorio-autocomplete/.
- Filtro por padrão de nome em helper único (q_nome_cri) compartilhado com
  cartorio_imoveis_autocomplete. NÃO mexe em buscar_cartorios/buscar_cidades.
- Campo de transmissão (cartorio_transacao) NÃO é filtrado (tabelionato é
  legítimo).

Co-review (4 ajustes obrigatórios):
- P1: REMOVER o listener sem filtro dos campos de origem (.cartorio-origem-nome)
  — não apenas igualar respostas. O fix deve remover o listener do
  setupCartorioAutocomplete dos campos de origem, não apenas confiar que as
  duas respostas são iguais.
- P2: Busca deve ser insensível a acento (q=Imoveis deve achar 'Imóveis' e
  vice-versa). Implementado via strip de acentos no query + OR.
- P2: renderizador de sugestões NÃO deve usar innerHTML com interpolação
  de dados do cartório (XSS); usar helper com createElement + textContent.
- P2: histórico vazio deve sincronizar o estado de teclado do autocomplete
  (currentSuggestions/índice/display) para não deixar setas/Enter pendurados.

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

Revisão r2 (fix-brief-227-r2.md):
- P1: XSS armazenado — helper `preencherSugestaoCartorio` monta spans via
  createElement + textContent em todos os 3 pontos; teste-guarda assertNotRegex
  veta innerHTML com interpolação de cartorio.nome/formatarLocalizacaoCartorio.
- P2: histórico vazio — mostrarSugestoesCartorioOrigem sincroniza também lista
  vazia (`_setCurrentSuggestions([])` + ocultar div) e descarta resposta
  obsoleta quando o input mudou entre fetch e resposta.
- P2: adicionarOrigem() passa a chamar ligarBuscaCartorioOrigem (entra no
  WeakSet); desativarSugestoesCartorioOrigem chama ligarBuscaCartorioOrigem
  no clone após replaceChild (fecha o caso Registro/Averbação).
- P2: testes/doc — fortalecer teste 16 (lê corpo da função alvo); teste-guarda
  XSS; teste que lê corpo de ligarBuscaCartorioOrigem para garantir somenteCri;
  remover `somente_cri=true` do fetch de histórico (backend ignora); docstring
  lista 4 ajustes (era 3).

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

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from dominial.models import Cartorios, TIs, Pessoas, Imovel, Lancamento, LancamentoTipo, Documento
from dominial.tests.segregacao_fixtures import usuario_com_tis


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
        cls._user = User.objects.create_user(username="u227_ac", password="p")
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

    def setUp(self):
        self.client.force_login(self._user)

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
        from dominial.tests.segregacao_fixtures import atribuir_tis
        atribuir_tis(self._user, ti)
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
        cls._user = User.objects.create_user(username="u227_mc", password="p")
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

    def setUp(self):
        self.client.force_login(self._user)

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
        cls._user = User.objects.create_user(username="u227_ba", password="p")
        cls.cri_acento = Cartorios.objects.create(
            nome="Registro de Imóveis de Guaíra", cns="227301",
            cidade="Guaíra", estado="PR",
        )
        cls.cri_sem_acento = Cartorios.objects.create(
            nome="Registro de Imoveis de Maringá", cns="227302",
            cidade="Maringá", estado="PR",
        )

    def setUp(self):
        self.client.force_login(self._user)

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
        # Após r2: adicionarOrigem chama ligarBuscaCartorioOrigem (WeakSet)
        # que internamente passa {somenteCri: true}
        has_somenteCri = 'somenteCri' in add_body
        has_ligar = 'ligarBuscaCartorioOrigem' in add_body
        self.assertTrue(
            has_somenteCri or has_ligar,
            "adicionarOrigem deve ter somenteCri ou chamar ligarBuscaCartorioOrigem"
        )

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
        cls._user = User.objects.create_user(username="u227_bc", password="p")
        cls.cri_com_cedilha = Cartorios.objects.create(
            nome="Foz do Iguaçu - Serviço de Registro de Imóveis", cns="227401",
            cidade="Foz do Iguaçu", estado="PR",
        )

    def setUp(self):
        self.client.force_login(self._user)

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
        cls._user = User.objects.create_user(username="u227_mr", password="p")
        Cartorios.objects.create(
            nome="Registro de Imóveis de Teste", cns="227501",
            cidade="Teste", estado="TE",
        )

    def setUp(self):
        self.client.force_login(self._user)

    def test_metacaracteres_nao_causam_erro_500(self):
        r"""q com metacaracteres regex (R(, [a, a\) deve retornar 200."""
        for q in ["R(", "[a", "a\\", ".*", "^test"]:
            with self.subTest(q=q):
                response = self.client.get(
                    reverse("cartorio-autocomplete"),
                    {"q": q, "somente_cri": "true"},
                )
                self.assertEqual(response.status_code, 200, f"q={q!r} retornou {response.status_code}")



class XSSGuardTest(TestCase):
    """Teste r2 P1: renderizador NÃO usa innerHTML com interpolação de dados do cartório."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'static', 'dominial', 'js', 'lancamento_form.js',
        )
        with open(js_path, 'r', encoding='utf-8') as f:
            cls.js_content = f.read()

    def test_sem_innerHTML_com_interpolacao_de_cartorio(self):
        """Nenhum innerHTML deve interpolar cartorio.nome ou formatarLocalizacaoCartorio."""
        # Padrão: innerHTML = `...${cartorio.nome}...` ou innerHTML = `...${formatarLocalizacaoCartorio(...)}...`
        # Deve usar preencherSugestaoCartorio (createElement + textContent)
        self.assertNotRegex(
            self.js_content,
            r'innerHTML\s*=\s*`[^`]*\$\{cartorio\.nome\}',
            "innerHTML não deve interpolar cartorio.nome (XSS); use preencherSugestaoCartorio"
        )
        self.assertNotRegex(
            self.js_content,
            r'innerHTML\s*=\s*`[^`]*\$\{formatarLocalizacaoCartorio\(',
            "innerHTML não deve interpolar formatarLocalizacaoCartorio (XSS); use preencherSugestaoCartorio"
        )


class HistoricoVazioSyncTest(TestCase):
    """Teste r2 P2: histórico vazio sincroniza estado de teclado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'static', 'dominial', 'js', 'lancamento_form.js',
        )
        with open(js_path, 'r', encoding='utf-8') as f:
            cls.js_content = f.read()

    def test_mostrarSugestoesCartorioOrigem_sincroniza_lista_vazia(self):
        """mostrarSugestoesCartorioOrigem deve chamar _setCurrentSuggestions mesmo com lista vazia."""
        match = re.search(
            r'function\s+mostrarSugestoesCartorioOrigem\s*\([^)]*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match, "mostrarSugestoesCartorioOrigem não encontrada")
        body = match.group(1)
        # Deve chamar _setCurrentSuggestions ANTES do if (data.results && data.results.length > 0)
        self.assertIn('_setCurrentSuggestions', body)
        # Deve ocultar o div quando lista é vazia
        self.assertIn('suggestions.style.display = \'none\'', body)

    def test_mostrarSugestoesCartorioOrigem_descarta_resposta_obsoleta(self):
        """mostrarSugestoesCartorioOrigem deve descartar resposta se input mudou."""
        match = re.search(
            r'function\s+mostrarSugestoesCartorioOrigem\s*\([^)]*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        # Deve capturar valor do input no momento do fetch
        self.assertIn('valorNoFetch', body)
        # Deve comparar input.value !== valorNoFetch
        self.assertIn('input.value !== valorNoFetch', body)

    def test_mostrarSugestoesCartorioOrigem_trim_antes_de_fetch(self):
        """r3: corpo da função deve checar trim() ANTES do fetch (guarda de campo vazio)."""
        match = re.search(
            r'function\s+mostrarSugestoesCartorioOrigem\s*\([^)]*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match, "mostrarSugestoesCartorioOrigem não encontrada")
        body = match.group(1)
        # trim() deve aparecer ANTES do fetch( — garante que campo com texto
        # aborta o histórico antes de disparar a requisição.
        self.assertIn('trim()', body, "trim() não encontrado no corpo da função")
        self.assertIn('fetch(', body, "fetch() não encontrado no corpo da função")
        self.assertLess(
            body.index('trim()'), body.index('fetch('),
            "trim() deve aparecer ANTES de fetch() no corpo de mostrarSugestoesCartorioOrigem"
        )


class LigarBuscaCartorioOrigemSomenteCriTest(TestCase):
    """Teste r2 P2: ligarBuscaCartorioOrigem passa {somenteCri: true}."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'static', 'dominial', 'js', 'lancamento_form.js',
        )
        with open(js_path, 'r', encoding='utf-8') as f:
            cls.js_content = f.read()

    def test_ligarBuscaCartorioOrigem_passa_somenteCri_true(self):
        """ligarBuscaCartorioOrigem deve chamar setupCartorioAutocomplete com {somenteCri: true}."""
        match = re.search(
            r'function\s+ligarBuscaCartorioOrigem\s*\([^)]*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match, "ligarBuscaCartorioOrigem não encontrada")
        body = match.group(1)
        self.assertIn('setupCartorioAutocomplete', body)
        self.assertIn('somenteCri: true', body)


class AdicionarOrigemEDesativarWeakSetTest(TestCase):
    """Teste r2 P2: adicionarOrigem e desativarSugestoes usam ligarBuscaCartorioOrigem (WeakSet)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'static', 'dominial', 'js', 'lancamento_form.js',
        )
        with open(js_path, 'r', encoding='utf-8') as f:
            cls.js_content = f.read()

    def test_adicionarOrigem_chama_ligarBuscaCartorioOrigem(self):
        """adicionarOrigem deve chamar ligarBuscaCartorioOrigem (não setupCartorioAutocomplete direto)."""
        match = re.search(
            r'function\s+adicionarOrigem\s*\(\s*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match, "adicionarOrigem não encontrada")
        body = match.group(1)
        self.assertIn('ligarBuscaCartorioOrigem', body)
        # NÃO deve chamar setupCartorioAutocomplete direto (WeakSet não vê)
        self.assertNotRegex(body, r'setupCartorioAutocomplete\s*\(')

    def test_desativarSugestoesCartorioOrigem_chama_ligarBuscaCartorioOrigem(self):
        """desativarSugestoesCartorioOrigem deve chamar ligarBuscaCartorioOrigem após replaceChild."""
        match = re.search(
            r'function\s+desativarSugestoesCartorioOrigem\s*\(\s*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match, "desativarSugestoesCartorioOrigem não encontrada")
        body = match.group(1)
        self.assertIn('ligarBuscaCartorioOrigem', body)
        # Deve chamar APÓS replaceChild (fecha caso Registro/Averbação)
        self.assertIn('replaceChild', body)


class HistoricoFiltraCriNoBackendTest(TestCase):
    """
    Teste r4 P1 (Greptile): ramo sugestões do backend respeita somente_cri=true.

    Cenário: imóvel com 2 origens históricas — um tabelionato (T) e um CRI (A).
    - GET sugestoes SEM somente_cri → retorna ambos (comportamento preservado).
    - GET sugestoes COM somente_cri=true → retorna só o CRI (filtra com q_nome_cri()).
    """

    @classmethod
    def setUpTestData(cls):
        ti = TIs.objects.create(nome="TI 227-hist", codigo="TI-227-hist", etnia="Teste")
        cls._user = usuario_com_tis('u227_hf', ti)
        cls.cri = Cartorios.objects.create(
            nome="Registro de Imóveis de Guaíra", cns="227601",
            cidade="Guaíra", estado="PR",
        )
        cls.tabelionato = Cartorios.objects.create(
            nome="1º Tabelionato de Notas de Guaíra", cns="227602",
            cidade="Guaíra", estado="PR",
        )
        pessoa = Pessoas.objects.create(nome="Pessoa 227-hist", cpf="22722722799")
        cls.imovel = Imovel.objects.create(
            terra_indigena_id=ti, nome="Imóvel 227-hist", proprietario=pessoa,
            matricula="227-hist-1", tipo_documento_principal="matricula",
            cartorio=cls.cri,
        )
        from datetime import date
        from dominial.models import DocumentoTipo
        doc_tipo = DocumentoTipo.objects.create(tipo="matricula")
        lt = LancamentoTipo.objects.create(tipo="inicio_matricula")
        doc = Documento.objects.create(
            imovel=cls.imovel, tipo=doc_tipo, numero="M227-hist",
            data=date(2026, 1, 1), cartorio=cls.cri,
        )
        Lancamento.objects.create(
            documento=doc, cartorio_origem=cls.tabelionato,
            tipo=lt, numero_lancamento="L-227-hist-1", data=date(2026, 1, 1),
        )
        Lancamento.objects.create(
            documento=doc, cartorio_origem=cls.cri,
            tipo=lt, numero_lancamento="L-227-hist-2", data=date(2026, 1, 2),
        )

    def setUp(self):
        self.client.force_login(self._user)

    def test_sugestoes_sem_somente_cri_retorna_tabelionato_e_cri(self):
        """Sem somente_cri, histórico continua amplo (tabelionato + CRI)."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"imovel_id": self.imovel.id, "sugestoes": "true"},
        )
        self.assertEqual(response.status_code, 200)
        nomes = {r["nome"] for r in response.json()["results"]}
        self.assertIn(self.tabelionato.nome, nomes)
        self.assertIn(self.cri.nome, nomes)

    def test_sugestoes_com_somente_cri_exclui_tabelionato(self):
        """Com somente_cri=true, tabelionato some do histórico (filtra com q_nome_cri())."""
        response = self.client.get(
            reverse("cartorio-autocomplete"),
            {"imovel_id": self.imovel.id, "sugestoes": "true", "somente_cri": "true"},
        )
        self.assertEqual(response.status_code, 200)
        nomes = {r["nome"] for r in response.json()["results"]}
        self.assertIn(self.cri.nome, nomes)
        self.assertNotIn(self.tabelionato.nome, nomes)


class HistoricoFetchComSomenteCriJsTest(TestCase):
    """
    Teste r4 P1 (frontend): os 2 fetches de histórico enviam somente_cri=true.
    - :543 (recarga ao apagar o campo) → condicionado a opcoes.somenteCri.
    - ~:1028 (mostrarSugestoesCartorioOrigem) → sempre (só campos de origem).
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

    def test_mostrarSugestoesCartorioOrigem_envia_somente_cri(self):
        """fetch de histórico em mostrarSugestoesCartorioOrigem envia somente_cri=true."""
        match = re.search(
            r'function\s+mostrarSugestoesCartorioOrigem\s*\([^)]*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match, "mostrarSugestoesCartorioOrigem não encontrada")
        body = match.group(1)
        # O fetch de histórico deve conter somente_cri=true
        fetch_match = re.search(
            r'fetch\s*\(\s*[`\'][^`\']*cartorio-autocomplete[^`\']*sugestoes=true[^`\']*[`\']',
            body,
        )
        self.assertIsNotNone(fetch_match, "fetch de sugestões não encontrado")
        self.assertIn('somente_cri=true', fetch_match.group(0),
            "fetch de histórico (mostrarSugestoesCartorioOrigem) deve enviar somente_cri=true")

    def test_handler_apagar_campo_envia_somente_cri_condicionado(self):
        """
        O fetch de recarga de histórico ao apagar o campo (dentro do handler
        `input` de setupCartorioAutocomplete) inclui somente_cri=true e está
        condicionado a opcoes.somenteCri.
        """
        # Extrair o bloco do handler `input` de setupCartorioAutocomplete:
        # começa em "input.addEventListener('input'" e termina antes da próxima
        # função declarada em nível 1. Usamos um recorte por linhas.
        match = re.search(
            r'function\s+setupCartorioAutocomplete\s*\([^)]*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match, "setupCartorioAutocomplete não encontrada")
        body = match.group(1)
        # Deve ter o bloco if (query.length === 0 && opcoes.somenteCri) seguido
        # de fetch(...) que inclui somente_cri=true.
        self.assertRegex(
            body,
            r'query\.length\s*===\s*0\s*&&\s*opcoes\.somenteCri[\s\S]*?fetch\s*\([^)]*somente_cri=true',
            "fetch de recarga de histórico deve enviar somente_cri=true sob opcoes.somenteCri",
        )


class BuscaDigitadaDescartaRespostaObsoletaTest(TestCase):
    """
    Teste r4 P1 (Greptile): handler de busca digitada captura queryNoFetch
    ANTES do fetch e descarta a resposta se o input mudou.
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

    def test_handler_busca_digitada_tem_guarda_queryNoFetch(self):
        """
        No handler `input` de setupCartorioAutocomplete:
        - queryNoFetch é capturado ANTES do fetch da busca (não do histórico)
        - input.value !== queryNoFetch é comparado ANTES de suggestions.innerHTML
        """
        match = re.search(
            r'function\s+setupCartorioAutocomplete\s*\([^)]*\)\s*\{(.*?)\n\}',
            self.js_content, re.DOTALL,
        )
        self.assertIsNotNone(match, "setupCartorioAutocomplete não encontrada")
        body = match.group(1)
        # queryNoFetch deve aparecer (variável de guarda)
        self.assertIn('queryNoFetch', body,
            "handler de busca digitada deve capturar queryNoFetch")
        # Captura: 'queryNoFetch = input.value'
        m_captura = re.search(r'queryNoFetch\s*=\s*input\.value', body)
        self.assertIsNotNone(m_captura, "captura 'queryNoFetch = input.value' não encontrada")
        # O fetch da BUSCA digitada é o que usa `fetch(url)` (variável `url`).
        # Localizar o fetch que usa 'fetch(url)' após a construção de `let url =`.
        # A última ocorrência de `fetch(` no handler é a da busca (a do histórico
        # vem antes, dentro do bloco query.length === 0).
        fetch_positions = [m.start() for m in re.finditer(r'\bfetch\s*\(', body)]
        self.assertGreaterEqual(len(fetch_positions), 2,
            "esperados ao menos 2 fetches no handler (histórico + busca)")
        last_fetch_pos = fetch_positions[-1]
        self.assertLess(
            m_captura.start(), last_fetch_pos,
            "queryNoFetch = input.value deve aparecer ANTES do fetch() da busca",
        )
        # Guarda: comparação antes de mexer no DOM
        m_guarda = re.search(r'input\.value\s*!==\s*queryNoFetch', body)
        self.assertIsNotNone(m_guarda, "guarda 'input.value !== queryNoFetch' não encontrada")
        # O suggestions.innerHTML da BUSCA digitada é o último no handler
        # (o primeiro está no bloco de recarga de histórico).
        inner_positions = [m.start() for m in re.finditer(r'suggestions\.innerHTML\s*=', body)]
        self.assertGreaterEqual(len(inner_positions), 2,
            "esperados ao menos 2 suggestions.innerHTML = (histórico + busca)")
        last_inner_pos = inner_positions[-1]
        self.assertLess(
            m_guarda.start(), last_inner_pos,
            "guarda deve acontecer ANTES de suggestions.innerHTML = da busca",
        )


class QNomeCRIVariantesImobiliarioTest(TestCase):
    """
    Teste r4 P2 (Codex): q_nome_cri deve incluir as variantes 'imobiliário'
    (masc. com acento) e 'imobiliaria' (fem. sem acento).
    """

    @classmethod
    def setUpTestData(cls):
        cls.masc_acento = Cartorios.objects.create(
            nome="Registro Imobiliário Teste", cns="227701",
            cidade="Teste", estado="TE",
        )
        cls.fem_sem_acento = Cartorios.objects.create(
            nome="Imobiliaria Teste", cns="227702",
            cidade="Teste", estado="TE",
        )
        # Os 4 existentes continuam passando (sanity):
        cls.existentes = []
        for i, (nome, cns) in enumerate([
            ("Registro de Imóveis de Guaíra", "227703"),
            ("Registro de Imoveis de Terra Roxa", "227704"),
            ("Registro Imobiliario de Tacuru", "227705"),
            ("Cartório Imobiliária do Sul", "227706"),
        ], start=1):
            c = Cartorios.objects.create(
                nome=nome, cns=cns, cidade="Cidade", estado="ES",
            )
            cls.existentes.append(c)

    def test_q_nome_cri_inclui_imobiliario_masc_com_acento(self):
        """'Registro Imobiliário Teste' deve passar no filtro (masc. com acento)."""
        from dominial.utils.cartorio_utils import q_nome_cri
        resultados = set(Cartorios.objects.filter(q_nome_cri()))
        self.assertIn(self.masc_acento, resultados)

    def test_q_nome_cri_inclui_imobiliaria_fem_sem_acento(self):
        """'Imobiliaria Teste' deve passar no filtro (fem. sem acento)."""
        from dominial.utils.cartorio_utils import q_nome_cri
        resultados = set(Cartorios.objects.filter(q_nome_cri()))
        self.assertIn(self.fem_sem_acento, resultados)

    def test_q_nome_cri_continua_incluindo_variantes_existentes(self):
        """Sanity: as 4 variantes já existentes continuam passando."""
        from dominial.utils.cartorio_utils import q_nome_cri
        resultados = set(Cartorios.objects.filter(q_nome_cri()))
        for c in self.existentes:
            self.assertIn(c, resultados, f"{c.nome} deveria continuar no resultado")
