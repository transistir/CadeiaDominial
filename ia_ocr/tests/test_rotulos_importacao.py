"""Fachada de testes da integração rótulos → importação OCR.

Os corpos de ``RotulosImportacaoTest`` vivem nas partes para manter este
módulo abaixo do limite de 400 linhas. Os nomes e ids dos testes são
preservados. A parte 3 (decisão do tipo no card + importação em lote)
saiu com o motor, aposentado na fase 4 da #341.
"""

from django.test import TestCase

from .test_importacao_base import ImportacaoFixture
from .test_rotulos_importacao_parte1 import RotulosImportacaoTestParte1
from .test_rotulos_importacao_parte2 import RotulosImportacaoTestParte2


class RotulosImportacaoTest(
    RotulosImportacaoTestParte1,
    RotulosImportacaoTestParte2,
    ImportacaoFixture,
    TestCase,
):
    """Nome preservado para os ids de teste; corpo nas partes."""
