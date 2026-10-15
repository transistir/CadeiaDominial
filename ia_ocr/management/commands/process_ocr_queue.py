"""Worker da fila de OCR (ADR-003: Postgres SKIP LOCKED, sem infra nova).

Fluxo por job: claim (services) → backend.processar → finalizar (services).
Logs só com job_id, status, timings e códigos de erro — nunca texto do
documento nem dados do PDF (PII de terceiros), nem traceback por job.
"""

import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from ia_ocr import services
from ia_ocr.backends import OcrBackendError, get_backend

logger = logging.getLogger('ia_ocr.process_ocr_queue')


class Command(BaseCommand):
    help = 'Processa a fila de jobs de OCR (claim → backend → finalização).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--once', action='store_true',
            help='Drena a fila uma única vez e sai (sem loop).',
        )
        parser.add_argument(
            '--max-jobs', type=int, default=None,
            help='Máximo de jobs processados nesta execução.',
        )
        parser.add_argument(
            '--interval', type=float, default=None,
            help='Segundos entre iterações no modo contínuo '
                 '(default settings.OCR_QUEUE_INTERVAL_SECONDS).',
        )
        parser.add_argument(
            '--timeout', type=float, default=None,
            help='Timeout do lease em segundos '
                 '(default settings.OCR_JOB_TIMEOUT_SECONDS).',
        )
        parser.add_argument(
            '--reap-stale', dest='reap_stale', action='store_true', default=True,
            help='Reapa jobs em_execucao expirados no início (padrão).',
        )
        parser.add_argument(
            '--no-reap-stale', dest='reap_stale', action='store_false',
            help='Não reapar jobs expirados no início.',
        )

    def handle(self, *args, **options):
        intervalo = options['interval']
        if intervalo is None:
            intervalo = getattr(settings, 'OCR_QUEUE_INTERVAL_SECONDS', 30.0)
        timeout = options['timeout']
        if timeout is None:
            timeout = getattr(settings, 'OCR_JOB_TIMEOUT_SECONDS', 3600.0)

        if options['reap_stale']:
            reapados = services.reap_jobs_expirados(timeout)
            if reapados:
                logger.info(
                    'reap: %s job(s) expirados → falhou/WORKER_TIMEOUT', reapados
                )

        backend = get_backend()
        processados = 0
        while True:
            while (options['max_jobs'] is None
                   or processados < options['max_jobs']):
                if not self._processar_um_job(backend):
                    break  # fila vazia
                processados += 1
            if options['once'] or (
                options['max_jobs'] is not None
                and processados >= options['max_jobs']
            ):
                break
            # Só no modo contínuo, entre iterações: reap de leases que
            # expiraram DEPOIS da partida (job de worker morto não fica
            # preso em em_execucao para sempre) e higiene de conexões ANTES
            # de dormir. Nunca no topo do laço: ali fecharia a conexão antes
            # do claim do caminho --once e, em Postgres (CONN_MAX_AGE=0 /
            # TestCase), o claim explode com `connection already closed`.
            reapados = services.reap_jobs_expirados(timeout)
            if reapados:
                logger.info(
                    'reap: %s job(s) expirados → falhou/WORKER_TIMEOUT', reapados
                )
            close_old_connections()
            time.sleep(intervalo)

        logger.info('encerrando: jobs processados=%s', processados)

    def _processar_um_job(self, backend):
        """Claim + processa um job. False se a fila está vazia.

        Nenhuma exceção derruba o worker: falha do backend E falha da
        persistência da finalização (ex.: IntegrityError de página
        duplicada no bulk_create) deixam o job em `falhou`/ERRO_INTERNO; se
        até isso falhar (banco fora), o reap do próximo ciclo é a rede de
        segurança.
        """
        job = services.claim_proximo_job()
        if job is None:
            return False
        tentativa = job.tentativa
        try:
            resultado = backend.processar(job)
        except Exception as excecao:
            if not isinstance(excecao, OcrBackendError):
                logger.warning(
                    'job_id=%s excecao_inesperada=%s',
                    job.job_id, type(excecao).__name__,
                )
            resultado_ou_erro = excecao
        else:
            resultado_ou_erro = resultado
        try:
            services.finalizar(job, resultado_ou_erro, tentativa)
        except Exception as excecao:
            # O atomic de finalizar já sofreu rollback; uma NOVA transação
            # marca o job falhou. Log só com tipo da exceção + job_id —
            # traceback por job pode carregar texto do documento (PII).
            logger.error(
                'job_id=%s falha ao persistir a finalizacao (%s): '
                'marcando ERRO_INTERNO',
                job.job_id, type(excecao).__name__,
            )
            try:
                services.marcar_falha_interna(job, tentativa)
            except Exception:
                logger.error(
                    'job_id=%s nao pode ser marcado falhou; o reap do proximo '
                    'ciclo e a rede de segurança',
                    job.job_id,
                )
        return True
