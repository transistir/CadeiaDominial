"""Parte 2 de 2 do corpo de ``ComandoProcessOcrQueueTest`` — migração VERBATIM
de ``ia_ocr/tests/test_fila.py`` (Etapa 13 do plano de 400 linhas).

Classe SIMPLES (sem ``TestCase``); quem coleta é a fachada em
``test_fila.py``. Persistência resiliente, origem do resultado, PII e
mensagens locais.
"""

import io
import logging
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from django.core.management import call_command
from django.db.utils import DatabaseError
from django.test import override_settings

from ia_ocr import estados, services
from ia_ocr.models import PaginaOcr
from ia_ocr.services import criar_job

from .factories import criar_documento_digital
from .test_fila_base import (
    ARQUIVO_ALVO_FALHA_PERSISTENCIA,
    MARCADOR_PII,
    MARCADOR_PII_NOME,
)


class ComandoProcessOcrQueueTestParte2:
    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendSucesso')
    def test_erro_de_persistencia_na_finalizacao_nao_derruba_o_comando(self):
        """Erro de banco ao gravar páginas: job vira falhou/ERRO_INTERNO e o
        worker segue para o próximo job no mesmo ciclo."""
        alvo, _ = criar_job(
            criar_documento_digital(
                upload_por=self.usuario, nome=ARQUIVO_ALVO_FALHA_PERSISTENCIA
            )
        )
        normal, _ = criar_job(self.documento)
        bulk_create_original = PaginaOcr.objects.bulk_create
        primeira_chamada = True

        def falhar_primeira_persistencia(objetos, *args, **kwargs):
            nonlocal primeira_chamada
            if primeira_chamada:
                primeira_chamada = False
                raise DatabaseError('boom sintético')
            return bulk_create_original(objetos, *args, **kwargs)

        with mock.patch.object(
            PaginaOcr.objects, 'bulk_create',
            side_effect=falhar_primeira_persistencia,
        ):
            call_command('process_ocr_queue', '--once', verbosity=0)

        alvo.refresh_from_db()
        self.assertEqual(alvo.status, estados.FALHOU)
        self.assertEqual(alvo.erro_codigo, 'ERRO_INTERNO')
        self.assertEqual(alvo.paginas.count(), 0)
        # O segundo job da fila ainda é processado no mesmo ciclo.
        normal.refresh_from_db()
        self.assertEqual(normal.status, estados.CONCLUIDO)
        self.assertEqual(normal.paginas.count(), 2)

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendSucesso')
    def test_falha_dupla_na_persistencia_nao_derruba_o_comando(self):
        """Se até marcar falhou falhar, o comando sobrevive: o job fica
        em_execucao e o reap do próximo ciclo é a rede de segurança."""
        alvo, _ = criar_job(self.documento)

        with mock.patch.object(
            PaginaOcr.objects, 'bulk_create', side_effect=DatabaseError('boom'),
        ), mock.patch.object(
            services, 'marcar_falha_interna', side_effect=DatabaseError('boom'),
        ):
            call_command('process_ocr_queue', '--once', verbosity=0)

        alvo.refresh_from_db()
        self.assertEqual(alvo.status, estados.EM_EXECUCAO)  # reap recuperará

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendSemOrigem')
    def test_resultado_sem_origem_preserva_a_origem_do_job(self):
        """Resultado sem origem não pisa o texto_embutido definido no criar_job."""
        job, _ = criar_job(self.documento, origem='texto_embutido')
        call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.origem, 'texto_embutido')

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendSucesso')
    def test_resultado_com_origem_ocr_valida_sobrescreve(self):
        job, _ = criar_job(self.documento, origem='texto_embutido')
        call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.origem, 'ocr')

    @override_settings(
        OCR_BACKEND='ia_ocr.tests.test_fila.BackendOrigemTextoEmbutido'
    )
    def test_resultado_com_origem_texto_embutido_valida_sobrescreve(self):
        job, _ = criar_job(self.documento, origem='ocr')
        call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.origem, 'texto_embutido')

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendOrigemInvalida')
    def test_resultado_com_origem_invalida_falha_sem_persistir_resultado(self):
        job, _ = criar_job(self.documento, origem='ocr')
        call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'ERRO_INTERNO')
        self.assertEqual(
            job.erro_mensagem, 'falha interna no processamento do job'
        )
        self.assertEqual(job.origem, 'ocr')
        self.assertEqual(job.paginas.count(), 0)
        self.assertEqual(
            job.transicoes.filter(para_status=estados.CONCLUIDO).count(), 0
        )
        self.assertEqual(
            job.transicoes.filter(para_status=estados.FALHOU).get().motivo,
            'ERRO_INTERNO',
        )

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendTimingsSuspeitos')
    def test_timings_nao_numericos_nao_sao_persistidos_nem_logados(self):
        job, _ = criar_job(self.documento)

        with self.assertLogs('ia_ocr.services', level='INFO') as logs:
            call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.timings_ms, {'total': 4321})
        for mensagem in logs.output:
            self.assertNotIn(MARCADOR_PII_NOME, mensagem)
            self.assertNotIn('arquivo', mensagem)

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendErroForaDoContrato')
    def test_codigo_fora_da_allowlist_vira_erro_interno_com_mensagem_local(self):
        job, _ = criar_job(self.documento)
        call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'ERRO_INTERNO')
        self.assertEqual(
            job.erro_mensagem, 'falha interna no processamento do job'
        )
        self.assertNotIn('quebra de linha sintética', job.erro_mensagem)

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendVazaPii')
    def test_pii_da_excecao_nao_vaza_em_log_nem_stdout(self):
        """Exceção carregando texto sintético não pode vazar em caplog/stdout/DB."""
        job, _ = criar_job(self.documento)

        class _Capturador(logging.Handler):
            def __init__(self):
                super().__init__(level=logging.DEBUG)
                self.mensagens = []

            def emit(self, record):
                self.mensagens.append(record.getMessage())

        capturador = _Capturador()
        raiz = logging.getLogger()
        raiz.addHandler(capturador)
        try:
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                call_command('process_ocr_queue', '--once', verbosity=0)
        finally:
            raiz.removeHandler(capturador)

        for mensagem in capturador.mensagens:
            self.assertNotIn(MARCADOR_PII, mensagem)
            self.assertNotIn(MARCADOR_PII_NOME, mensagem)
        self.assertNotIn(MARCADOR_PII, stdout.getvalue())
        self.assertNotIn(MARCADOR_PII, stderr.getvalue())

        # E nenhuma mensagem em texto-vivo vai para o banco.
        job.refresh_from_db()
        self.assertNotIn(MARCADOR_PII, job.erro_mensagem)
        self.assertNotIn(MARCADOR_PII, job.erro_codigo)

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendVazaPii')
    def test_pii_nao_vaza_nem_com_verbosity_3_nem_em_exc_text(self):
        """--verbosity 3 e exc_info: nenhum record pode carregar o marcador."""
        job, _ = criar_job(self.documento)
        formatador = logging.Formatter()

        with self.assertLogs(level='WARNING') as logs:
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                call_command('process_ocr_queue', '--once', verbosity=3)

        for record in logs.records:
            formatado = formatador.format(record)  # mensagem + exc_text
            self.assertNotIn(MARCADOR_PII, formatado)
            self.assertNotIn(MARCADOR_PII_NOME, formatado)
            # Caminho por job nunca usa logger.exception (traceback = PII).
            self.assertIsNone(record.exc_info)
        self.assertNotIn(MARCADOR_PII, stdout.getvalue())
        self.assertNotIn(MARCADOR_PII, stderr.getvalue())
