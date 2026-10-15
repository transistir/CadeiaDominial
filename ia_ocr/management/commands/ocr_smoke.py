"""Comando de evidência do fluxo OCR (#259): provas de aceite do dono.

Dois modos, dois públicos:

- ``--pdf <caminho>``: cliente HTTP direto (diagnóstico local + upload +
  poll + resultado full) com um job_id novo, SEM tocar no banco. É o
  caminho das evidências (1) e (3) contra o serviço real. A saída carrega
  só job_id, status, page_count, contagens por página, presença de bbox,
  chaves de geometria e timings_ms — nunca texto do documento,
  nome/caminho do arquivo, token ou credenciais. ``--sem-diagnostico-
  local`` envia o arquivo como está: um PDF inválido precisa voltar com o
  código DO SERVIÇO (o diagnóstico local o barraria antes).
- ``--documento-digital <id> --confirmar``: caminho de aplicação no
  SERVIDOR DE TESTES — cria/reaproveita o job do documento com
  ``forcar_ocr=True``, roda o backend real e finaliza via services.
  ESCREVE no banco: por isso recusa sem ``--confirmar``.
"""

import os
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from dominial.models import DocumentoDigital

from ia_ocr import estados, leitor_pdf, services
from ia_ocr.backends import (
    OcrBackendError, OcrServiceBackend, OrcamentoEsgotado,
)
from ia_ocr.models import OcrJob, OcrJobTransicao
from ia_ocr.ocr_client import OcrServiceClient
from ia_ocr.services import CHAVES_TIMING_PERMITIDAS, CODIGOS_ERRO_PERMITIDOS

MENSAGEM_RECUSA_DOCUMENTO_DIGITAL = (
    'O modo --documento-digital ESCREVE no banco (cria/reaproveita job de '
    'OCR e persiste páginas) e é destinado ao SERVIDOR DE TESTES. Confirme '
    'explicitamente com --confirmar.'
)

TETO_PAGINAS_SERVICO = 100
MIN_PAGINAS_SERVICO = 25


