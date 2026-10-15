"""Fila de OCR: comando, claim CAS, reap, finalização tardia e vazamento de PII."""

import io
import logging
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.db import transaction
from django.db.utils import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone

from ia_ocr import estados, services
from ia_ocr.backends import OcrBackend, OcrBackendError, ResultadoOcr
from ia_ocr.models import OcrJob, OcrJobTransicao, PaginaOcr
from ia_ocr.services import (
    claim_proximo_job, criar_job, finalizar, reap_jobs_expirados,
)

from .factories import criar_documento_digital, criar_usuario

MARCADOR_PII = 'CPF-SINTETICO-999.888.777-66'
MARCADOR_PII_NOME = 'PROPRIETARIO-SINTETICO-XYZ'


def _resultado():
    return ResultadoOcr(
        paginas=[
            {
                'numero_pagina': 1,
                'texto': 'texto sintético da página 1',
                'blocos': [{'bbox': [0, 0, 100, 200]}],
            },
            {'numero_pagina': 2, 'texto': 'texto sintético da página 2', 'blocos': None},
        ],
        sha256_pdf='a' * 64,
        page_count=2,
        timings_ms={'total_ms': 1234},
        origem='ocr',
    )


class BackendSucesso(OcrBackend):
    def processar(self, job):
        return _resultado()


class BackendFalhaContratual(OcrBackend):
    def processar(self, job):
        raise OcrBackendError('SERVICE_UNAVAILABLE', 'gateway respondeu 503')


class BackendErroGenerico(OcrBackend):
    def processar(self, job):
        raise RuntimeError('explode de propósito')


class BackendDatabaseError(OcrBackend):
    def processar(self, job):
        raise DatabaseError('boom sintético')


class BackendVazaPii(OcrBackend):
    def processar(self, job):
        raise RuntimeError(
            f'falha lendo página do documento {MARCADOR_PII} de {MARCADOR_PII_NOME}'
        )


class BackendSemOrigem(OcrBackend):
    """Resultado sem `origem` explícita: a origem definida no criar_job prevalece."""

    def processar(self, job):
        return ResultadoOcr(
            paginas=[{'numero_pagina': 1, 'texto': 'texto sintético', 'blocos': None}],
            sha256_pdf='e' * 64,
            page_count=1,
            timings_ms={'total_ms': 10},
        )


class BackendOrigemTextoEmbutido(OcrBackend):
    def processar(self, job):
        resultado = _resultado()
        resultado.origem = 'texto_embutido'
        return resultado


class BackendOrigemInvalida(OcrBackend):
    def processar(self, job):
        resultado = _resultado()
        resultado.origem = 'origem_invalida'
        return resultado


class BackendPaginaDuplicada(OcrBackend):
    """Devolucao com numero_pagina repetido (viola unique_together) para o
    documento alvo: a persistência da finalização explode com IntegrityError."""

    ALVO = 'alvo-pagina-duplicada.pdf'

    def processar(self, job):
        if job.documento_digital.nome_original == self.ALVO:
            return ResultadoOcr(
                paginas=[
                    {'numero_pagina': 1, 'texto': 'texto sintético', 'blocos': None},
                    {'numero_pagina': 1, 'texto': 'texto sintético (repetido)', 'blocos': None},
                ],
                sha256_pdf='f' * 64,
                page_count=2,
                timings_ms={'total_ms': 5},
            )
        return _resultado()


class BackendTimingsSuspeitos(OcrBackend):
    """timings_ms com texto/bool/lista: só escalares numéricos podem persistir."""

    def processar(self, job):
        return ResultadoOcr(
            paginas=[{'numero_pagina': 1, 'texto': 'texto sintético', 'blocos': None}],
            sha256_pdf='g' * 64,
            page_count=1,
            timings_ms={
                'total_ms': 4321,
                'arquivo': f'{MARCADOR_PII_NOME}.pdf',
                'aceito': True,
                'lista': [1, 2],
            },
        )


class BackendErroForaDoContrato(OcrBackend):
    """Código fora de [A-Z0-9_] e mensagem longa com quebra de linha."""

    def processar(self, job):
        raise OcrBackendError(
            'serviço fora do ar!', 'x' * 600 + '\nquebra de linha sintética'
        )


class _Pare(Exception):
    """Sentinela para encerrar o modo contínuo no teste."""


