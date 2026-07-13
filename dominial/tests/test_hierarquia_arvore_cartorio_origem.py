from django.test import TestCase
from django.utils import timezone
from dominial.models import (
    TIs, Pessoas, Imovel, Cartorios,
    DocumentoTipo, LancamentoTipo,
    Documento, Lancamento
)
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService


class HierarquiaArvoreCartorioOrigemTest(TestCase):
    """
    Regressão: um lançamento pode declarar `cartorio_origem` diferente do
    cartório do documento filho (início de matrícula em outro cartório).
    A busca do documento pai deve respeitar esse cartório de origem, e não
    apenas o cartório do documento atual.
    """

    def setUp(self):
        self.tis = TIs.objects.create(nome="TI Teste", codigo="TEST001", etnia="Teste")

        self.cartorio_a = Cartorios.objects.create(
            nome="Cartório A", cns="111111", cidade="Cidade A", estado="TS"
        )
        self.cartorio_b = Cartorios.objects.create(
            nome="Cartório B", cns="222222", cidade="Cidade B", estado="TS"
        )

        self.pessoa1 = Pessoas.objects.create(nome="Pessoa 1", cpf="12345678901")
        self.pessoa2 = Pessoas.objects.create(nome="Pessoa 2", cpf="98765432109")

        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel Teste",
            proprietario=self.pessoa1,
            matricula="M100",
            cartorio=self.cartorio_a,
        )

        self.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        self.tipo_registro = LancamentoTipo.objects.create(tipo='registro')

        # Documento principal do imóvel, registrado no Cartório A
        self.doc_principal = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="M100",
            data=timezone.now().date(),
            cartorio=self.cartorio_a,
            livro="1",
            folha="1",
        )

        # Documento de origem (pai) registrado no Cartório B
        self.doc_pai_cartorio_b = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="M50",
            data=timezone.now().date(),
            cartorio=self.cartorio_b,
            livro="1",
            folha="1",
        )

        # Lançamento do documento principal referencia M50, com
        # cartorio_origem explicitamente apontando para o Cartório B.
        self.lancamento = Lancamento.objects.create(
            documento=self.doc_principal,
            tipo=self.tipo_registro,
            data=timezone.now().date(),
            transmitente=self.pessoa1,
            adquirente=self.pessoa2,
            valor_transacao=100000.00,
            origem="M50",
            cartorio_origem=self.cartorio_b,
        )

    def test_busca_documento_pai_respeita_cartorio_origem_do_lancamento(self):
        documentos_pais = HierarquiaArvoreService._buscar_documentos_pais(
            self.doc_principal, self.imovel, criar_documentos_automaticos=False
        )

        self.assertIn(self.doc_pai_cartorio_b, documentos_pais)

    def test_arvore_completa_inclui_origem_de_outro_cartorio(self):
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(
            self.imovel, criar_documentos_automaticos=False
        )

        numeros_na_arvore = {no['numero'] for no in arvore['documentos']}
        self.assertIn("M50", numeros_na_arvore)
