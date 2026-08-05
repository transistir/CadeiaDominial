"""Testes de regressão para issue #118.

Livro/folha da ORIGEM (``livro_origem[]`` / ``folha_origem[]``) nunca devem ser
aplicados ao documento ATUAL. O documento atual só recebe livro/folha de
``livro_documento`` / ``folha_documento``.

Os 3 pontos de vazamento cobertos aqui:
1. ``LancamentoFormService.processar_dados_lancamento`` — leitura dos arrays
2. ``LancamentoCriacaoService._aplicar_campos_documento`` — fallback de herança
3. ``RegraPetreaService._definir_livro_folha_documento`` — prioriza ``livro_origem``

Os testes de múltiplas origens (Tarefa 6) garantem que CADA origem preserva seu
próprio livro/folha nos registros ``LancamentoOrigem``.
"""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.services.lancamento_form_service import LancamentoFormService
from dominial.services.lancamento_heranca_service import LancamentoHerancaService
from dominial.services.regra_petrea_service import RegraPetreaService


class TestIssue118LivroFolhaOrigemNaoVaza(TestCase):
    """O documento atual não deve herdar livro/folha da origem."""

    def setUp(self):
        self.tis = TIs.objects.create(nome="TI #118", codigo="T118", etnia="Teste")
        self.pessoa = Pessoas.objects.create(nome="Pessoa #118", cpf="99988877766")
        self.cri = Cartorios.objects.create(
            nome="CRI #118", cns="118118", cidade="Cidade", estado="SP"
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel #118",
            proprietario=self.pessoa,
            matricula="118",
            tipo_documento_principal="matricula",
            cartorio=self.cri,
        )
        self.documento_a = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="100",
            data=timezone.now().date(),
            cartorio=self.cri,
            livro="",
            folha="",
        )
        self.rf = RequestFactory()

    # ------------------------------------------------------------------
    # Vetor 1: LancamentoFormService — leitura dos arrays
    # ------------------------------------------------------------------
    def test_form_service_le_livro_origem_como_array_nao_scalar(self):
        """``livro_origem[]``/``folha_origem[]`` chegam como arrays no form."""
        request = self.rf.post("/lancamento/", {
            "livro_documento": "",
            "folha_documento": "",
            "livro_origem[]": ["5"],
            "folha_origem[]": ["10"],
        })
        dados = LancamentoFormService.processar_dados_lancamento(request, self.tipo_inicio)

        # livro/folha_documento ficam vazios (documento atual sem livro/folha)
        self.assertIn(dados.get("livro_documento"), (None, ""))
        self.assertIn(dados.get("folha_documento"), (None, ""))
        # livro/folha_origem capturam o valor da origem
        self.assertEqual(dados.get("livro_origem"), "5")
        self.assertEqual(dados.get("folha_origem"), "10")

    def test_form_service_livro_origem_nao_vaza_para_livro_documento(self):
        """Mesmo quando só há origem, ``livro_documento`` fica vazio."""
        request = self.rf.post("/lancamento/", {
            "livro_documento": "",
            "folha_documento": "",
            "livro_origem[]": ["5"],
            "folha_origem[]": ["10"],
        })
        dados = LancamentoFormService.processar_dados_lancamento(request, self.tipo_inicio)

        self.assertNotEqual(dados.get("livro_documento"), "5")
        self.assertNotEqual(dados.get("folha_documento"), "10")

    # ------------------------------------------------------------------
    # Vetor 2: _aplicar_campos_documento — remover fallback de herança
    # ------------------------------------------------------------------
    def test_aplicar_campos_documento_nao_herda_livro_origem(self):
        """BUG #118: o documento atual recebia livro/folha da origem."""
        lancamento = Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            cartorio_origem=self.cri,
        )
        dados = {
            "livro_documento": "",   # documento atual sem livro
            "folha_documento": "",   # documento atual sem folha
            "livro_origem": "5",     # livro da ORIGEM
            "folha_origem": "10",    # folha da ORIGEM
        }

        LancamentoCriacaoService._aplicar_campos_documento(lancamento, dados)

        self.documento_a.refresh_from_db()
        # CORE: livro/folha da origem NÃO vazam para o documento atual
        self.assertNotIn(
            self.documento_a.livro, ("5", " 5 ".strip()),
            f"BUG #118: documento atual recebeu livro da origem: {self.documento_a.livro!r}",
        )
        self.assertNotIn(
            self.documento_a.folha, ("10",),
            f"BUG #118: documento atual recebeu folha da origem: {self.documento_a.folha!r}",
        )

    def test_aplicar_campos_documento_usa_livro_documento_quando_fornecido(self):
        """Quando ``livro_documento`` vem preenchido, ele é aplicado."""
        lancamento = Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            cartorio_origem=self.cri,
        )
        dados = {
            "livro_documento": "7",   # documento atual COM livro
            "folha_documento": "8",   # documento atual COM folha
            "livro_origem": "5",
            "folha_origem": "10",
        }

        LancamentoCriacaoService._aplicar_campos_documento(lancamento, dados)

        self.documento_a.refresh_from_db()
        self.assertEqual(self.documento_a.livro, "7")
        self.assertEqual(self.documento_a.folha, "8")

    # ------------------------------------------------------------------
    # Vetor 3: RegraPetreaService — não usar lancamento.livro_origem
    # ------------------------------------------------------------------
    def test_regra_petrea_nao_usa_livro_origem_para_documento_atual(self):
        """BUG #118: a regra pétrea copiava ``lancamento.livro_origem``."""
        lancamento = Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            cartorio_origem=self.cri,
            livro_origem="5",    # livro da ORIGEM
            folha_origem="10",   # folha da ORIGEM
        )

        RegraPetreaService._definir_livro_folha_documento(lancamento)

        self.documento_a.refresh_from_db()
        self.assertNotEqual(
            self.documento_a.livro, "5",
            f"BUG #118: regra pétrea vazou livro da origem: {self.documento_a.livro!r}",
        )
        self.assertNotEqual(
            self.documento_a.folha, "10",
            f"BUG #118: regra pétrea vazou folha da origem: {self.documento_a.folha!r}",
        )

    def test_regra_petrea_usa_livro_transacao_para_documento_atual(self):
        """A regra pétrea ainda pode usar ``livro_transacao`` (campo correto)."""
        lancamento = Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            cartorio_origem=self.cri,
            livro_origem="5",         # origem — NÃO deve vazar
            folha_origem="10",
            livro_transacao="7",      # transação — caminho correto
            folha_transacao="8",
        )

        RegraPetreaService._definir_livro_folha_documento(lancamento)

        self.documento_a.refresh_from_db()
        self.assertEqual(self.documento_a.livro, "7")
        self.assertEqual(self.documento_a.folha, "8")

    def test_regra_petrea_preserva_livro_ja_no_documento(self):
        """Se o documento já tem livro (via form service), a regra pétrea preserva."""
        self.documento_a.livro = "9"
        self.documento_a.folha = "11"
        self.documento_a.save()

        lancamento = Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            cartorio_origem=self.cri,
            livro_origem="5",
            folha_origem="10",
        )

        RegraPetreaService._definir_livro_folha_documento(lancamento)

        self.documento_a.refresh_from_db()
        # o documento preserva o livro que já tinha (9/11), não herda da origem
        self.assertEqual(self.documento_a.livro, "9")
        self.assertEqual(self.documento_a.folha, "11")

    # ------------------------------------------------------------------
    # Vetor 4 (review Codex): LancamentoHerancaService — herança não
    # propaga livro_origem/folha_origem do primeiro lançamento para o
    # segundo. Esses campos pertencem à ORIGEM, não ao documento atual.
    # ------------------------------------------------------------------
    def test_heranca_nao_propaga_livro_origem_para_novo_lancamento(self):
        """O segundo lançamento de um documento NÃO herda livro_origem/folha_origem
        do primeiro lançamento. Apenas cartorio_origem pode ser herdado."""
        # Primeiro lançamento COM origem (livro_origem/folha_origem preenchidos)
        Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            cartorio_origem=self.cri,
            livro_origem="5",
            folha_origem="10",
        )

        # Novo lançamento no mesmo documento (subsequente)
        novo_lancamento = Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
        )

        LancamentoHerancaService.herdar_dados_para_novo_lancamento(
            self.documento_a, novo_lancamento
        )
        novo_lancamento.refresh_from_db()

        # livro_origem/folha_origem NÃO devem ser herdados (são da origem)
        self.assertNotIn(
            novo_lancamento.livro_origem, ("5",),
            f"BUG #118: herança propagou livro_origem: {novo_lancamento.livro_origem!r}",
        )
        self.assertNotIn(
            novo_lancamento.folha_origem, ("10",),
            f"BUG #118: herança propagou folha_origem: {novo_lancamento.folha_origem!r}",
        )
        # cartorio_origem PODE ser herdado (legítimo)
        # (não há assert de igualdade obrigatória — apenas confirmamos que
        # livro/folha_origem não vazam)

    def test_obter_dados_nao_retorna_livro_origem_do_primeiro(self):
        """dados_primeiro não inclui livro_origem/folha_origem — são da origem,
        não devem ser herdados por lançamentos subsequentes."""
        # Primeiro lançamento com livro_origem/folha_origem preenchidos
        Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            cartorio_origem=self.cri,
            livro_origem="5",
            folha_origem="10",
        )

        dados = LancamentoHerancaService.obter_dados_primeiro_lancamento(
            self.documento_a
        )

        self.assertIsNotNone(dados, "Deve retornar dados do primeiro lançamento")
        # livro_origem/folha_origem NÃO devem estar no resultado (ou devem ser
        # vazios), pois pertencem à origem, não ao documento atual.
        self.assertNotIn(
            dados.get("livro_origem"), ("5",),
            f"BUG #118: dados_primeiro incluiu livro_origem: {dados.get('livro_origem')!r}",
        )
        self.assertNotIn(
            dados.get("folha_origem"), ("10",),
            f"BUG #118: dados_primeiro incluiu folha_origem: {dados.get('folha_origem')!r}",
        )


