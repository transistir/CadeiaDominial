"""Fachada dos testes do fallback de cartório."""

from .test_cartorio_fallback_base import CartorioFallbackBase
from .test_cartorio_fallback_parte1 import CartorioFallbackTestParte1
from .test_cartorio_fallback_parte2 import CartorioFallbackTestParte2
from .test_revisao_tela_base import TelaRevisaoBase


class CartorioFallbackTest(
    CartorioFallbackTestParte1,
    CartorioFallbackTestParte2,
    CartorioFallbackBase,
    TelaRevisaoBase,
):
    """Nome preservado para os ids dos testes de fallback."""
