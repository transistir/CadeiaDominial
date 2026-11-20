"""Pendências e avisos da revisão — fachada da migração VERBATIM de
``ia_ocr/tests/test_revisao.py`` (Etapa 5, grupo 3 do plano de
400 linhas). O corpo verbatim vive nas 3 partes (classes simples,
sem ``TestCase``); a fachada preserva o nome da classe e os ids de
teste. A parte 1 vem primeiro na MRO para o setUp dela valer para
todas, e a base real (``TestCase``) vem por último.
"""

from django.test import TestCase

from .test_revisao_pendencias_parte1 import PendenciasEAvisosTestParte1
from .test_revisao_pendencias_parte2 import PendenciasEAvisosTestParte2
from .test_revisao_pendencias_parte3 import PendenciasEAvisosTestParte3


class PendenciasEAvisosTest(
    PendenciasEAvisosTestParte1,
    PendenciasEAvisosTestParte2,
    PendenciasEAvisosTestParte3,
    TestCase,
):
    """Nome preservado para os ids de teste; corpo nas partes."""
