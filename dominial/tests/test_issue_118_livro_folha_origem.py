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
from django.test import RequestFactory, TestCase
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
