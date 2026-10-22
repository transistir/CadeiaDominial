"""Backends de OCR: interface estável para a I-2 plugar o cliente HTTP.

O backend NUNCA transiciona estado do job — só o management command (via
services) mexe em `status`. Falha de processamento = `OcrBackendError` com
código estável do contrato.
"""

import dataclasses
import hashlib
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

_CODIGOS_ERRO_SERVICO = frozenset({
    'INVALID_INPUT',
    'UNSUPPORTED_MEDIA_TYPE',
    'FILE_TOO_LARGE',
    'EMPTY_FILE',
    'INVALID_PDF',
    'ENCRYPTED_PDF',
    'TOO_MANY_PAGES',
    'PDF_PAGE_TOO_LARGE',
    'INVALID_OCR_RESULT',
    'EMPTY_OCR_RESULT',
    'OUTPUT_TOO_LARGE',
    'JOB_NOT_FOUND',
    'JOB_TIMEOUT',
    'JOB_ID_CONFLICT',
    'QUEUE_FULL',
    'UNAUTHORIZED',
    'INFERENCE_FAILED',
})


@dataclasses.dataclass
class ResultadoOcr:
    """Saída de um backend de OCR para um job.

    `paginas` é um iterável de dicts com `numero_pagina`, `texto` e `blocos`
    (bbox/confiança por bloco, quando o serviço fornecer). O contrato exige
    exatamente uma entrada por página, numerada de 1 a `page_count`, sem
    duplicatas.
    """

    paginas: Iterable[dict]
    sha256_pdf: str
    page_count: int
    timings_ms: dict
    # None (default) preserva a origem definida no criar_job (ex.:
    # texto_embutido da I-2); só um valor explícito do resultado sobrescreve.
    origem: str | None = None
    # DPI efetivo do raster: o que o serviço declarou ter usado, ou o DPI
    # solicitado quando o resultado não o traz. None só no texto_embutido
    # (não houve raster) — aí o job não tem DPI a persistir.
    dpi: int | None = None


class OcrBackendError(Exception):
    """Falha de processamento com código estável do contrato do serviço."""

    def __init__(self, codigo, mensagem):
        self.codigo = codigo
        self.mensagem = mensagem
        super().__init__(f'{codigo}: {mensagem}')


class OrcamentoEsgotado(Exception):
    """O prazo monotônico compartilhado da operação foi consumido."""


class OcrBackend(ABC):
    @abstractmethod
    def processar(self, job) -> ResultadoOcr:
        """Processa o job e devolve o resultado. Falha → OcrBackendError."""


class StubBackend(OcrBackend):
    """Placeholder da I-1: falha sempre, com código estável."""

    def processar(self, job):
        raise OcrBackendError(
            'BACKEND_NAO_IMPLEMENTADO',
            'Backend de OCR ainda não implementado (plugue o cliente HTTP na I-2).',
        )


