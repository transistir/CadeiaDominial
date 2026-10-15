"""Backends de OCR: interface estável para a I-2 plugar o cliente HTTP.

O backend NUNCA transiciona estado do job — só o management command (via
services) mexe em `status`. Falha de processamento = `OcrBackendError` com
código estável do contrato.
"""

import dataclasses
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils.module_loading import import_string


@dataclasses.dataclass
class ResultadoOcr:
    """Saída de um backend de OCR para um job.

    `paginas`: lista de dicts com `numero_pagina`, `texto` e `blocos`
    (bbox/confiança por bloco, quando o serviço fornecer).
    """

    paginas: list
    sha256_pdf: str
    page_count: int
    timings_ms: dict
    # None (default) preserva a origem definida no criar_job (ex.:
    # texto_embutido da I-2); só um valor explícito do resultado sobrescreve.
    origem: str | None = None


class OcrBackendError(Exception):
    """Falha de processamento com código estável do contrato do serviço."""

    def __init__(self, codigo, mensagem):
        self.codigo = codigo
        self.mensagem = mensagem
        super().__init__(f'{codigo}: {mensagem}')


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


def get_backend() -> OcrBackend:
    caminho = getattr(settings, 'OCR_BACKEND', 'ia_ocr.backends.StubBackend')
    return import_string(caminho)()
