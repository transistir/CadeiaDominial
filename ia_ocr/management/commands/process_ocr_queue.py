"""Worker da fila de OCR (ADR-003: Postgres SKIP LOCKED, sem infra nova).

Fluxo por job: claim (services) → backend.processar → finalizar (services).
Logs só com job_id, status, timings e códigos de erro — nunca texto do
documento nem dados do PDF (PII de terceiros), nem traceback por job.
"""

import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from ia_ocr import services
from ia_ocr.backends import OcrBackendError, get_backend
from ia_ocr.checks import (
    backend_real, conta_do_orcamento, lease_minimo_seconds,
)

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

        self._conferir_viabilidade_do_lease(timeout)

        if options['reap_stale']:
            self._reap_expirados(timeout)

        backend = get_backend()
        processados = 0
        proximo_reap = time.monotonic() + intervalo
        while True:
            while (options['max_jobs'] is None
                   or processados < options['max_jobs']):
                if not self._processar_um_job(backend, timeout):
                    break  # fila vazia
                processados += 1
                # --once preserva a semântica original: reap somente no início.
                if (
                    not options['once']
                    and time.monotonic() >= proximo_reap
                ):
                    self._reap_expirados(timeout)
                    proximo_reap = time.monotonic() + intervalo
            if options['once'] or (
                options['max_jobs'] is not None
                and processados >= options['max_jobs']
            ):
                break
            # No modo contínuo, a cadência também é conferida com fila vazia.
            # A higiene de conexões continua somente ANTES de dormir. Nunca no
            # topo do laço: ali fecharia a conexão antes do claim do caminho
            # --once e, em Postgres (CONN_MAX_AGE=0 / TestCase), o claim
            # explode com `connection already closed`.
            if time.monotonic() >= proximo_reap:
                self._reap_expirados(timeout)
                proximo_reap = time.monotonic() + intervalo
            close_old_connections()
            time.sleep(intervalo)

        logger.info('encerrando: jobs processados=%s', processados)

    @staticmethod
    def _conferir_viabilidade_do_lease(timeout):
        """Falha rápida com backend real: lease abaixo do orçamento máximo
        de um job faria o reap encerrar o job antes de ele concluir e
        persistir — queimaria a tentativa em vez de processar. Com
        StubBackend nada é validado (a I-1 não fala com serviço nenhum).
        """
        if not backend_real():
            return
        minimo = lease_minimo_seconds()
        if timeout < minimo:
            raise CommandError(
                f'Lease insuficiente: timeout ({timeout:g} s, '
                '--timeout/OCR_JOB_TIMEOUT_SECONDS) não cobre o orçamento '
                'máximo de um job: OCR_MAX_PAGINAS × OCR_SEGUNDOS_POR_PAGINA '
                '+ OCR_FOLGA_FILA_SECONDS + OCR_MARGEM_PERSISTENCIA_SECONDS '
                f'= {conta_do_orcamento()}. Aumente o lease antes de '
                'processar a fila.'
            )

    @staticmethod
    def _reap_expirados(timeout):
        reapados = services.reap_jobs_expirados(timeout)
        if reapados:
            logger.info(
                'reap: %s job(s) expirados → falhou/WORKER_TIMEOUT', reapados
            )

    def _processar_um_job(self, backend, timeout=None):
        """Claim + processa um job. False se a fila está vazia.

        Nenhuma exceção derruba o worker: falha do backend E falha da
        persistência da finalização (ex.: DatabaseError no bulk_create)
        deixam o job em `falhou`/ERRO_INTERNO; se até isso falhar (banco
        fora), o reap do próximo ciclo é a rede de segurança.
        """
        job = services.claim_proximo_job(timeout_s=timeout)
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
