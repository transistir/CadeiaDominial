"""Concorrência real: editar/confirmar página × transição para texto_confirmado.

`TransactionTestCase` + threads com conexões próprias. Exige row-lock real
(`select_for_update`): na suíte sqlite esta classe é PULADA (comportamento
esperado); rodar contra um Postgres local para valer (mesmo critério de
test_concorrencia_pg.py).

Invariante (issue #261 / I-4): o job nunca fica em `texto_confirmado` com
página não confirmada/editada, e nenhuma página muda depois da transição. Toda
mutação de página toma a trava do job (`services._travar_job_editavel`) e a
transição toma a mesma linha no seu CAS.
"""

import threading
from unittest import mock

from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from ia_ocr import estados, services
from ia_ocr.estados import TransicaoInvalida
from ia_ocr.models import (
    ESTADO_CONFIRMADA, ESTADO_EDITADA, OcrJob,
)
from ia_ocr.services import TextoNaoEditavel

from .factories import criar_job_concluido, criar_usuario

ESPERA_S = 10
BLOQUEIO_S = 1.0


def _rodar(destino, resultado, chave):
    """Executa `destino` numa thread com conexão própria, guardando o desfecho."""
    def alvo():
        close_old_connections()
        try:
            resultado[chave] = ('ok', destino())
        except Exception as exc:  # o desfecho (inclusive a exceção) é o que se afirma
            resultado[chave] = ('erro', exc)
        finally:
            close_old_connections()

    thread = threading.Thread(target=alvo, name=f'i4-{chave}')
    thread.start()
    return thread


@skipUnlessDBFeature('has_select_for_update')
class EdicaoXTransicaoTest(TransactionTestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.job = criar_job_concluido(textos=['alfa', 'beta'])
        for numero in (1, 2):
            services.confirmar_pagina(self.job, numero, self.usuario)

    def test_transicao_espera_a_edicao_em_andamento_e_a_enxerga(self):
        """Edição já dentro da trava: a transição bloqueia, vê a página editada e recusa."""
        dentro = threading.Event()
        liberar = threading.Event()
        normalizar = services._normalizar_quebras_de_linha

        def normalizar_devagar(texto):
            # Chamada por editar_pagina DEPOIS de travar o job e ler a página.
            dentro.set()
            liberar.wait(timeout=ESPERA_S)
            return normalizar(texto)

        resultado = {}
        with mock.patch.object(services, '_normalizar_quebras_de_linha', normalizar_devagar):
            edicao = _rodar(
                lambda: services.editar_pagina(self.job, 1, 'alfa mexida'), resultado, 'edicao'
            )
            self.assertTrue(dentro.wait(timeout=ESPERA_S), 'a edição não chegou a travar o job')

            transicao = _rodar(
                lambda: services.confirmar_texto(self.job, self.usuario), resultado, 'transicao'
            )
            transicao.join(timeout=BLOQUEIO_S)
            self.assertTrue(
                transicao.is_alive(),
                'a transição não esperou a trava do job tomada pela edição',
            )

            liberar.set()
            edicao.join(timeout=ESPERA_S)
            transicao.join(timeout=ESPERA_S)

        self.assertEqual(resultado['edicao'][0], 'ok', resultado['edicao'])
        desfecho, erro = resultado['transicao']
        self.assertEqual(desfecho, 'erro')
        self.assertIsInstance(erro, TransicaoInvalida)
        self.assertEqual(erro.code, 'paginas_nao_confirmadas')
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertEqual(self.job.paginas.get(numero_pagina=1).estado, ESTADO_EDITADA)
        self.assertFalse(
            self.job.transicoes.filter(para_status=estados.TEXTO_CONFIRMADO).exists()
        )

    def test_edicao_espera_a_transicao_em_andamento_e_e_recusada(self):
        """Transição já com o CAS feito: a edição bloqueia, vê texto_confirmado e recusa."""
        dentro = threading.Event()
        liberar = threading.Event()
        validar = OcrJob._validar_confirmacao_de_texto

        def validar_devagar(job):
            # Depois do UPDATE do CAS (linha do job travada), antes do commit.
            dentro.set()
            liberar.wait(timeout=ESPERA_S)
            return validar(job)

        resultado = {}
        with mock.patch.object(OcrJob, '_validar_confirmacao_de_texto', validar_devagar):
            transicao = _rodar(
                lambda: services.confirmar_texto(self.job, self.usuario), resultado, 'transicao'
            )
            self.assertTrue(dentro.wait(timeout=ESPERA_S), 'a transição não chegou ao CAS')

            edicao = _rodar(
                lambda: services.editar_pagina(self.job, 1, 'tarde demais'), resultado, 'edicao'
            )
            edicao.join(timeout=BLOQUEIO_S)
            self.assertTrue(
                edicao.is_alive(),
                'a edição não esperou a transição em andamento',
            )

            liberar.set()
            transicao.join(timeout=ESPERA_S)
            edicao.join(timeout=ESPERA_S)

        self.assertEqual(resultado['transicao'][0], 'ok', resultado['transicao'])
        desfecho, erro = resultado['edicao']
        self.assertEqual(desfecho, 'erro')
        self.assertIsInstance(erro, TextoNaoEditavel)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)
        pagina = self.job.paginas.get(numero_pagina=1)
        self.assertEqual(pagina.estado, ESTADO_CONFIRMADA)
        self.assertEqual(pagina.texto_confirmado, 'alfa')