class OcrServiceBackend(OcrBackend):
    """Backend do serviço OCR v1.0.1, sem persistência nem transições.

    Em cada página, ``blocos`` permanece um JSONField opaco para a I-1 e tem
    o formato ``{'dpi', 'width_px', 'height_px', 'blocos': [...]}``. Assim a
    geometria e seus blocos viajam juntos sem exigir migração em PaginaOcr.

    A tentativa 1 usa o próprio ``OcrJob.job_id``. Tentativas posteriores
    usam ``uuid5(job.job_id, str(tentativa))``; retries de transporte e
    reenvios após perda no serviço preservam sempre o mesmo ID da tentativa.
    """

    def processar(self, job):
        from . import leitor_pdf

        try:
            prazo = self._prazo_monotonico(job)
            arquivo = job.documento_digital.arquivo
            sha256_pdf = self._calcular_sha256(arquivo, prazo)
            inspecao = leitor_pdf.inspecionar_pdf(
                arquivo.path,
                prazo=prazo,
                max_bytes=settings.OCR_MAX_BYTES,
                max_paginas=settings.OCR_MAX_PAGINAS,
                ler_texto=not job.forcar_ocr,
                min_chars_pagina=settings.OCR_TEXTO_EMBUTIDO_MIN_CHARS_PAGINA,
            )

            if not job.forcar_ocr:
                paginas_locais = leitor_pdf.paginas_texto_embutido(
                    inspecao.texto_por_pagina,
                    min_chars_pagina=(
                        settings.OCR_TEXTO_EMBUTIDO_MIN_CHARS_PAGINA
                    ),
                )
                if paginas_locais is not None:
                    return ResultadoOcr(
                        paginas=paginas_locais,
                        sha256_pdf=sha256_pdf,
                        page_count=inspecao.page_count,
                        timings_ms={},
                        origem='texto_embutido',
                    )

            return self._processar_no_servico(
                job,
                arquivo.path,
                sha256_pdf,
                inspecao.page_count,
                prazo,
            )
        except OrcamentoEsgotado as exc:
            raise OcrBackendError(
                'WORKER_TIMEOUT', 'Prazo do worker OCR esgotado.'
            ) from exc

    @staticmethod
    def _prazo_monotonico(job):
        expiracao = job.lease_expira_em
        if expiracao is None:
            expiracao = job.atualizado_em + timedelta(
                seconds=settings.OCR_JOB_TIMEOUT_SECONDS
            )
        segundos = (
            expiracao - timezone.now()
        ).total_seconds() - settings.OCR_MARGEM_PERSISTENCIA_SECONDS
        # Única conversão do prazo de relógio civil para o relógio monotônico.
        return time.monotonic() + segundos

    @staticmethod
    def _conferir_prazo(prazo):
        if time.monotonic() >= prazo:
            raise OrcamentoEsgotado('Prazo do job OCR esgotado.')

    def _calcular_sha256(self, arquivo, prazo):
        digest = hashlib.sha256()
        self._conferir_prazo(prazo)
        with arquivo.open('rb') as aberto:
            for chunk in aberto.chunks():
                self._conferir_prazo(prazo)
                digest.update(chunk)
        self._conferir_prazo(prazo)
        return digest.hexdigest()

    def _processar_no_servico(
        self, job, caminho_pdf, sha256_pdf, page_count, prazo
    ):
        from .ocr_client import OcrServiceClient

        paginas_para_orcamento = page_count or 0
        cliente = OcrServiceClient(
            settings.OCR_SERVICE_URL,
            settings.OCR_INTERNAL_TOKEN,
            settings.OCR_ACCESS_CLIENT_ID,
            settings.OCR_ACCESS_CLIENT_SECRET,
            timeout_s=settings.OCR_HTTP_TIMEOUT_SECONDS,
            max_tentativas=settings.OCR_HTTP_MAX_TENTATIVAS,
            backoff_base_s=settings.OCR_HTTP_BACKOFF_BASE_SECONDS,
            backoff_max_s=settings.OCR_BACKOFF_MAX_SECONDS,
            reserva_retry_s=(
                settings.OCR_FOLGA_FILA_SECONDS
                + paginas_para_orcamento * settings.OCR_SEGUNDOS_POR_PAGINA
            ),
            poll_interval_s=settings.OCR_POLL_INTERVAL_SECONDS,
        )
        job_id_servico = self._job_id_servico(job)
        if page_count is None:
            max_pages = settings.OCR_MAX_PAGINAS
        else:
            max_pages = min(
                100, max(page_count, settings.OCR_MAX_PAGINAS)
            )
        reenvios = 0
        estado = self._enviar(
            cliente, caminho_pdf, job_id_servico, max_pages, prazo
        )

        while True:
            try:
                estado = self._aguardar_conclusao(
                    cliente, job_id_servico, estado, prazo
                )
                resultado = cliente.obter_resultado(
                    job_id_servico, prazo, formato='full'
                )
            except OcrBackendError as exc:
                if exc.codigo != 'JOB_NOT_FOUND':
                    raise
                if reenvios >= settings.OCR_MAX_REENVIOS_LOST:
                    raise OcrBackendError(
                        'JOB_NOT_FOUND',
                        'Job OCR perdido após o limite de reenvios.',
                    ) from None
                reenvios += 1
                estado = self._enviar(
                    cliente, caminho_pdf, job_id_servico, max_pages, prazo
                )
                continue

            status_resultado = resultado.get('status') if isinstance(
                resultado, dict
            ) else None
            if status_resultado in {'queued', 'processing'}:
                estado = resultado
                continue
            if status_resultado == 'failed':
                self._levantar_falha_do_estado(resultado)
            return self._montar_resultado(
                job,
                resultado,
                sha256_pdf,
                self._dpi_efetivo(resultado, settings.OCR_DPI),
            )

    @staticmethod
    def _dpi_efetivo(resultado, dpi_solicitado):
        """O DPI que o serviço DECLAROU usar; ausente/inválido → o solicitado.

        O envio pede ``settings.OCR_DPI``, mas o serviço pode rasterizar em
        outro DPI — e bbox pixel→PDF só converge com o DPI real. `bool` é
        int em Python: não vale como DPI.
        """
        remoto = resultado.get('dpi') if isinstance(resultado, dict) else None
        if type(remoto) is int and remoto > 0:
            return remoto
        return dpi_solicitado

    @staticmethod
    def _job_id_servico(job):
        if job.tentativa == 1:
            return str(job.job_id)
        return str(uuid.uuid5(job.job_id, str(job.tentativa)))

    def _enviar(self, cliente, caminho_pdf, job_id_servico, max_pages, prazo):
        restante = prazo - time.monotonic()
        if restante <= 0:
            raise OrcamentoEsgotado('Prazo esgotado antes do envio OCR.')
        timeout_seconds = max(
            1,
            min(
                86_400,
                int(restante) - settings.OCR_FOLGA_FILA_SECONDS,
            ),
        )
        return cliente.enviar_job(
            caminho_pdf,
            job_id_servico,
            prazo,
            dpi=settings.OCR_DPI,
            timeout_seconds=timeout_seconds,
            max_pages=max_pages,
        )

    def _aguardar_conclusao(self, cliente, job_id_servico, estado, prazo):
        while True:
            if not isinstance(estado, dict):
                raise OcrBackendError(
                    'INVALID_OCR_RESULT', 'Estado inválido do serviço OCR.'
                )
            status = estado.get('status')
            progresso = estado.get('progress')
            if isinstance(progresso, dict):
                pages_done = progresso.get('pages_done')
                if isinstance(pages_done, int) and not isinstance(
                    pages_done, bool
                ):
                    logger.info(
                        'job_id=%s status=%s pages_done=%s',
                        job_id_servico,
                        status,
                        pages_done,
                    )
            if status == 'succeeded':
                return estado
            if status == 'failed':
                self._levantar_falha_do_estado(estado)
            if status not in {'queued', 'processing'}:
                raise OcrBackendError(
                    'INVALID_OCR_RESULT', 'Estado inválido do serviço OCR.'
                )

            restante = prazo - time.monotonic()
            if restante <= 0:
                raise OrcamentoEsgotado('Prazo esgotado durante o poll OCR.')
            espera = min(settings.OCR_POLL_INTERVAL_SECONDS, restante)
            if espera > 0:
                time.sleep(espera)
            estado = cliente.consultar_job(job_id_servico, prazo)

    @staticmethod
    def _levantar_falha_do_estado(estado):
        erro = estado.get('error')
        codigo = erro.get('code') if isinstance(erro, dict) else None
        if codigo not in _CODIGOS_ERRO_SERVICO:
            codigo = 'ERRO_INTERNO'
        raise OcrBackendError(codigo, 'O serviço OCR informou falha no job.')

    @staticmethod
    def _montar_resultado(job, resultado, sha256_pdf, dpi):
        try:
            source = resultado['source']
            sha256_remoto = source['sha256']
            page_count = source['page_count']
            paginas = [
                {
                    'numero_pagina': pagina['page'],
                    'texto': pagina['text'],
                    'blocos': {
                        'dpi': dpi,
                        'width_px': pagina.get('width_px'),
                        'height_px': pagina.get('height_px'),
                        'blocos': pagina.get('blocks', []),
                    },
                }
                for pagina in resultado['pages']
            ]
            timings_ms = resultado.get('timings_ms', {})
        except (KeyError, TypeError):
            raise OcrBackendError(
                'INVALID_OCR_RESULT', 'Resultado inválido do serviço OCR.'
            ) from None
        if sha256_remoto != sha256_pdf:
            logger.error('job_id=%s sha256 do resultado divergente', job.job_id)
            raise OcrBackendError(
                'ERRO_INTERNO', 'Integridade do resultado OCR inválida.'
            )
        return ResultadoOcr(
            paginas=paginas,
            sha256_pdf=sha256_pdf,
            page_count=page_count,
            timings_ms=timings_ms,
            origem='ocr',
            dpi=dpi,
        )


def get_backend() -> OcrBackend:
    caminho = getattr(settings, 'OCR_BACKEND', 'ia_ocr.backends.StubBackend')
    return import_string(caminho)()
