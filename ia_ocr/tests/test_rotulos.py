"""Fachada dos cenários do parser de rótulos de lançamento."""

from django.test import TestCase

from .test_rotulos_base import RotulosBase
from .test_rotulos_analisar_classificar import (
    AnalisarRotuloTestParte,
    ClassificarAposTestParte,
)
from .test_rotulos_compor_resolver import (
    ComporNumeroLancamentoTestParte,
    ResolverTipoTestParte,
)


class AnalisarRotuloTest(AnalisarRotuloTestParte, RotulosBase, TestCase):
    """Nome preservado para os ids deste cenário."""


class ClassificarAposTest(ClassificarAposTestParte, RotulosBase, TestCase):
    """Nome preservado para os ids deste cenário."""


class ComporNumeroLancamentoTest(ComporNumeroLancamentoTestParte, RotulosBase, TestCase):
    """Nome preservado para os ids deste cenário."""


class ResolverTipoTest(ResolverTipoTestParte, RotulosBase, TestCase):
    """Nome preservado para os ids deste cenário."""
