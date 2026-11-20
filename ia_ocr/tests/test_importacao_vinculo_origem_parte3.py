"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.

Parte 3 de 3 da classe ``VinculoDocumentoOrigemTest`` — 816 linhas
não cabem em um arquivo de 400. Classe SIMPLES (sem ``TestCase``):
o discovery do Django não a coleta; quem coleta é a fachada em
``test_importacao_vinculo_origem.py``. Corpos verbatim.
"""

from datetime import date
from django.test import (
    RequestFactory, TestCase, TransactionTestCase, skipUnlessDBFeature,
)
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, TIs, UserTI,
)
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo


class VinculoDocumentoOrigemParte3:
    """Continuação verbatim da parte 2 (ver lá)."""



    def test_numero_sem_cartorio_continua_valor_obrigatorio(self):
        payload = self._payload_origem()
        del payload['acts'][0]['origem']['cartorio']
        extracao = self._extracao(payload)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (linha,) = contexto.exception.linhas
        (erro,) = linha['erros']
        self.assertEqual(erro['chave'], '/acts/0/origem/cartorio')
        self.assertEqual(erro['codigo'], 'valor_obrigatorio')
        self.assertEqual(Lancamento.objects.count(), 0)

    # --- #324 (PR #343, P2): a edição MANUAL não deixa a FK obsoleta ---------
    # O caminho manual NUNCA cria o vínculo ``documento_origem`` (só a
    # importação grava); ele só LIMPA o que a edição da origem tornou falso:
    # sem isso a tela mostrava o "Documento de Origem" errado e o PROTECT
    # impedia apagar um documento que já não tem relação com o lançamento.

    NUMERO_MATRICULA = 'M366'


    def _importar_com_origem_matricula_m366(self):
        """Importa um início de matrícula cuja origem é a matrícula M366."""
        DocumentoTipo.objects.get_or_create(tipo='matricula')
        payload = self._payload_inicio()
        origem = payload['acts'][0]['origem']
        origem['tipo_documento'] = self._campo('matricula', 'MATRÍCULA Nº 42.718')
        origem['numero'] = self._campo(self.NUMERO_MATRICULA, '42.718')
        extracao = self._extracao(payload)

        self.assertTrue(self._importar(extracao)['ok'])

        lancamento = Lancamento.objects.get()
        (documento_m366,) = self._outros_documentos()
        self.assertEqual(documento_m366.numero, self.NUMERO_MATRICULA)
        self.assertEqual(documento_m366.tipo.tipo, 'matricula')
        # Premissa: a IA preencheu a FK com o documento da origem M366.
        self.assertEqual(lancamento.documento_origem, documento_m366)
        return lancamento, documento_m366


    def _editar_pelo_formulario_manual(
        self, lancamento, origem, *, cartorio=None, livro='', folha='',
    ):
        """POST do formulário manual de edição, trocando só a origem.

        Mesmo caminho da view ``editar_lancamento``
        (``LancamentoService.atualizar_lancamento_completo``): o resto do
        formulário segue como o lançamento está.
        """
        cartorio = cartorio or self.cartorio_origem
        post = {
            'tipo_lancamento': str(lancamento.tipo_id),
            'numero_lancamento': lancamento.numero_lancamento or 'R1 M42',
            'data': lancamento.data.isoformat(),
            'observacoes': '',
            'origem_completa[]': [origem],
            'cartorio_origem[]': [str(cartorio.pk) if origem else ''],
            'cartorio_origem_nome[]': [cartorio.nome if origem else ''],
            'livro_origem[]': [livro],
            'folha_origem[]': [folha],
        }
        if lancamento.tipo.tipo in ('registro', 'averbacao'):
            # Exigido pelo formulário nesses tipos (número simples).
            post['numero_lancamento_simples'] = '1'
        request = RequestFactory().post('/lancamento/editar/', post)
        request.user = self.usuario
        sucesso, mensagem = LancamentoCriacaoService.atualizar_lancamento_completo(
            request, lancamento, self.imovel,
        )
        self.assertTrue(sucesso, mensagem)


    def test_editar_o_numero_da_origem_pelo_manual_limpa_a_fk(self):
        lancamento, documento_m366 = self._importar_com_origem_matricula_m366()

        self._editar_pelo_formulario_manual(lancamento, 'M999')

        lancamento = Lancamento.objects.get(pk=lancamento.pk)
        # A origem foi reprocessada para M999, mas o manual NÃO vincula nada.
        origem = LancamentoOrigem.objects.get(lancamento=lancamento)
        self.assertEqual(origem.numero, 'M999')
        self.assertIsNone(lancamento.documento_origem_id)
        # O documento antigo não tem mais relação com o lançamento: nada o
        # protege de uma exclusão legítima (a FK PROTECT só olha esta relação).
        self.assertFalse(documento_m366.lancamentos_origem.exists())
        self.assertTrue(Documento.objects.filter(pk=documento_m366.pk).exists())


    def test_editar_so_o_livro_da_origem_pelo_manual_mantem_a_fk(self):
        lancamento, documento_m366 = self._importar_com_origem_matricula_m366()

        self._editar_pelo_formulario_manual(
            lancamento, self.NUMERO_MATRICULA, livro='L-9', folha='F-9',
        )

        lancamento = Lancamento.objects.get(pk=lancamento.pk)
        origem = LancamentoOrigem.objects.get(lancamento=lancamento)
        self.assertEqual((origem.livro, origem.folha), ('L-9', 'F-9'))
        self.assertEqual(origem.numero, self.NUMERO_MATRICULA)
        self.assertEqual(lancamento.documento_origem_id, documento_m366.pk)


    def test_apagar_a_origem_pelo_manual_limpa_a_fk(self):
        lancamento, documento_m366 = self._importar_com_origem_matricula_m366()

        self._editar_pelo_formulario_manual(lancamento, '')

        lancamento = Lancamento.objects.get(pk=lancamento.pk)
        self.assertFalse(
            LancamentoOrigem.objects.filter(lancamento=lancamento).exists()
        )
        self.assertIsNone(lancamento.documento_origem_id)
        self.assertFalse(documento_m366.lancamentos_origem.exists())


    def test_mesmo_numero_em_outro_cartorio_pelo_manual_limpa_a_fk(self):
        """A identidade é tipo + número + CARTÓRIO: só o número não basta."""
        lancamento, documento_m366 = self._importar_com_origem_matricula_m366()
        outro_cartorio = Cartorios.objects.create(
            nome='CRI Outro 324', cns='CNS-324B', cidade='Dourados', estado='MS',
        )

        self._editar_pelo_formulario_manual(
            lancamento, self.NUMERO_MATRICULA, cartorio=outro_cartorio,
        )

        lancamento = Lancamento.objects.get(pk=lancamento.pk)
        origem = LancamentoOrigem.objects.get(lancamento=lancamento)
        self.assertEqual(origem.cartorio, outro_cartorio)
        self.assertIsNone(lancamento.documento_origem_id)
        self.assertFalse(documento_m366.lancamentos_origem.exists())


    def test_edicao_manual_sem_fk_nao_cria_vinculo(self):
        """O manual só limpa: origem existente no escopo não vira vínculo."""
        irmao = self._imovel_em(self.imovel.terra_indigena_id, 'Irmão M366')
        tipo_matricula, _ = DocumentoTipo.objects.get_or_create(tipo='matricula')
        existente = Documento.objects.create(
            imovel=irmao, tipo=tipo_matricula, numero=self.NUMERO_MATRICULA,
            data=date(1990, 1, 1), cartorio=self.cartorio_origem,
            livro='1', folha='1',
        )
        lancamento = Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento='R1 M42', data=date(2020, 2, 15),
        )
        self.assertIsNone(lancamento.documento_origem_id)

        self._editar_pelo_formulario_manual(lancamento, self.NUMERO_MATRICULA)

        lancamento = Lancamento.objects.get(pk=lancamento.pk)
        self.assertEqual(
            LancamentoOrigem.objects.get(lancamento=lancamento).numero,
            self.NUMERO_MATRICULA,
        )
        self.assertIsNone(lancamento.documento_origem_id)
        self.assertFalse(existente.lancamentos_origem.exists())
