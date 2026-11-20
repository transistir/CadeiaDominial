"""Fachada dos testes do fallback de cartório.

A parte 2 (save/seletor pela tela de cards) saiu com a tela, aposentada na
fase 4 da #341 — o resolvedor direto que resta está na parte 1.
"""

from .test_cartorio_fallback_base import CartorioFallbackBase
from .test_cartorio_fallback_parte1 import CartorioFallbackTestParte1
from .test_revisao_tela_base import TelaRevisaoBase


class CartorioFallbackTest(
    CartorioFallbackTestParte1,
    CartorioFallbackBase,
    TelaRevisaoBase,
):
    """Nome preservado para os ids dos testes de fallback."""
