"""Desnormalização do payload A3 — fachada da migração VERBATIM de
``ia_ocr/tests/test_revisao.py`` (Etapa 5, grupo 3 do plano de
400 linhas; as 758 linhas da classe não cabem nem em 2 arquivos de
400 com os imports de cada parte). O corpo verbatim vive nas 3
partes (classes simples, sem ``TestCase``); a fachada preserva o
nome da classe e os ids de teste. A parte 1 vem primeiro na MRO
para o setUp dela valer para todas, e a base real (``TestCase``)
vem por último.
"""

from django.test import TestCase

from .test_revisao_desnormalizar_parte1 import DesnormalizarTestParte1
from .test_revisao_desnormalizar_parte2 import DesnormalizarTestParte2
from .test_revisao_desnormalizar_parte3 import DesnormalizarTestParte3


class DesnormalizarTest(
    DesnormalizarTestParte1,
    DesnormalizarTestParte2,
    DesnormalizarTestParte3,
    TestCase,
):
    """Nome preservado para os ids de teste; corpo nas partes."""
