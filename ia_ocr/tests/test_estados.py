"""Fachada dos testes da máquina de estados OCR (Etapa 16)."""

from django.test import TestCase

from .test_estados_precondicao_retry_cas import (
    CasSemTentativaExplicitaTestParte,
    PreCondicaoDeExtracaoTestParte,
    RetryTestParte,
)
from .test_estados_transicoes_confirmacao import (
    ConfirmacaoDeTextoTestParte,
    PaginaCorrigidaTestParte,
    TransicoesValidasTestParte,
)


class TransicoesValidasTest(TransicoesValidasTestParte, TestCase):
    """Fachada com o ID histórico."""


class ConfirmacaoDeTextoTest(ConfirmacaoDeTextoTestParte, TestCase):
    """Fachada com o ID histórico."""


class PaginaCorrigidaTest(PaginaCorrigidaTestParte, TestCase):
    """Fachada com o ID histórico."""


class PreCondicaoDeExtracaoTest(PreCondicaoDeExtracaoTestParte, TestCase):
    """Fachada com o ID histórico."""


class RetryTest(RetryTestParte, TestCase):
    """Fachada com o ID histórico."""


class CasSemTentativaExplicitaTest(CasSemTentativaExplicitaTestParte, TestCase):
    """Fachada com o ID histórico."""
