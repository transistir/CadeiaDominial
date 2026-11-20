"""Fachada dos testes de PII OCR (Etapa 16, limite de 400 linhas)."""

from django.test import TestCase

from .test_pii_base import (
    BackendCodigoContratual,
    BackendCodigoForjadoComPii,
    BackendExcecaoInesperada,
    BackendMensagemComPii,
    BackendTimingComChaveDesconhecida,
    BackendTimingComChavePii,
    BackendTimingComValorTextual,
    BackendTimingsContratuais,
    MARCADOR_CHAVE_TIMING,
    MARCADOR_CODIGO,
    MARCADOR_PII,
    NOME_SENSIVEL,
)
__all__ = [
    'BackendCodigoContratual',
    'BackendCodigoForjadoComPii',
    'BackendExcecaoInesperada',
    'BackendMensagemComPii',
    'BackendTimingComChaveDesconhecida',
    'BackendTimingComChavePii',
    'BackendTimingComValorTextual',
    'BackendTimingsContratuais',
    'MARCADOR_CHAVE_TIMING',
    'MARCADOR_CODIGO',
    'MARCADOR_PII',
    'NOME_SENSIVEL',
]

from .test_pii_parte1 import SanitizacaoDePiiDoBackendTestParte
from .test_pii_parte2 import (
    ExclusoesComOcrTestParte,
    ExclusoesSemOcrTestParte,
    StrSemNomeDoArquivoTestParte,
)


class SanitizacaoDePiiDoBackendTest(SanitizacaoDePiiDoBackendTestParte, TestCase):
    """Fachada com o ID histórico."""


class StrSemNomeDoArquivoTest(StrSemNomeDoArquivoTestParte, TestCase):
    """Fachada com o ID histórico."""


class ExclusoesComOcrTest(ExclusoesComOcrTestParte, TestCase):
    """Fachada com o ID histórico."""


class ExclusoesSemOcrTest(ExclusoesSemOcrTestParte, TestCase):
    """Fachada com o ID histórico."""
