"""Fim de cadeia em linha de origem sem documento anterior (#407).

O formulário envia ``origem_completa[]`` vazio (input escondido) quando a linha
de origem não tem identidade — o caso "sem documento anterior" / "sem origem".
O POST da M237 gravou o lançamento 13108 como fim de cadeia no formulário, mas
``OrigemFimCadeia`` ficou com 0 linhas: o writer só criava o registro quando
``origem.strip()`` era não vazio e descartava o índice marcado em
``fim_cadeia[]`` em silêncio.

Regra coberta aqui:
- linha vazia + ``fim_cadeia[]`` marcado grava ``OrigemFimCadeia``;
- a linha vazia NÃO vira texto em ``lancamento.origem`` nem origem
  estruturada/cartório (sem origem fantasma);
- tipos/classificação/especificação vêm da POSIÇÃO DA LINHA nos arrays densos
  do formulário (não da posição entre os checkboxes marcados);
- índice marcado sem linha de origem correspondente não cria registro.
"""

from django.test import RequestFactory, TestCase
from django.utils import timezone

from ..models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
    OrigemFimCadeia,
    Pessoas,
    TIs,
)
from ..services.lancamento_campos_service import LancamentoCamposService


class FimCadeiaOrigemVaziaBase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        tis = TIs.objects.create(nome='TI Teste', codigo='T407', etnia='Teste')
        self.cartorio = Cartorios.objects.create(
            nome='Cartório Teste', cns='407407', cidade='Cidade', estado='TS'
        )
        proprietario = Pessoas.objects.create(
            nome='Proprietário', cpf='40740740740'
        )
        imovel = Imovel.objects.create(
            terra_indigena_id=tis,
            nome='Imóvel Teste',
            proprietario=proprietario,
            matricula='M407',
            cartorio=self.cartorio,
        )
        documento = Documento.objects.create(
            imovel=imovel,
            tipo=DocumentoTipo.objects.create(tipo='matricula'),
            numero='M407',
            data=timezone.now().date(),
            cartorio=self.cartorio,
            livro='1',
            folha='1',
        )
        self.lancamento = Lancamento.objects.create(
            documento=documento,
            tipo=LancamentoTipo.objects.create(tipo='inicio_matricula'),
            data=timezone.now().date(),
            origem='',
        )

    def _postar(self, dados):
        request = self.factory.post('/', dados)
        LancamentoCamposService._processar_campos_inicio_matricula(
            request, self.lancamento
        )

    def _postar_linha_vazia_com_fim_cadeia(self):
        # Exatamente o que o form envia numa única linha sem documento
        # anterior, com o toggle de fim de cadeia marcado.
        self._postar({
            'origem_completa[]': [''],
            'cartorio_origem[]': [''],
            'cartorio_origem_nome[]': [''],
            'livro_origem[]': [''],
            'folha_origem[]': [''],
            'fim_cadeia[]': ['0'],
            'tipo_fim_cadeia[]': ['sem_origem'],
            'classificacao_fim_cadeia[]': ['sem_origem'],
            'especificacao_fim_cadeia[]': [''],
            'info_adicional_fim_cadeia[]': [''],
        })


class FimCadeiaOrigemVaziaPersistenciaTest(FimCadeiaOrigemVaziaBase):
    def test_linha_vazia_com_fim_cadeia_marcado_grava_registro(self):
        # RED antes da correção: o loop pulava a linha vazia e nada era
        # gravado, deixando o lançamento sem tipo/classificação de fim de
        # cadeia.
        self._postar_linha_vazia_com_fim_cadeia()

        registros = OrigemFimCadeia.objects.filter(
            lancamento=self.lancamento
        )
        self.assertEqual(registros.count(), 1)
        registro = registros.get()
        self.assertEqual(registro.indice_origem, 0)
        self.assertTrue(registro.fim_cadeia)
        self.assertEqual(registro.tipo_fim_cadeia, 'sem_origem')
        self.assertEqual(registro.classificacao_fim_cadeia, 'sem_origem')

    def test_linha_vazia_nao_grava_origem_fantasma(self):
        self._postar_linha_vazia_com_fim_cadeia()

        self.assertEqual(self.lancamento.origem, '')
        self.assertEqual(
            LancamentoOrigem.objects.filter(lancamento=self.lancamento).count(),
            0,
        )
        self.assertEqual(Cartorios.objects.count(), 1)

    def test_linha_vazia_sem_fim_cadeia_nao_grava_registro(self):
        self._postar({
            'origem_completa[]': [''],
            'cartorio_origem[]': [''],
            'cartorio_origem_nome[]': [''],
            'livro_origem[]': [''],
            'folha_origem[]': [''],
        })

        self.assertEqual(
            OrigemFimCadeia.objects.filter(lancamento=self.lancamento).count(),
            0,
        )
        self.assertEqual(self.lancamento.origem, '')

    def test_indice_marcado_sem_linha_de_origem_nao_cria_fantasma(self):
        # POST sem nenhuma linha de origem: não há posição para ancorar o
        # registro; nada é criado.
        self._postar({
            'fim_cadeia[]': ['0'],
            'tipo_fim_cadeia[]': ['sem_origem'],
            'classificacao_fim_cadeia[]': ['sem_origem'],
        })

        self.assertEqual(
            OrigemFimCadeia.objects.filter(lancamento=self.lancamento).count(),
            0,
        )


class FimCadeiaTipoPorPosicaoDaLinhaTest(FimCadeiaOrigemVaziaBase):
    def test_tipo_vem_da_posicao_da_linha_nos_arrays_densos(self):
        # Duas linhas; só a segunda (índice 1) é fim de cadeia. O formulário
        # envia os arrays de tipo/classificação/especificação densos — uma
        # posição por linha. O writer antigo indexava pela posição entre os
        # checkboxes marcados (j=0) e gravava tipo/classificação vazios.
        self._postar({
            'origem_completa[]': ['', 'M111'],
            'cartorio_origem[]': ['', ''],
            'cartorio_origem_nome[]': ['', ''],
            'livro_origem[]': ['', ''],
            'folha_origem[]': ['', ''],
            'fim_cadeia[]': ['1'],
            'tipo_fim_cadeia[]': ['', 'outra'],
            'classificacao_fim_cadeia[]': ['', 'inconclusa'],
            'especificacao_fim_cadeia[]': ['', 'Detalhe da segunda linha'],
            'info_adicional_fim_cadeia[]': ['', ''],
        })

        registro = OrigemFimCadeia.objects.get(lancamento=self.lancamento)
        self.assertEqual(registro.indice_origem, 1)
        self.assertEqual(registro.tipo_fim_cadeia, 'outra')
        self.assertEqual(registro.classificacao_fim_cadeia, 'inconclusa')
        self.assertEqual(
            registro.especificacao_fim_cadeia, 'Detalhe da segunda linha'
        )