class TestIssue118MultiplasOrigens(TestCase):
    """COM 2+ ORIGENS: cada uma preserva seu próprio livro/folha individualmente,
    e o documento ATUAL não recebe livro/folha de nenhuma origem.

    O fluxo que já funciona (e NÃO deve ser tocado):
      lancamento_campos_service → cache 'mapeamento_origens_lancamento_{id}'
      → lancamento_origem_service._sincronizar_origens_estruturadas
      → cria LancamentoOrigem por origem com seu livro/folha
    """

    def setUp(self):
        self.tis = TIs.objects.create(nome="TI #118B", codigo="T118B", etnia="Teste")
        self.pessoa = Pessoas.objects.create(nome="Pessoa #118B", cpf="88877766655")
        self.cri = Cartorios.objects.create(
            nome="CRI #118B", cns="118118B", cidade="Cidade", estado="SP"
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo="transcricao")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel #118B",
            proprietario=self.pessoa,
            matricula="118B",
            tipo_documento_principal="matricula",
            cartorio=self.cri,
        )
        # documento A (matrícula atual) — sem livro/folha
        self.documento_a = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="100",
            data=timezone.now().date(),
            cartorio=self.cri,
            livro="",
            folha="",
        )

    def _criar_lancamento_com_mapeamento_multiplas_origens(self):
        """Cria um lançamento cujo cache de mapeamento tem 2 origens, cada uma
        com seu próprio livro/folha — espelhando o que
        ``lancamento_campos_service`` grava para ``livro_origem[]``/``folha_origem[]``.
        """
        from django.core.cache import cache

        lancamento = Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            cartorio_origem=self.cri,
            origem="M101; T202",
        )

        # Mapeamento por origem, exatamente como lancamento_campos_service faz.
        cache_key = f"mapeamento_origens_lancamento_{lancamento.id}"
        cache.set(cache_key, [
            {
                "origem": "M101",
                "cartorio_id": self.cri.id,
                "cartorio_nome": self.cri.nome,
                "livro": "5",
                "folha": "10",
            },
            {
                "origem": "T202",
                "cartorio_id": self.cri.id,
                "cartorio_nome": self.cri.nome,
                "livro": "12",
                "folha": "20",
            },
        ], timeout=3600)
        return lancamento

    def test_multiplas_origens_cada_uma_preserva_seu_livro_folha(self):
        """CADA LancamentoOrigem tem seu próprio livro/folha (M101→5/10, T202→12/20)."""
        from dominial.services.lancamento_origem_service import LancamentoOrigemService

        lancamento = self._criar_lancamento_com_mapeamento_multiplas_origens()

        # Processar origens (sincroniza origens estruturadas).
        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem, self.imovel
        )

        origens = LancamentoOrigem.objects.filter(
            lancamento=lancamento
        ).order_by("indice_origem")
        self.assertEqual(origens.count(), 2)

        # M101 → livro=5, folha=10
        origem_0 = origens[0]
        self.assertEqual(origem_0.numero_normalizado, "101")
        self.assertEqual(origem_0.livro, "5")
        self.assertEqual(origem_0.folha, "10")

        # T202 → livro=12, folha=20
        origem_1 = origens[1]
        self.assertEqual(origem_1.numero_normalizado, "202")
        self.assertEqual(origem_1.livro, "12")
        self.assertEqual(origem_1.folha, "20")

    def test_multiplas_origens_documento_atual_nao_recebe_livro_folha(self):
        """Com 2+ origens, o documento ATUAL não recebe livro/folha de nenhuma."""
        from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
        from dominial.services.lancamento_origem_service import LancamentoOrigemService
        from dominial.services.regra_petrea_service import RegraPetreaService

        lancamento = self._criar_lancamento_com_mapeamento_multiplas_origens()

        # Simular o pipeline: _aplicar_campos_documento (sem livro_documento) +
        # regra pétrea + processar origens. Em nenhum momento o documento
        # atual deve receber livro/folha das origens (5/10 nem 12/20).
        LancamentoCriacaoService._aplicar_campos_documento(
            lancamento,
            {"livro_documento": "", "folha_documento": "",
             "livro_origem": "5", "folha_origem": "10"},
        )
        RegraPetreaService.aplicar_regra_petrea(lancamento)
        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem, self.imovel
        )

        self.documento_a.refresh_from_db()
        self.assertNotIn(
            self.documento_a.livro, ("5", "12"),
            f"BUG #118: documento atual recebeu livro de uma origem: {self.documento_a.livro!r}",
        )
        self.assertNotIn(
            self.documento_a.folha, ("10", "20"),
            f"BUG #118: documento atual recebeu folha de uma origem: {self.documento_a.folha!r}",
        )

    def test_multiplas_origens_nao_se_cruzam(self):
        """A origem 0 não recebe o livro/folha da origem 1 e vice-versa."""
        from dominial.services.lancamento_origem_service import LancamentoOrigemService

        lancamento = self._criar_lancamento_com_mapeamento_multiplas_origens()

        LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem, self.imovel
        )

        origens = LancamentoOrigem.objects.filter(
            lancamento=lancamento
        ).order_by("indice_origem")

        # M101 NÃO deve ter 12/20 (da T202)
        self.assertNotEqual(origens[0].livro, "12")
        self.assertNotEqual(origens[0].folha, "20")
        # T202 NÃO deve ter 5/10 (da M101)
        self.assertNotEqual(origens[1].livro, "5")
        self.assertNotEqual(origens[1].folha, "10")


