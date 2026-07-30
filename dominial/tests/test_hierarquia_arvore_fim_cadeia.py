from django.test import TestCase
from django.utils import timezone

from dominial.models import (
    TIs, Pessoas, Imovel, Cartorios,
    DocumentoTipo, LancamentoTipo,
    Documento, Lancamento, OrigemFimCadeia,
)
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService


class HierarquiaArvoreFimCadeiaTest(TestCase):
    """Testa injeção de nós de fim de cadeia na árvore D3 (issue #85)."""

    def _criar_infra_base(self, matricula="M100"):
        """Cria TIs, cartório, pessoa, imóvel, tipo de documento e tipo de lançamento."""
        self.tis = TIs.objects.create(
            nome="TI Teste", codigo="TEST001", etnia="Teste"
        )
        self.cartorio = Cartorios.objects.create(
            nome="Cartório Teste", cns="111111", cidade="Cidade", estado="TS"
        )
        self.proprietario = Pessoas.objects.create(
            nome="Proprietário", cpf="12345678901"
        )
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel Teste",
            proprietario=self.proprietario,
            matricula=matricula,
            cartorio=self.cartorio,
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        self.tipo_registro = LancamentoTipo.objects.create(tipo='registro')

    def _criar_documento_com_lancamento(self, matricula="M100"):
        """Cria documento matrícula + lançamento de registro."""
        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero=matricula,
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro="1",
            folha="1",
        )
        self.lancamento = Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_registro,
            data=timezone.now().date(),
            valor_transacao=100000.00,
            origem="",
        )

    def setUp(self):
        self._criar_infra_base()
        self._criar_documento_com_lancamento()
        # OrigemFimCadeia padrão: destacamento público + origem lídima
        OrigemFimCadeia.objects.create(
            lancamento=self.lancamento,
            indice_origem=0,
            fim_cadeia=True,
            tipo_fim_cadeia='destacamento_publico',
            classificacao_fim_cadeia='origem_lidima',
        )

    def _extrair_fim_cadeia(self, arvore):
        return [d for d in arvore['documentos'] if d.get('is_fim_cadeia')]

    def test_arvore_inclui_no_fim_cadeia(self):
        """Árvore deve incluir nó com is_fim_cadeia=True quando há origem de fim de cadeia."""
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(self.imovel)
        nos_fim_cadeia = self._extrair_fim_cadeia(arvore)
        self.assertTrue(len(nos_fim_cadeia) > 0)

    def test_no_fim_cadeia_tem_classificacao(self):
        """Nó de fim de cadeia deve ter classificacao_fim_cadeia definida."""
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(self.imovel)
        no_fc = self._extrair_fim_cadeia(arvore)[0]
        self.assertIsNotNone(no_fc['classificacao_fim_cadeia'])
        self.assertIn(
            no_fc['classificacao_fim_cadeia'],
            ['origem_lidima', 'sem_origem', 'inconclusa'],
        )

    def test_no_fim_cadeia_id_eh_string(self):
        """O ID do nó de fim de cadeia deve ser string para não colidir com IDs de documentos."""
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(self.imovel)
        no_fc = self._extrair_fim_cadeia(arvore)[0]
        self.assertIsInstance(no_fc['id'], str)
        self.assertEqual(no_fc['id'], f"fim_cadeia_{self.documento.id}")

    def test_arvore_sem_fim_cadeia(self):
        """Documento sem origem de fim de cadeia não deve gerar nó is_fim_cadeia."""
        # Criar um segundo imóvel e documento sem fim de cadeia
        tis2 = TIs.objects.create(
            nome="TI Teste 2", codigo="TEST002", etnia="Teste"
        )
        cartorio2 = Cartorios.objects.create(
            nome="Cartório 2", cns="222222", cidade="Cidade 2", estado="TS"
        )
        imovel_sem_fc = Imovel.objects.create(
            terra_indigena_id=tis2,
            nome="Imóvel Sem FC",
            proprietario=self.proprietario,
            matricula="M200",
            cartorio=cartorio2,
        )
        doc_sem_fc = Documento.objects.create(
            imovel=imovel_sem_fc,
            tipo=self.tipo_matricula,
            numero="M200",
            data=timezone.now().date(),
            cartorio=cartorio2,
            livro="1",
            folha="1",
        )
        Lancamento.objects.create(
            documento=doc_sem_fc,
            tipo=self.tipo_registro,
            data=timezone.now().date(),
            valor_transacao=50000.00,
            origem="",
        )
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel_sem_fc)
        nos_fc = self._extrair_fim_cadeia(arvore)
        self.assertEqual(len(nos_fc), 0)

    def test_conexao_fim_cadeia(self):
        """Deve haver conexão tipo 'fim_cadeia' entre documento e nó de fim de cadeia."""
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(self.imovel)
        conexoes_fc = [c for c in arvore['conexoes'] if c.get('tipo') == 'fim_cadeia']
        self.assertTrue(len(conexoes_fc) > 0)
        conexao = conexoes_fc[0]
        self.assertEqual(conexao['from'], self.documento.id)
        self.assertEqual(conexao['to'], f"fim_cadeia_{self.documento.id}")

    def test_classificacao_fallback_none(self):
        """classificacao_fim_cadeia=None deve cair para 'sem_origem'."""
        # Sobrescrever a origem com classificacao=None
        OrigemFimCadeia.objects.filter(lancamento=self.lancamento).update(
            classificacao_fim_cadeia=None
        )
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(self.imovel)
        no_fc = self._extrair_fim_cadeia(arvore)[0]
        self.assertEqual(no_fc['classificacao_fim_cadeia'], 'sem_origem')

    def test_tipo_destacamento_com_sigla(self):
        """Tipo destacamento_publico com sigla na origem gera título apropriado."""
        # Atualizar lançamento com origem contendo sigla de patrimônio público
        Lancamento.objects.filter(id=self.lancamento.id).update(
            origem="FIM_CADEIA:M:1:Cartório:123:INCRA"
        )
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(self.imovel)
        no_fc = self._extrair_fim_cadeia(arvore)[0]
        self.assertEqual(no_fc['tipo_fim_cadeia'], 'destacamento_publico')
        self.assertEqual(no_fc['sigla_patrimonio_publico'], 'INCRA')
