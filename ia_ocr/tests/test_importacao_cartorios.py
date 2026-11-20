"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.
"""

from unittest.mock import patch
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, TIs, UserTI,
)
from ia_ocr import importacao as modulo_importacao
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA, OcrJob, PaginaOcr
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao, payload_com_closure,
    payload_registro,
)
from .test_importacao_base import ImportacaoBase


class CartorioSumiuNaGravacaoTest(ImportacaoBase):
    """P3 (#263 rodada 3): cartório escolhido que some DURANTE a gravação.

    A revisão foi lida com o cartório de pé; ele é excluído antes de o ato
    gravar (o ``Cartorios`` não é travado). Origem e transmissão viram
    ``decisao_perdida`` na linha do cartório — nunca o lançamento gravado
    sem ele.
    """

    def _escolher(self, extracao, chave):
        cartorio = Cartorios.objects.create(
            nome='CRI Escolhido', cns='CNS-263-SUM',
        )
        extracao.campos.filter(chave=chave).update(
            cartorio_escolhido=cartorio, criar_novo=False,
        )
        return cartorio

    def _importar_excluindo_no_meio(self, extracao, cartorio):
        marcar = modulo_importacao._atos_marcados

        def marcar_e_excluir(*args, **kwargs):
            # Já passou da leitura da revisão e do token: outro usuário
            # exclui o cartório agora.
            marcados = marcar(*args, **kwargs)
            cartorio.delete()
            return marcados

        with patch.object(
            modulo_importacao, '_atos_marcados', side_effect=marcar_e_excluir,
        ):
            with self.assertRaises(ImportacaoInvalida) as contexto:
                self._importar(extracao)
        return contexto.exception.linhas[0]['erros']

    def test_cartorio_da_transmissao_excluido_e_decisao_perdida(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['cartorio_transmissao'] = self._campo(
            'CRI de Transmissão', 'CRI de Guaíra',
        )
        extracao = self._extracao(payload)
        cartorio = self._escolher(extracao, '/acts/0/cartorio_transmissao')

        (erro,) = self._importar_excluindo_no_meio(extracao, cartorio)

        self.assertEqual(erro['chave'], '/acts/0/cartorio_transmissao')
        self.assertEqual(erro['codigo'], 'decisao_perdida')
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_cartorio_da_origem_excluido_e_decisao_perdida(self):
        extracao = self._extracao(self._payload_origem())
        cartorio = self._escolher(extracao, '/acts/0/origem/cartorio')

        (erro,) = self._importar_excluindo_no_meio(extracao, cartorio)

        self.assertEqual(erro['chave'], '/acts/0/origem/cartorio')
        self.assertEqual(erro['codigo'], 'decisao_perdida')
        self.assertEqual(Lancamento.objects.count(), 0)


class CartorioConcorrenteTest(ImportacaoBase):
    """P1 Greptile (#263 rodada 4): mesmo nome de cartório, uma linha só.

    A trava do ``Documento`` não cobre ``Cartorios`` e só o CNS é unique
    (e é gerado): importações em documentos distintos que criam o mesmo
    nome gravavam duas linhas. A criação é serializada pelo nome
    normalizado e a re-busca sob a trava reaproveita a linha vencedora.
    """

    def test_cartorio_do_outro_escritor_e_reaproveitado(self):
        extracao = self._extracao(self._payload_origem())
        vencedor = {}

        def trava_com_outro_escritor(nome):
            # Esta importação bloqueia na trava do nome (tomada antes do
            # primeiro ato) enquanto a importação do OUTRO documento cria
            # o cartório, commita e libera. A busca, que roda SOB a trava,
            # tem que achar a linha dele.
            vencedor['cartorio'] = Cartorios.objects.create(
                nome='CRI de Origem', cns='CNS-OUTRO-DOC',
            )

        with patch.object(
            modulo_importacao, '_trava_nome_cartorio',
            trava_com_outro_escritor,
        ):
            self._importar(extracao)

        self.assertIn('cartorio', vencedor)
        self.assertEqual(
            Cartorios.objects.filter(nome__iexact='CRI de Origem').count(), 1,
        )
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.cartorio_origem, vencedor['cartorio'])
        # Cartório reutilizado não gera vínculo de auditoria novo.
        self.assertFalse(
            ImportacaoIA.objects.filter(modelo='Cartorios').exists(),
        )

    def test_caminho_sequencial_cria_o_cartorio_uma_vez(self):
        # Regressão do caminho sem disputa: sem concorrente, a importação
        # cria o cartório e o vínculo de auditoria como antes.
        extracao = self._extracao(self._payload_origem())

        self._importar(extracao)

        self.assertEqual(
            Cartorios.objects.filter(nome__iexact='CRI de Origem').count(), 1,
        )
        self.assertTrue(
            ImportacaoIA.objects.filter(modelo='Cartorios').exists(),
        )
