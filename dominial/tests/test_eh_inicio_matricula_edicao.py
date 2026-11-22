"""``eh_inicio_matricula`` acompanha o tipo também na edição (#388).

O campo é derivado de ``tipo_lancamento``. A criação já o grava; a edição
precisa atualizá-lo, senão um ato que muda de registro para início (ou volta)
fica com a flag do tipo antigo.
"""

from datetime import date

from django.test import RequestFactory

from dominial.models import Lancamento, LancamentoTipo
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.tests.segregacao_fixtures import usuario_com_tis
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


class EhInicioMatriculaNaEdicaoTest(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tipo_registro, _ = LancamentoTipo.objects.get_or_create(tipo='registro')
        cls.tipo_inicio, _ = LancamentoTipo.objects.get_or_create(
            tipo='inicio_matricula',
        )

    def _lancamento(self):
        imovel = self.criar_imovel('888', self.cartorio_a, nome='Imóvel 888')
        documento = self.criar_documento(
            imovel, self.tipo_matricula, 'M888', self.cartorio_a,
        )
        return Lancamento.objects.create(
            documento=documento,
            tipo=self.tipo_registro,
            numero_lancamento='888',
            data=date(2020, 2, 15),
            eh_inicio_matricula=False,
        )

    def _editar(self, lancamento, tipo):
        # POST mínimo para ``atualizar_lancamento_completo``: tipo e o número
        # simples que o service exige para registro. Sem origens nem partes, o
        # service só reprocessa os campos básicos — o que basta para a flag.
        post = {
            'tipo_lancamento': str(tipo.pk),
            'numero_lancamento_simples': '888',
            'numero_lancamento': lancamento.numero_lancamento,
            'data': '2020-02-15',
            'observacoes': '',
        }
        request = RequestFactory().post('/', post)
        request.user = usuario_com_tis(f'ed-{tipo.tipo}', self.ti)
        sucesso, mensagem = LancamentoCriacaoService.atualizar_lancamento_completo(
            request, lancamento, lancamento.documento.imovel,
        )
        self.assertTrue(sucesso, mensagem)
        lancamento.refresh_from_db()
        return lancamento

    def test_flag_acompanha_o_tipo_na_edicao(self):
        lancamento = self._lancamento()
        self.assertFalse(lancamento.eh_inicio_matricula)

        self._editar(lancamento, self.tipo_inicio)
        self.assertTrue(lancamento.eh_inicio_matricula)

        self._editar(lancamento, self.tipo_registro)
        self.assertFalse(lancamento.eh_inicio_matricula)
