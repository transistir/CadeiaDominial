"""
T27 (redefinida) — Regressão: a confirmação de duplicata usa a identidade de
cartório ponta a ponta, do fluxo legado de importação (anterior a esta
branch) até a reconstrução da árvore.

Contexto (2026-07-14): uma primeira implementação de T27 (prévia de UI
"criar/importar/reutilizar") foi descartada — o usuário apontou que o fluxo
de detectar duplicata, avisar, confirmar, importar a cadeia e recalcular a
hierarquia já existe no baseline (anterior a esta branch); esta branch deve
apenas corrigir a identidade por cartório nesse fluxo, não inventar uma tela
nova. Consulta ao Codex confirmou o diagnóstico e recomendou este teste de
regressão no lugar da UI: nenhuma mudança de código de produção é esperada
para este teste passar, já que R03/R04/T14/T26 já cobrem o caminho.

Cenário: dois documentos homônimos M123 em cartórios diferentes (A e B).
Confirma-se a duplicata apontando para o cartório A. O teste verifica que:
- o `LancamentoOrigem` estruturado grava o cartório A (não B, não nenhum);
- a árvore reconstruída liga o documento ativo ao documento de M123 do
  cartório A por ID;
- o homônimo do cartório B não aparece na árvore;
- o nível do nó importado é o esperado.

Nenhuma migração é aplicada; os testes rodam no banco de testes.
"""

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.contrib.messages.storage.fallback import FallbackStorage

from dominial.models import LancamentoTipo
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.services.lancamento_duplicata_service import LancamentoDuplicataService
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


def _request_com_messages(factory, path, data):
    request = factory.post(path, data)
    setattr(request, "session", {})
    setattr(request, "_messages", FallbackStorage(request))
    return request


class T27RegressaoCartorioDuplicataTest(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(username="t27reg", password="t27pass")
        cls.tipo_registro = LancamentoTipo.objects.create(
            tipo='registro', requer_transmissao=False,
        )

    def test_confirmacao_duplicata_usa_cartorio_ponta_a_ponta(self):
        # Homônimos M123 em cartórios diferentes.
        imovel_origem_a = self.criar_imovel("123", self.cartorio_a, nome="Origem A")
        imovel_origem_b = self.criar_imovel("123", self.cartorio_b, nome="Origem B")
        doc_origem_a = self.criar_documento(imovel_origem_a, self.tipo_matricula, "M123", self.cartorio_a)
        doc_origem_b = self.criar_documento(imovel_origem_b, self.tipo_matricula, "M123", self.cartorio_b)

        imovel_destino = self.criar_imovel("999", self.cartorio_a, nome="Destino")
        documento_ativo = self.criar_documento(imovel_destino, self.tipo_matricula, "M999", self.cartorio_a)

        post_data = {
            'tipo_lancamento': str(self.tipo_registro.id),
            'numero_lancamento_simples': '1',
            'data': '2026-07-14',
            'origem_completa[]': ['M123'],
            'cartorio_origem[]': [str(self.cartorio_a.id)],
            'cartorio_origem_nome[]': [self.cartorio_a.nome],
            'documento_origem_id': str(doc_origem_a.id),
            'documentos_importaveis[]': [str(doc_origem_a.id)],
        }
        request = _request_com_messages(RequestFactory(), '/fake-url/', post_data)
        request.user = self.user

        # Passo 1: confirmar a importação (mesmo caminho de
        # `duplicata_views.importar_duplicata` antes de criar o lançamento).
        resultado_importacao = LancamentoDuplicataService.processar_importacao_duplicata(
            request, documento_ativo, self.user
        )
        self.assertTrue(resultado_importacao['sucesso'], resultado_importacao.get('mensagem'))

        # Passo 2: criar o lançamento original (mesmo caminho da view,
        # `apos_importacao=true` pula a nova verificação de duplicata).
        request.POST = request.POST.copy()
        request.POST['apos_importacao'] = 'true'
        lancamento, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request=request,
            tis=self.ti,
            imovel=imovel_destino,
            documento_ativo=documento_ativo,
        )
        self.assertIsNotNone(lancamento, mensagem)

        # Passo 3: o LancamentoOrigem estruturado grava o cartório A, não B.
        origem_estruturada = lancamento.origens_estruturadas.get()
        self.assertEqual(origem_estruturada.cartorio_id, self.cartorio_a.id)
        self.assertEqual(origem_estruturada.numero_normalizado, "123")

        # Passo 4: a árvore reconstruída liga ao documento certo por ID e
        # não confunde com o homônimo do cartório B.
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel_destino)
        conexoes = {(c['from'], c['to']) for c in arvore['conexoes']}
        self.assertIn((documento_ativo.pk, doc_origem_a.pk), conexoes)
        self.assertNotIn((documento_ativo.pk, doc_origem_b.pk), conexoes)

        nos = {no['id']: no for no in arvore['documentos']}
        self.assertIn(doc_origem_a.pk, nos)
        self.assertNotIn(doc_origem_b.pk, nos)
        self.assertEqual(nos[doc_origem_a.pk]['nivel'], 1)