class ComandoProcessOcrQueueTest(TestCase):
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
        self.assertEqual(job.timings_ms, {'total_ms': 1234})
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
            side_effect=lambda: ordem.append('claim') or None,
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

        def fake_sleep(_):
            sonos.append(1)
            if len(sonos) == 1:
                # O lease expira durante o primeiro sono (depois da partida).
                OcrJob.objects.filter(pk=job.pk).update(
                    atualizado_em=timezone.now() - timedelta(seconds=7201)
                )
            else:
                raise _Pare

        # close_old_connections mockado: fechá-la de verdade dentro do atomic
        # do TestCase mata a transação de teste em Postgres (CONN_MAX_AGE=0) —
        # o close real é objeto do teste anterior (ordem), este é do reap.
        with mock.patch(
            'ia_ocr.management.commands.process_ocr_queue.close_old_connections',
        ), mock.patch('time.sleep', side_effect=fake_sleep):
            with self.assertRaises(_Pare):
                call_command(
                    'process_ocr_queue', '--timeout', '3600', '--interval', '1',
                    verbosity=0,
                )

        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'WORKER_TIMEOUT')

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendPaginaDuplicada')
    def test_erro_de_persistencia_na_finalizacao_nao_derruba_o_comando(self):
        """IntegrityError ao gravar páginas: job vira falhou/ERRO_INTERNO e o
        worker segue para o próximo job no mesmo ciclo."""
        alvo, _ = criar_job(
            criar_documento_digital(
                upload_por=self.usuario, nome=BackendPaginaDuplicada.ALVO
            )
        )
        normal, _ = criar_job(self.documento)

        call_command('process_ocr_queue', '--once', verbosity=0)  # não pode explodir

        alvo.refresh_from_db()
        self.assertEqual(alvo.status, estados.FALHOU)
        self.assertEqual(alvo.erro_codigo, 'ERRO_INTERNO')
        self.assertEqual(alvo.paginas.count(), 0)
        # O segundo job da fila ainda é processado no mesmo ciclo.
        normal.refresh_from_db()
        self.assertEqual(normal.status, estados.CONCLUIDO)
        self.assertEqual(normal.paginas.count(), 2)

    @override_settings(OCR_BACKEND='ia_ocr.tests.test_fila.BackendPaginaDuplicada')
    def test_falha_dupla_na_persistencia_nao_derruba_o_comando(self):
        """Se até marcar falhou falhar, o comando sobrevive: o job fica
        em_execucao e o reap do próximo ciclo é a rede de segurança."""
        alvo, _ = criar_job(
            criar_documento_digital(
                upload_por=self.usuario, nome=BackendPaginaDuplicada.ALVO
            )
        )

        with mock.patch.object(
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
        self.assertEqual(job.timings_ms, {'total_ms': 4321})
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


class _SeletorComDisputa:
    """Delega ao queryset real; no 1º .first() outro worker "rouba" o
    candidato devolvido (muda o estado entre a seleção e o nosso CAS).

    Diferente do seletor falso antigo: filter/exclude/order_by continuam
    reais — só a disputa do primeiro candidato é injetada.
    """

    def __init__(self, queryset, roubar):
        self._queryset = queryset
        self._roubar = roubar  # lista mutável compartilhada por toda a cadeia

    def _encadear(self, queryset):
        return _SeletorComDisputa(queryset, self._roubar)

    def filter(self, *args, **kwargs):
        return self._encadear(self._queryset.filter(*args, **kwargs))

    def exclude(self, *args, **kwargs):
        return self._encadear(self._queryset.exclude(*args, **kwargs))

    def order_by(self, *args, **kwargs):
        return self._encadear(self._queryset.order_by(*args, **kwargs))

    def first(self):
        candidato = self._queryset.first()
        if candidato is not None and self._roubar:
            self._roubar.clear()
            OcrJob.objects.filter(
                pk=candidato.pk, status=estados.PENDENTE,
            ).update(
                status=estados.EM_EXECUCAO, atualizado_em=timezone.now(),
            )
        return candidato


class ClaimProximoJobTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    def test_claim_marca_em_execucao_e_audita(self):
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job()

        self.assertIsNotNone(claimado)
        self.assertEqual(claimado.pk, job.pk)
        self.assertEqual(claimado.status, estados.EM_EXECUCAO)
        self.assertEqual(
            claimado.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 1
        )
        self.assertIsNone(claim_proximo_job())  # fila drenada

    def test_claim_respeita_ordem_de_criacao(self):
        antigo, _ = criar_job(self.documento)
        novo, _ = criar_job(self.documento)
        with transaction.atomic():
            OcrJob.objects.filter(pk=antigo.pk).update(
                criado_em=timezone.now() - timedelta(minutes=10)
            )
        claimado = claim_proximo_job()
        self.assertEqual(claimado.pk, antigo.pk)

    def test_disputa_real_perde_o_primeiro_candidato_e_claima_o_segundo(self):
        """CAS do candidato A falha (outro worker vence entre a seleção e o
        UPDATE) e o claim segue para o candidato B — seleção real, com
        exclude de verdade."""
        job_antigo, _ = criar_job(self.documento)
        job_novo, _ = criar_job(self.documento)
        with transaction.atomic():
            OcrJob.objects.filter(pk=job_antigo.pk).update(
                criado_em=timezone.now() - timedelta(minutes=10)
            )

        roubar = ['sim']

        def select_for_update_disputa(**kwargs):
            return _SeletorComDisputa(OcrJob.objects.all(), roubar)

        with mock.patch.object(
            OcrJob.objects, 'select_for_update',
            side_effect=select_for_update_disputa,
        ):
            claimado = claim_proximo_job()

        self.assertIsNotNone(claimado)
        self.assertEqual(claimado.pk, job_novo.pk)  # perdeu A, claimou B
        job_antigo.refresh_from_db()
        self.assertEqual(job_antigo.status, estados.EM_EXECUCAO)  # levado pelo outro
        job_novo.refresh_from_db()
        self.assertEqual(job_novo.status, estados.EM_EXECUCAO)
        self.assertEqual(
            job_novo.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 1
        )
        self.assertEqual(
            job_antigo.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 0
        )


class ReapJobsExpiradosTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    def _claimar(self):
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job()
        self.assertIsNotNone(claimado)
        return claimado

    def test_em_execucao_recente_nao_e_reapado(self):
        job = self._claimar()
        reapados = reap_jobs_expirados(timeout_s=3600)
        self.assertEqual(reapados, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.EM_EXECUCAO)

    def test_em_execucao_expirado_vira_falhou_worker_timeout(self):
        job = self._claimar()
        # Envelhece o lease além do timeout.
        OcrJob.objects.filter(pk=job.pk).update(
            atualizado_em=timezone.now() - timedelta(seconds=7200)
        )
        reapados = reap_jobs_expirados(timeout_s=3600)

        self.assertEqual(reapados, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)
        self.assertEqual(job.erro_codigo, 'WORKER_TIMEOUT')
        transicao = job.transicoes.latest('criado_em')
        self.assertEqual(
            (transicao.de_status, transicao.para_status),
            (estados.EM_EXECUCAO, estados.FALHOU),
        )

    def test_borda_do_timeout_de_um_segundo(self):
        """Dentro do timeout (3599 s de lease) não é reapado; fora (3601 s), é."""
        dentro = self._claimar()
        fora, _ = criar_job(self.documento)
        self.assertIsNotNone(claim_proximo_job())  # claima `fora`

        OcrJob.objects.filter(pk=dentro.pk).update(
            atualizado_em=timezone.now() - timedelta(seconds=3599)
        )
        OcrJob.objects.filter(pk=fora.pk).update(
            atualizado_em=timezone.now() - timedelta(seconds=3601)
        )

        reapados = reap_jobs_expirados(timeout_s=3600)

        self.assertEqual(reapados, 1)
        dentro.refresh_from_db()
        fora.refresh_from_db()
        self.assertEqual(dentro.status, estados.EM_EXECUCAO)
        self.assertEqual(fora.status, estados.FALHOU)
        self.assertEqual(fora.erro_codigo, 'WORKER_TIMEOUT')


class FinalizacaoTardiaTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    def test_finalizacao_do_worker_antigo_e_descartada(self):
        """claim → reap → retry → claim(2): resultado do worker antigo é
        descartado pelo filtro de TENTATIVA (o job está em_execucao na
        tentativa 2 — não é o status que salva)."""
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job()
        self.assertEqual(claimado.tentativa, 1)

        reap_jobs_expirados(timeout_s=0)  # lease expira imediatamente
        job.refresh_from_db()
        self.assertEqual(job.status, estados.FALHOU)

        job.retry(motivo='reap manual')  # volta a pendente na tentativa 2
        novo_claim = claim_proximo_job()  # tentativa 2 assume o lease
        self.assertIsNotNone(novo_claim)
        self.assertEqual(novo_claim.tentativa, 2)

        # O worker antigo (tentativa 1) tenta finalizar tardiamente.
        with self.assertLogs('ia_ocr.services', level='WARNING') as logs:
            aplicado = finalizar(claimado, _resultado(), tentativa=1)

        self.assertFalse(aplicado)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.EM_EXECUCAO)  # lease da tentativa 2 intacto
        self.assertEqual(job.tentativa, 2)
        self.assertEqual(job.paginas.count(), 0)  # resultado descartado
        self.assertEqual(
            job.transicoes.filter(para_status=estados.CONCLUIDO).count(), 0
        )
        # Auditoria da tentativa 2 intacta: 2 claims (tentativas 1 e 2).
        self.assertEqual(
            job.transicoes.filter(para_status=estados.EM_EXECUCAO).count(), 2
        )
        # O log de descarte carrega só job_id/tentativa — sem PII.
        self.assertTrue(
            any(str(job.job_id) in mensagem for mensagem in logs.output)
        )

    def test_finalizacao_valida_aplica_resultado(self):
        job, _ = criar_job(self.documento)
        claimado = claim_proximo_job()
        aplicado = finalizar(claimado, _resultado(), tentativa=claimado.tentativa)

        self.assertTrue(aplicado)
        job.refresh_from_db()
        self.assertEqual(job.status, estados.CONCLUIDO)
        self.assertEqual(job.paginas.count(), 2)
