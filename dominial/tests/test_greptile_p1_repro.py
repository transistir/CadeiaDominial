"""Teste de reprodução do P1 do Greptile no #184.

O bug: o service original agrupava `OrigemFimCadeia` por
`lancamento__documento__imovel`, então:
- fim de cadeia em documento compartilhado era creditado ao imóvel
  dono do documento, não ao imóvel cuja árvore o alcançava;
- imóvel dono de um documento desconectado herdava a classificação
  desse fim isolado.

Cenário realista (issue #174 — M100 aponta M200 como origem via
lançamento estruturado; M200 é de outro imóvel da mesma TI; M999 é
doc desconectado do M100 com fim `sem_origem`).
"""
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model

from dominial.models import (
    TIs, Imovel, DocumentoTipo, Cartorios, Documento, LancamentoTipo,
    Lancamento, LancamentoOrigem, OrigemFimCadeia, Pessoas,
)
from dominial.services.status_cadeia_service import StatusCadeiaService


def _criar_doc(numero, imovel, cart, tipo_m):
    return Documento.objects.create(
        tipo=tipo_m, numero=numero, cartorio=cart, imovel=imovel,
        data=date(2020, 1, 1), livro='1', folha='1',
    )


def _criar_lancamento(doc, tipo_reg, origem_numero=None, origem_doc=None):
    """Cria Lancamento + (opcional) LancamentoOrigem estruturada."""
    l = Lancamento.objects.create(documento=doc, tipo=tipo_reg, data=date(2020, 1, 1))
    if origem_numero and origem_doc is not None:
        LancamentoOrigem.objects.create(
            lancamento=l,
            indice_origem=0,
            tipo_documento='matricula',
            numero=origem_numero,
            cartorio=doc.cartorio,
        )
    return l


class GreptileP1ReproductionTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('u', 'u@x.com', 'pw')
        self.pessoa = Pessoas.objects.create(nome='Proprietário')

        self.ti = TIs.objects.create(nome='TI X')
        self.cart = Cartorios.objects.create(nome='CRI 1', cidade='C')
        self.tipo_m = DocumentoTipo.objects.get_or_create(tipo='matricula')[0]
        self.tipo_reg = LancamentoTipo.objects.get_or_create(tipo='registro')[0]

        self.m100 = Imovel.objects.create(
            nome='Imovel 100', matricula='100',
            tipo_documento_principal='M', cartorio=self.cart,
            terra_indigena_id=self.ti, proprietario=self.pessoa,
        )
        self.m300 = Imovel.objects.create(
            nome='Imovel 300', matricula='300',
            tipo_documento_principal='M', cartorio=self.cart,
            terra_indigena_id=self.ti, proprietario=self.pessoa,
        )

        # M200 é do m300 mas é compartilhado: o m100 aponta M200 como origem
        # estruturada via LancamentoOrigem.
        self.m200 = _criar_doc('200', self.m300, self.cart, self.tipo_m)
        # M999 é do m100, mas o m100 NÃO aponta M999 em nenhum lançamento
        # (desconectado).
        self.m999 = _criar_doc('999', self.m100, self.cart, self.tipo_m)
        # M100 (doc principal do m100) — origem estruturada aponta M200.
        self.m100d = _criar_doc('100', self.m100, self.cart, self.tipo_m)
        _criar_lancamento(
            self.m100d, self.tipo_reg, origem_numero='200', origem_doc=self.m200,
        )

        # Fim de cadeia em M200: origem_lidima (alcançável pela árvore do m100)
        l_m200 = _criar_lancamento(self.m200, self.tipo_reg)
        OrigemFimCadeia.objects.create(
            lancamento=l_m200, indice_origem=0, fim_cadeia=True,
            tipo_fim_cadeia='destacamento_publico',
            classificacao_fim_cadeia='origem_lidima',
        )

        # Fim de cadeia em M999: sem_origem (NÃO alcançável pela árvore do m100)
        l_m999 = _criar_lancamento(self.m999, self.tipo_reg)
        OrigemFimCadeia.objects.create(
            lancamento=l_m999, indice_origem=0, fim_cadeia=True,
            tipo_fim_cadeia='destacamento_publico',
            classificacao_fim_cadeia='sem_origem',
        )

    def test_m100_recebe_status_alcancavel_nao_desconectado(self):
        result = StatusCadeiaService.status_por_imovel(self.ti.id)
        # Árvore do m100 alcança M200 (origem_lidima) — badge deve refletir isso.
        # O status do imóvel M100 deve ser 'origem_lidima' (alcançável via M200),
        # NÃO 'sem_origem' (que está em M999, doc desconectado).
        self.assertEqual(
            result.get(self.m100.id), 'origem_lidima',
            f'P1 Greptile: árvore do M100 alcança M200 (origem_lidima) '
            f'mas o service retorna {result.get(self.m100.id)} — '
            f'deveria ser origem_lidima',
        )
        # M300 é dono direto do M200, então origem_lidima também
        self.assertEqual(result.get(self.m300.id), 'origem_lidima')

        # Sanidade: nenhum imóvel da TI deve receber 'sem_origem'
        # (a única classificação 'sem_origem' está em M999, doc que o M100
        # NÃO alcança pela sua árvore).
        for imovel_id, cls in result.items():
            self.assertNotEqual(
                cls, 'sem_origem',
                f'Imóvel {imovel_id} recebeu sem_origem mas nenhum fim de '
                f'cadeia alcançável é sem_origem',
            )
