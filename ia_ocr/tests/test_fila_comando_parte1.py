"""Parte 1 de 2 do corpo de ``ComandoProcessOcrQueueTest`` — migração VERBATIM
de ``ia_ocr/tests/test_fila.py`` (Etapa 13 do plano de 400 linhas).

Classe SIMPLES (sem ``TestCase``); quem coleta é a fachada em
``test_fila.py``. ``setUp`` e os testes até o reap pós-partida.
"""

from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from ia_ocr import estados, services
from ia_ocr.models import OcrJob
from ia_ocr.services import claim_proximo_job, criar_job

from .factories import criar_documento_digital, criar_usuario
from .test_fila_base import _Pare


class ComandoProcessOcrQueueTestParte1:
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendSucesso')
    def test_sucesso_persiste_paginas_e_transicoes(self):
        job, _ = criar_job(self.documento, criado_por=self.usuario)
        call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.sha256_pdf, 'a' * 64)
        self.assertEqual(job.page_count, 2)
        self.assertEqual(job.timings_ms, {'total': 1234})
        self.assertEqual(job.origem, 'ocr')

        paginas = list(job.paginas.all())
        self.assertEqual(len(paginas), 2)
        self.assertEqual(paginas[0].texto_ocr, 'texto sintético da página 1')
        self.assertEqual(paginas[0].blocos, [{'bbox': [0, 0, 100, 200]}])
        self.assertEqual(paginas[1].texto_ocr, 'texto sintético da página 2')

        transicoes = [(t.de_status, t.para_status) for t in job.transicoes.all()]
        self.assertEqual(
            transicoes,
            [
                (estados.PENDENTE, estados.EM_EXECUCAO),
                (estados.EM_EXECUCAO, estados.CONCLUIDO),
            ],
        )

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendSucesso')
    def test_timeout_da_flag_e_persistido_no_lease_do_claim(self):
        """O --timeout do worker é o lease gravado no claim: sem isso, o
        lease sairia sempre de OCR_JOB_TIMEOUT_SECONDS e a checagem de
        viabilidade validaria um número que nunca chegou ao banco."""
        antes = timezone.now()
        criar_job(self.documento)

        call_command(
            'process_ocr_queue', '--once', '--timeout', '654', verbosity=0
        )

        job = OcrJob.objects.get(documento_digital=self.documento)
        self.assertEqual(job.status, estados.CONCLUIDO)
        delta = (job.lease_expira_em - antes).total_seconds()
        self.assertGreaterEqual(delta, 653)  # ≈ agora + 654
        self.assertLess(delta, 660)

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendFalhaContratual')
    def test_backend_error_falha_com_codigo_do_servico(self):
        job, _ = criar_job(self.documento)
        call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'SERVICE_UNAVAILABLE')
        self.assertEqual(job.erro_mensagem, 'serviço OCR indisponível')
        self.assertEqual(
            job.transicoes.filter(para_status=estados.FALHOU).count(), 1
        )

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendErroGenerico')
    def test_excecao_generica_vira_erro_interno(self):
        job, _ = criar_job(self.documento)
        call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'ERRO_INTERNO')
        self.assertNotEqual(job.status, estados.EM_EXECUCAO)  # nunca preso

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendDatabaseError')
    def test_database_error_vira_erro_interno(self):
        job, _ = criar_job(self.documento)
        call_command('process_ocr_queue', '--once', verbosity=0)

        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'ERRO_INTERNO')
        self.assertEqual(job.paginas.count(), 0)

    def test_fila_vazia_termina_limpo(self):
        call_command('process_ocr_queue', '--once', verbosity=0)
        self.assertEqual(OcrJob.objects.count(), 0)

    def test_modo_continuo_fecha_conexao_depois_de_drenar_e_antes_de_dormir(self):
        """close_old_connections só entre iterações do modo contínuo.

        No topo do laço ela fecharia a conexão antes do claim: em Postgres
        (CONN_MAX_AGE=0 / TestCase) o claim explode com `connection already
        closed`. A ordem correta é: drenar → fechar → dormir.
        """
        ordem = []

        def fake_sleep(_):
            ordem.append('sleep')
            raise _Pare

        with mock.patch(
            'ia_ocr.management.commands.process_ocr_queue.close_old_connections',
            side_effect=lambda: ordem.append('close'),
        ), mock.patch.object(
            services, 'claim_proximo_job',
            # O worker agora repassa o timeout efetivo ao claim (item 1 da
            # r1 do #259); o mock só registra a ordem — aceita qualquer args.
            side_effect=lambda *args, **kwargs: ordem.append('claim') or None,
        ), mock.patch('time.sleep', side_effect=fake_sleep):
            with self.assertRaises(_Pare):
                call_command('process_ocr_queue', interval=1, verbosity=0)

        self.assertEqual(ordem, ['claim', 'close', 'sleep'])

    def test_once_nao_fecha_conexao_do_worker(self):
        """O caminho --once não fecha a conexão (era a causa dos 6 erros PG)."""
        with mock.patch(
            'ia_ocr.management.commands.process_ocr_queue.close_old_connections'
        ) as close:
            call_command('process_ocr_queue', '--once', verbosity=0)
        close.assert_not_called()

    def test_reap_a_cada_iteracao_recupera_job_expirado_pos_partida(self):
        """Job cujo lease expira DEPOIS da partida é reapado na iteração seguinte."""
        job, _ = criar_job(self.documento)
        claim_proximo_job()  # worker fantasma claima e morre sem finalizar

        sonos = []
        relogio = [0]

        def fake_sleep(_):
            sonos.append(1)
            if len(sonos) == 1:
                # O lease expira durante o primeiro sono (depois da partida).
                OcrJob.objects.filter(pk=job.pk).update(
                    lease_expira_em=timezone.now() - timedelta(seconds=1)
                )
                relogio[0] += 1
            else:
                raise _Pare

        # close_old_connections mockado: fechá-la de verdade dentro do atomic
        # do TestCase mata a transação de teste em Postgres (CONN_MAX_AGE=0) —
        # o close real é objeto do teste anterior (ordem), este é do reap.
        with mock.patch(
            'ia_ocr.management.commands.process_ocr_queue.close_old_connections',
        ), mock.patch(
            'time.monotonic', side_effect=lambda: relogio[0],
        ), mock.patch('time.sleep', side_effect=fake_sleep):
            with self.assertRaises(_Pare):
                call_command(
                    'process_ocr_queue', '--timeout', '3600', '--interval', '1',
                    verbosity=0,
                )

        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'WORKER_TIMEOUT')