class Command(BaseCommand):
    help = (
        'Evidência do fluxo OCR: cliente direto (--pdf, sem escrita em '
        'banco) ou aplicação no servidor de testes (--documento-digital '
        '--confirmar).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--pdf', default=None,
            help='Caminho do PDF para o ciclo direto contra o serviço '
                 '(nenhuma escrita em banco).',
        )
        parser.add_argument(
            '--sem-diagnostico-local', action='store_true',
            help='Pula o diagnóstico local e envia o arquivo como está '
                 '(prova dos códigos DE ERRO do próprio serviço).',
        )
        parser.add_argument(
            '--documento-digital', type=int, default=None,
            help='ID do DocumentoDigital para o caminho de aplicação '
                 '(exige --confirmar; servidor de TESTES).',
        )
        parser.add_argument(
            '--confirmar', action='store_true',
            help='Confirma que o modo --documento-digital pode escrever no '
                 'banco do servidor de testes.',
        )
        parser.add_argument(
            '--prazo', type=float, default=None,
            help='Prazo total em segundos do modo --pdf (default: '
                 'OCR_JOB_TIMEOUT_SECONDS - OCR_MARGEM_PERSISTENCIA_SECONDS).',
        )

    def handle(self, *args, **options):
        documento_id = options['documento_digital']
        if documento_id is not None:
            if not options['confirmar']:
                raise CommandError(MENSAGEM_RECUSA_DOCUMENTO_DIGITAL)
            self._modo_documento_digital(documento_id)
            return
        if options['pdf'] is None:
            raise CommandError(
                'Informe --pdf <caminho> ou '
                '--documento-digital <id> --confirmar.'
            )
        self._modo_pdf(options['pdf'], options)

    # ------------------------------------------------------------------
    # Modo --pdf: cliente direto, zero banco.

    def _modo_pdf(self, caminho, options):
        if not os.path.exists(caminho):
            raise CommandError('O arquivo informado não existe.')
        prazo = self._prazo_monotonico(options['prazo'])

        page_count = None
        if not options['sem_diagnostico_local']:
            try:
                inspecao = leitor_pdf.inspecionar_pdf(
                    caminho,
                    prazo=prazo,
                    max_bytes=settings.OCR_MAX_BYTES,
                    max_paginas=settings.OCR_MAX_PAGINAS,
                )
            except OcrBackendError as exc:
                self.stdout.write('status=falhou')
                self.stdout.write('origem=diagnostico_local')
                self.stdout.write(f'erro_codigo={exc.codigo}')
                raise CommandError(
                    'Diagnóstico local recusou o arquivo '
                    f'(erro_codigo={exc.codigo}).'
                ) from None
            page_count = inspecao.page_count

        job_id = uuid.uuid4()
        cliente = self._cliente(page_count)
        try:
            params = {
                'dpi': settings.OCR_DPI,
                'timeout_seconds': self._timeout_seconds(prazo),
            }
            if page_count is not None:
                params['max_pages'] = min(
                    TETO_PAGINAS_SERVICO, max(page_count, MIN_PAGINAS_SERVICO)
                )
            estado = cliente.enviar_job(caminho, job_id, prazo, **params)
            resultado = self._aguardar_resultado(cliente, job_id, estado, prazo)
        except (OcrBackendError, OrcamentoEsgotado) as exc:
            codigo = (
                exc.codigo if isinstance(exc, OcrBackendError)
                else 'WORKER_TIMEOUT'
            )
            self.stdout.write(f'job_id={job_id}')
            self.stdout.write('status=falhou')
            self.stdout.write(f'erro_codigo={codigo}')
            raise CommandError(
                f'Job OCR falhou contra o serviço (erro_codigo={codigo}).'
            ) from None
        self._imprimir_resultado(job_id, resultado)

    @staticmethod
    def _prazo_monotonico(prazo_s):
        if prazo_s is None:
            prazo_s = (
                settings.OCR_JOB_TIMEOUT_SECONDS
                - settings.OCR_MARGEM_PERSISTENCIA_SECONDS
            )
        return time.monotonic() + max(1.0, prazo_s)

    @staticmethod
    def _timeout_seconds(prazo):
        restante = prazo - time.monotonic()
        return max(1, min(86_400, int(restante) - settings.OCR_FOLGA_FILA_SECONDS))

    @staticmethod
    def _cliente(page_count):
        reserva_retry_s = (
            settings.OCR_FOLGA_FILA_SECONDS
            + (page_count or 0) * settings.OCR_SEGUNDOS_POR_PAGINA
        )
        return OcrServiceClient(
            settings.OCR_SERVICE_URL,
            settings.OCR_INTERNAL_TOKEN,
            settings.OCR_ACCESS_CLIENT_ID,
            settings.OCR_ACCESS_CLIENT_SECRET,
            timeout_s=settings.OCR_HTTP_TIMEOUT_SECONDS,
            max_tentativas=settings.OCR_HTTP_MAX_TENTATIVAS,
            backoff_base_s=settings.OCR_HTTP_BACKOFF_BASE_SECONDS,
            backoff_max_s=settings.OCR_BACKOFF_MAX_SECONDS,
            reserva_retry_s=reserva_retry_s,
            poll_interval_s=settings.OCR_POLL_INTERVAL_SECONDS,
        )

    def _aguardar_resultado(self, cliente, job_id, estado, prazo):
        """Poll até succeeded/failed e devolve o resultado full."""
        while True:
            status = estado.get('status') if isinstance(estado, dict) else None
            if status == 'failed':
                self._falha_do_estado(estado)
            if status not in {'succeeded', 'queued', 'processing'}:
                raise OcrBackendError(
                    'INVALID_OCR_RESULT', 'Estado inválido do serviço OCR.'
                )
            if status == 'succeeded':
                resultado = cliente.obter_resultado(
                    job_id, prazo, formato='full'
                )
                status_resultado = (
                    resultado.get('status')
                    if isinstance(resultado, dict)
                    else None
                )
                if status_resultado == 'failed':
                    self._falha_do_estado(resultado)
                if status_resultado not in {'queued', 'processing'}:
                    return resultado
                # 409 do /result: ainda não terminou — segue o poll abaixo.
            self._esperar_poll(prazo)
            estado = cliente.consultar_job(job_id, prazo)

    @staticmethod
    def _esperar_poll(prazo):
        restante = prazo - time.monotonic()
        if restante <= 0:
            raise OrcamentoEsgotado('Prazo do ocr_smoke esgotado no poll.')
        espera = min(settings.OCR_POLL_INTERVAL_SECONDS, restante)
        if espera > 0:
            time.sleep(espera)

    @staticmethod
    def _falha_do_estado(estado):
        erro = estado.get('error')
        codigo = erro.get('code') if isinstance(erro, dict) else None
        if codigo not in CODIGOS_ERRO_PERMITIDOS:
            codigo = 'ERRO_INTERNO'
        raise OcrBackendError(codigo, 'O serviço OCR informou falha no job.')

    def _imprimir_resultado(self, job_id, resultado):
        """Saída de evidência: contagens e chaves, nunca conteúdo."""
        self.stdout.write(f'job_id={job_id}')
        self.stdout.write('status=succeeded')
        if not isinstance(resultado, dict):
            raise OcrBackendError(
                'INVALID_OCR_RESULT', 'Resultado inválido do serviço OCR.'
            )
        source = resultado.get('source')
        page_count = source.get('page_count') if isinstance(source, dict) else None
        self.stdout.write(f'page_count={page_count}')

        paginas = resultado.get('pages') or []
        for pagina in sorted(paginas, key=self._numero_da_pagina):
            texto = pagina.get('text')
            chars = len(texto) if isinstance(texto, str) else 0
            blocos = pagina.get('blocks') or []
            com_bbox = bool(blocos) and all(
                isinstance(bloco, dict)
                and isinstance(bloco.get('bbox'), (list, tuple))
                and len(bloco['bbox']) == 4
                for bloco in blocos
            )
            chaves = (
                ','.join(
                    chave
                    for chave in ('width_px', 'height_px')
                    if chave in pagina
                )
                or '-'
            )
            self.stdout.write(
                f"pagina={pagina.get('page')} chars={chars} "
                f"blocos={len(blocos)} bbox={'sim' if com_bbox else 'nao'} "
                f'geometria={chaves}'
            )

        timings = resultado.get('timings_ms')
        pares = []
        if isinstance(timings, dict):
            pares = [
                f'{chave}={valor}'
                for chave, valor in sorted(timings.items())
                if chave in CHAVES_TIMING_PERMITIDAS
                and isinstance(valor, (int, float))
                and not isinstance(valor, bool)
            ]
        self.stdout.write(f"timings_ms {' '.join(pares) or '-'}")

    @staticmethod
    def _numero_da_pagina(pagina):
        numero = pagina.get('page') if isinstance(pagina, dict) else None
        return numero if isinstance(numero, int) else 0

    # ------------------------------------------------------------------
    # Modo --documento-digital: aplicação no servidor de testes.

    def _modo_documento_digital(self, documento_id):
        try:
            documento = DocumentoDigital.objects.get(pk=documento_id)
        except DocumentoDigital.DoesNotExist:
            raise CommandError(
                f'DocumentoDigital {documento_id} não encontrado.'
            ) from None

        job = self._garantir_job_claimado(documento)
        tentativa = job.tentativa
        try:
            resultado = OcrServiceBackend().processar(job)
        except Exception as excecao:
            services.finalizar(job, excecao, tentativa)
            job.refresh_from_db()
            self._imprimir_job(job)
            raise CommandError(
                f'Job OCR falhou (erro_codigo={job.erro_codigo or "ERRO_INTERNO"}).'
            ) from None

        aplicado = services.finalizar(job, resultado, tentativa)
        job.refresh_from_db()
        self._imprimir_job(job)
        if not aplicado:
            raise CommandError('Finalização descartada: o lease do job mudou.')
        if job.status != estados.CONCLUIDO:
            raise CommandError(
                f'Job OCR falhou (erro_codigo={job.erro_codigo}).'
            )

    def _garantir_job_claimado(self, documento):
        """Cria/reaproveita o job vigente do documento e toma o lease dele.

        O claim do services pega o job mais antigo da fila INTEIRA — no
        servidor de testes pode ser de outro documento. Aqui o CAS é
        dirigido a este job, com a mesma auditoria de transição do worker.
        """
        agora = timezone.now()
        lease_expira_em = agora + timedelta(
            seconds=settings.OCR_JOB_TIMEOUT_SECONDS
        )
        with transaction.atomic():
            DocumentoDigital.objects.select_for_update().get(pk=documento.pk)
            job = (
                OcrJob.objects
                .filter(
                    documento_digital_id=documento.pk,
                    status__in=[estados.PENDENTE, estados.EM_EXECUCAO],
                )
                .order_by('criado_em', 'pk')
                .first()
            )
            if job is None:
                job = OcrJob.objects.create(
                    documento_digital_id=documento.pk,
                    origem='ocr',
                    forcar_ocr=True,
                    status=estados.PENDENTE,
                )
            claim = OcrJob.objects.filter(
                pk=job.pk, status=estados.PENDENTE
            ).update(
                status=estados.EM_EXECUCAO,
                atualizado_em=agora,
                lease_expira_em=lease_expira_em,
                forcar_ocr=True,
            )
            if claim:
                OcrJobTransicao.objects.create(
                    ocr_job_id=job.pk,
                    de_status=estados.PENDENTE,
                    para_status=estados.EM_EXECUCAO,
                    motivo='claim do ocr_smoke',
                )
            else:
                # Job em_execucao reaproveitado: renova o lease para este run.
                OcrJob.objects.filter(pk=job.pk).update(
                    atualizado_em=agora,
                    lease_expira_em=lease_expira_em,
                    forcar_ocr=True,
                )
            return OcrJob.objects.get(pk=job.pk)

    def _imprimir_job(self, job):
        """Saída do modo aplicação: status e contagens, nunca conteúdo."""
        self.stdout.write(f'job_id={job.job_id}')
        self.stdout.write(f'status={job.status}')
        self.stdout.write(f'page_count={job.page_count}')
        self.stdout.write(f'paginas_persistidas={job.paginas.count()}')
        if job.status == estados.FALHOU:
            self.stdout.write(f'erro_codigo={job.erro_codigo}')
