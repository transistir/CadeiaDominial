"""O formulário manual continua criando cartório de origem por texto livre.

O bloqueio #388 vive só na revisão OCR (``bloqueios_do_post``). No caminho
manual, nome de cartório sem id existente segue a regra antiga: busca por
``iexact`` e, se não achar, cria com CNS gerado.
"""

from django.test import RequestFactory

from dominial.models import Cartorios, Lancamento, LancamentoTipo
from dominial.services.lancamento_service import LancamentoService
from dominial.tests.segregacao_fixtures import usuario_com_tis
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


class CartorioOrigemManualTextoLivreTest(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tipo_inicio, _ = LancamentoTipo.objects.get_or_create(
            tipo='inicio_matricula',
        )

    def test_nome_novo_no_formulario_manual_cria_cartorio(self):
        nome_livre = 'CRI Texto Livre Manual 388'
        self.assertFalse(Cartorios.objects.filter(nome__iexact=nome_livre).exists())
        imovel = self.criar_imovel('889', self.cartorio_a, nome='Imóvel 889')
        documento = self.criar_documento(
            imovel, self.tipo_matricula, 'M889', self.cartorio_a,
        )
        # Sem ``cartorio_origem[]``: é o nome digitado à mão que identifica o
        # cartório. Com o id presente o service exigiria um cadastro existente.
        post = {
            'tipo_lancamento': str(self.tipo_inicio.pk),
            'sigla_matricula': 'M889',
            'numero_lancamento_simples': '1',
            'numero_lancamento': '',
            'data': '2026-01-02',
            'observacoes': '',
            'origem_completa[]': ['M500'],
            'cartorio_origem_nome[]': [nome_livre],
            'livro_origem[]': [''],
            'folha_origem[]': [''],
            'transmitente_nome[]': [],
            'transmitente[]': [],
            'adquirente_nome[]': [],
            'adquirente[]': [],
        }
        request = RequestFactory().post('/x/', post)
        request.user = usuario_com_tis('u-manual-livre', self.ti)

        lancamento, mensagem = LancamentoService.criar_lancamento_completo(
            request, self.ti, imovel, documento,
        )

        self.assertIsNotNone(lancamento, mensagem)
        self.assertEqual(Lancamento.objects.count(), 1)
        cartorio = Cartorios.objects.get(nome__iexact=nome_livre)
        self.assertTrue(cartorio.cns.startswith('CNS'))
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.cartorio_origem, cartorio)
