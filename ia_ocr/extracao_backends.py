"""Backends da extração estruturada (I-5).

Espelha ``ia_ocr.backends``: um backend abstrato, o stub que nunca
opina com o serviço, e o backend do serviço real (que usa o cliente
HTTP do prazo absoluto). ``get_extracao_backend()`` resolve o caminho
por string em ``settings.EXTRACAO_BACKEND``.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils.module_loading import import_string

CAMINHO_BACKEND_STUB = 'ia_ocr.extracao_backends.StubExtracaoBackend'


@dataclasses.dataclass
class ResultadoExtracao:
    """Saída de um backend de extração para um job.

    `payload` é o dict validado pelo A3 (ver extracao_schema.py) — os
    campos sugeridos nascem dele; nenhum serviço de log recebe o valor
    lido (PII).
    """

    payload: dict


class ExtracaoBackendError(Exception):
    """Falha de extração com código estável do contrato do serviço."""

    def __init__(self, codigo, mensagem):
        self.codigo = codigo
        self.mensagem = mensagem
        super().__init__(f'{codigo}: {mensagem}')


class ExtracaoBackend(ABC):
    @abstractmethod
    def extrair(self, requisicao) -> ResultadoExtracao:
        """Extrai a partir da requisição. Falha → ExtracaoBackendError."""


class StubExtracaoBackend(ExtracaoBackend):
    """Placeholder: falha sempre, com código estável — nunca opinar."""

    def extrair(self, requisicao):
        raise ExtracaoBackendError(
            'EXTRACAO_NAO_IMPLEMENTADA',
            'Backend de extração ainda não implementado '
            '(plugue o serviço real em EXTRACAO_BACKEND).',
        )


class ExtracaoServiceBackend(ExtracaoBackend):
    """Backend do serviço de extração real: uma POST dogmática."""

    def extrair(self, requisicao):
        from .extracao_client import ExtracaoServiceClient

        cliente = ExtracaoServiceClient(
            settings.EXTRACAO_SERVICE_URL,
            settings.EXTRACAO_INTERNAL_TOKEN,
            settings.EXTRACAO_ACCESS_CLIENT_ID,
            settings.EXTRACAO_ACCESS_SECRET,
        )
        payload = cliente.extrair(requisicao)
        return ResultadoExtracao(payload=payload)


def get_extracao_backend() -> ExtracaoBackend:
    caminho = getattr(settings, 'EXTRACAO_BACKEND', CAMINHO_BACKEND_STUB)
    return import_string(caminho)()
