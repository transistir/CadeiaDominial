"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.
"""

import io
import threading
from contextlib import redirect_stdout
from copy import deepcopy
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import (
    RequestFactory, TestCase, TransactionTestCase, skipUnlessDBFeature,
)
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, TIs, UserTI,
)
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from ia_ocr import importacao as modulo_importacao
from ia_ocr import services
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    CAMPOS_DA_ORIGEM, ParteRevisada, RevisaoInvalidada, dados_revisados,
    desnormalizar, descrever_aviso,
)
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao, payload_com_closure,
    payload_registro,
)
from .test_texto_concorrencia_pg import _rodar
from .test_importacao_base import ESPERA_S, BLOQUEIO_S, ImportacaoFixture, ImportacaoBase, _post_cadastro_manual


class ErroPorCampoTest(ImportacaoBase):
    """Cenário 7: message_dict do full_clean vira erro na linha do ato."""

    def test_erro_de_campo_mapeia_para_a_chave_do_titulo(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        # Defesa em profundidade: a revisão já teria bloqueado um título
        # fora do limite; o patch isola o MAPEAMENTO do message_dict do
        # modelo para a chave de linha que a tela conhece.
        with patch.object(
            Lancamento, 'full_clean',
            side_effect=ValidationError({'titulo': ['Fora do limite.']}),
        ):
            with self.assertRaises(ImportacaoInvalida) as contexto:
                self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['chave'], '/acts/0/titulo')
        self.assertEqual(erro['codigo'], 'campo_invalido')
        self.assertEqual(erro['mensagem'], 'Fora do limite.')
        self.assertEqual(Lancamento.objects.count(), 0)


class EstadoEVersaoTest(ImportacaoBase):
    """Cenários 8 e 9: estado do job, idempotência, versão e atos marcados."""

    def test_job_extraido_recusa_com_estado_invalido(self):
        self.job.status = 'extraido'
        self.job.save(update_fields=['status'])
        extracao = self._extracao(payload_registro(self.job.job_id))

        with self.assertRaises(services.ExtracaoRecusada) as contexto:
            self._importar(extracao)

        self.assertEqual(contexto.exception.code, 'estado_invalido')

    def test_importado_e_idempotente_com_a_mesma_versao_da_tela(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        versao_tela = services.versao_bloco(extracao)

        primeiro = importar(extracao, self.usuario, versao_tela, ['/acts/0'])
        # A tela não recarregou: manda a mesma versão (agora velha — as
        # linhas viraram importado). O job importado responde o resultado
        # gravado em vez de conflitar.
        segundo = importar(extracao, self.usuario, versao_tela, ['/acts/0'])

        self.assertEqual(Lancamento.objects.count(), 1)
        self.assertTrue(segundo['ok'])
        self.assertEqual(segundo['linhas'][0]['status'], 'criado')
        self.assertEqual(
            segundo['linhas'][0]['lancamento_id'],
            primeiro['linhas'][0]['lancamento_id'],
        )
        self.assertEqual(
            self.job.transicoes.filter(para_status='importado').count(), 1,
        )

    def test_replay_de_12_atos_devolve_as_linhas_em_ordem_numerica(self):
        # Rodada 8 (review Opus, P3): o replay do job importado ordenava as
        # chaves como TEXTO — '/acts/10' vinha antes de '/acts/2'. A ordem
        # devolvida é a do payload, pelo índice numérico do ato.
        payload = payload_registro(self.job.job_id)
        for ordem in range(2, 13):
            ato = deepcopy(payload['acts'][0])
            ato['ordem'] = ordem
            ato['data'] = self._campo(
                f'{2019 + ordem}-02-15', '15 de fevereiro de 2020',
            )
            payload['acts'].append(ato)
        extracao = self._extracao(payload)
        versao_tela = services.versao_bloco(extracao)

        primeiro = self._importar(extracao, versao=versao_tela)
        segundo = self._importar(extracao, versao=versao_tela)

        self.assertTrue(primeiro['ok'])
        self.assertTrue(segundo['ok'])
        self.assertEqual(
            [linha['chave'] for linha in segundo['linhas']],
            [f'/acts/{indice}' for indice in range(12)],
        )

    def test_versao_velha_e_conflito(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        versao_tela = services.versao_bloco(extracao)
        # A revisão mudou depois que a tela leu o token.
        CampoSugerido.objects.filter(chave='/acts/0/area').update(
            valor_final='9.99',
        )

        with self.assertRaises(services.ConflitoVersao):
            importar(extracao, self.usuario, versao_tela, ['/acts/0'])

        self.assertEqual(Lancamento.objects.count(), 0)

    def test_ato_desmarcado_aparece_ignorado(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'].append(
            deepcopy(payload['acts'][0]) | {'ordem': 2}
        )
        payload['acts'][1]['data'] = self._campo(
            '2021-03-20', '20 de março de 2021',
        )
        extracao = self._extracao(payload)

        resultado = self._importar(extracao, atos=['/acts/0'])

        self.assertEqual(Lancamento.objects.count(), 1)
        self.assertEqual(len(resultado['linhas']), 2)
        ignorado = resultado['linhas'][1]
        self.assertEqual(ignorado['chave'], '/acts/1')
        self.assertEqual(ignorado['status'], 'ignorado')
        self.assertIsNone(ignorado['lancamento_id'])
        self.assertFalse(
            extracao.campos
            .filter(chave__startswith='/acts/1')
            .filter(status_revisao='importado')
            .exists()
        )

    def test_ato_inexistente_recusa(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        with self.assertRaises(services.ExtracaoRecusada) as contexto:
            self._importar(extracao, atos=['/acts/9'])

        self.assertEqual(contexto.exception.code, 'ato_invalido')

    def test_lista_vazia_recusa(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        with self.assertRaises(services.ExtracaoRecusada) as contexto:
            self._importar(extracao, atos=[])

        self.assertEqual(contexto.exception.code, 'nenhum_ato')


class DecisaoPerdidaTest(ImportacaoBase):
    """Cadastro escolhido (pessoa/cartório) deletado após a finalização."""

    def test_pessoa_deletada_deixa_a_revisao_invalida(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        maria = Pessoas.objects.create(nome='MARIA EXISTENTE', cpf='11122233344')
        extracao.campos.filter(chave='/acts/0/partes/1').update(
            pessoa_escolhida=maria, criar_novo=False,
        )
        # A tela leu o token ANTES da exclusão (#263 rodada 3): o SET_NULL
        # muda a linha e envelhece o token, mas a resposta tem de dizer
        # ONDE a decisão se perdeu — não um conflito de versão genérico.
        versao_tela = services.versao_bloco(extracao)
        # A escolha morre com a pessoa (FK SET_NULL): a linha volta a ser
        # pendência de escolha e o motor de revisão recusa antes da gravação.
        maria.delete()

        with self.assertRaises(RevisaoInvalidada):
            self._importar(extracao, versao=versao_tela)

        # Aceite da rodada 2 (#263): a recusa preserva as pendências
        # estruturadas para a tela identificar a parte — uma escolha que
        # virou nada depois da finalização é decisão perdida, não uma
        # pendência genérica de escolha.
        pendencias = modulo_importacao.pendencias_para_resposta(extracao)
        self.assertIn(
            {'chave': '/acts/0/partes/1', 'motivo': 'decisao_perdida'},
            pendencias,
        )

        self.assertEqual(Lancamento.objects.count(), 0)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')

    def test_cartorio_da_origem_deletado_vira_decisao_perdida(self):
        # P3 (#263 rodada 3): ``cartorio_escolhido`` também é SET_NULL — a
        # pendência genérica de escolha vira decisão perdida na linha da
        # origem, como na parte.
        extracao = self._extracao(self._payload_origem())
        escolhido = Cartorios.objects.create(
            nome='CRI Escolhido', cns='CNS-263-ESC',
        )
        extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=escolhido, criar_novo=False,
        )
        versao_tela = services.versao_bloco(extracao)
        escolhido.delete()

        with self.assertRaises(RevisaoInvalidada):
            self._importar(extracao, versao=versao_tela)

        self.assertIn(
            {'chave': '/acts/0/origem/cartorio', 'motivo': 'decisao_perdida'},
            modulo_importacao.pendencias_para_resposta(extracao),
        )
        self.assertEqual(Lancamento.objects.count(), 0)


@skipUnlessDBFeature('has_select_for_update', 'has_select_for_update_of')
class ImportacaoXCadastroManualPostgresTest(
    ImportacaoFixture, TransactionTestCase,
):
    """Concorrência real (2 conexões): a trava do Documento serializa os fluxos.

    ``TransactionTestCase`` + threads com conexões próprias (mesmo padrão
    de ``test_texto_concorrencia_pg``). Na suíte sqlite esta classe é
    PULADA (comportamento esperado); rodar contra um Postgres para valer.
    """

    def setUp(self):
        super().setUp()
        self.dentro = threading.Event()
        self.liberar = threading.Event()
        vincular = modulo_importacao._vincular

        def vincular_devagar(*args, **kwargs):
            # Depois de travar o Documento e gravar o lançamento do ato,
            # antes do commit: a importação segura as travas aqui.
            self.dentro.set()
            self.liberar.wait(timeout=ESPERA_S)
            return vincular(*args, **kwargs)

        patcher = patch.object(modulo_importacao, '_vincular', vincular_devagar)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.liberar.set)

    def _importacao_segurando_a_trava(self, extracao, resultado):
        importacao = _rodar(
            lambda: self._importar(extracao), resultado, 'importacao',
        )
        self.assertTrue(
            self.dentro.wait(timeout=ESPERA_S),
            'a importação não chegou a travar o Documento',
        )
        return importacao

    def test_importacao_trava_o_documento_e_nao_o_imovel(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        resultado = {}
        importacao = self._importacao_segurando_a_trava(extracao, resultado)

        # NOWAIT falha na hora se a linha estiver travada por outra conexão.
        with transaction.atomic():
            Imovel.objects.select_for_update(nowait=True).get(pk=self.imovel.pk)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                Documento.objects.select_for_update(nowait=True).get(
                    pk=self.documento.pk,
                )

        self.liberar.set()
        importacao.join(timeout=ESPERA_S)
        self.assertEqual(resultado['importacao'][0], 'ok', resultado['importacao'])

    def test_cadastro_manual_espera_a_importacao_e_recusa_o_mesmo_numero(self):
        payload = payload_registro(self.job.job_id)
        # O importador compõe 'R{numero} {documento.numero}' (#322 rodada
        # 3); o manual compõe com a sigla do POST — aqui a do documento, para
        # os dois fluxos disputarem o MESMO número.
        payload['acts'][0]['numero_lancamento'] = self._campo(
            'R-1', 'R-1/42.718',
        )
        extracao = self._extracao(payload)
        post = _post_cadastro_manual(self.tipo_registro)
        post['sigla_matricula'] = self.documento.numero
        request = RequestFactory().post('/lancamento/criar/', post)
        request.user = self.usuario
        resultado = {}
        importacao = self._importacao_segurando_a_trava(extracao, resultado)

        manual = _rodar(
            lambda: LancamentoCriacaoService.criar_lancamento_completo(
                request, self.imovel.terra_indigena_id, self.imovel,
                self.documento,
            ),
            resultado, 'manual',
        )
        manual.join(timeout=BLOQUEIO_S)
        self.assertTrue(
            manual.is_alive(),
            'o cadastro manual não esperou a trava do Documento',
        )

        self.liberar.set()
        importacao.join(timeout=ESPERA_S)
        manual.join(timeout=ESPERA_S)

        self.assertEqual(resultado['importacao'][0], 'ok', resultado['importacao'])
        self.assertEqual(resultado['manual'][0], 'ok', resultado['manual'])
        lancamento, mensagem = resultado['manual'][1]
        self.assertIsNone(lancamento)
        self.assertIn(
            f'Já existe um lançamento com o número "R1 {self.documento.numero}"',
            mensagem,
        )
        self.assertEqual(
            Lancamento.objects.filter(documento=self.documento).count(), 1,
        )


class StdoutSemValorDocumentalTest(ImportacaoBase):
    """P2-9 (#263 rodada 2): stdout da importação sem número/tipo documental."""

    def test_importacao_nao_imprime_o_numero_da_origem(self):
        extracao = self._extracao(self._payload_origem())

        saida = io.StringIO()
        with redirect_stdout(saida):
            self._importar(extracao)

        self.assertNotIn('366', saida.getvalue())


# ---------------------------------------------------------------------------
# Rodada 4 (bots no PR #310): CPF/cartório disputados por importações em
# documentos distintos, origem pontuada virando dois documentos e origem só
# com cartório.
# ---------------------------------------------------------------------------