class TestIssue118NovoLancamentoViewSegundoLancamento(TestCase):
    """Regressão P1 (review Codex, PR #119): a view ``novo_lancamento`` indexava
    ``dados_primeiro['livro_origem']``/``['folha_origem']`` diretamente, mas esses
    campos foram removidos do dict retornado por
    ``LancamentoHerancaService.obter_dados_primeiro_lancamento``. Isso derrubava
    a tela com ``KeyError`` sempre que o documento já tinha um primeiro
    lançamento (ou seja, ao abrir o formulário do SEGUNDO lançamento)."""

    def setUp(self):
        self.tis = TIs.objects.create(nome="TI #118C", codigo="T118C", etnia="Teste")
        self.pessoa = Pessoas.objects.create(nome="Pessoa #118C", cpf="77766655544")
        self.cri = Cartorios.objects.create(
            nome="CRI #118C", cns="118118C", cidade="Cidade", estado="SP"
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel #118C",
            proprietario=self.pessoa,
            matricula="118C",
            tipo_documento_principal="matricula",
            cartorio=self.cri,
        )
        self.documento_a = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="100",
            data=timezone.now().date(),
            cartorio=self.cri,
            livro="",
            folha="",
        )
        # Primeiro lançamento do documento, com livro_origem/folha_origem
        # preenchidos (dados da ORIGEM, não do documento atual).
        Lancamento.objects.create(
            documento=self.documento_a,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            cartorio_origem=self.cri,
            livro_origem="5",
            folha_origem="10",
        )

        usuario = get_user_model().objects.create_user(
            username="tester118c", password="senha-118c"
        )
        self.client.force_login(usuario)

    def test_get_formulario_segundo_lancamento_nao_gera_keyerror(self):
        """Abrir o formulário do segundo lançamento não deve estourar KeyError."""
        url = reverse(
            "novo_lancamento_documento",
            args=[self.tis.id, self.imovel.id, self.documento_a.id],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_get_formulario_segundo_lancamento_nao_herda_livro_folha_origem(self):
        """O lançamento herdado no contexto não deve trazer livro/folha da origem."""
        url = reverse(
            "novo_lancamento_documento",
            args=[self.tis.id, self.imovel.id, self.documento_a.id],
        )

        response = self.client.get(url)

        lancamento_herdado = response.context["lancamento"]
        self.assertFalse(
            lancamento_herdado.livro_origem,
            f"BUG #118 (P1): view herdou livro_origem: {lancamento_herdado.livro_origem!r}",
        )
        self.assertFalse(
            lancamento_herdado.folha_origem,
            f"BUG #118 (P1): view herdou folha_origem: {lancamento_herdado.folha_origem!r}",
        )
