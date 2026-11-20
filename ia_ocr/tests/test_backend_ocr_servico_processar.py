"""Fachada de ``OcrServiceBackendTests`` — migração VERBATIM de
``ia_ocr/tests/test_backend_ocr_servico.py`` (Etapa 12 do plano de 400 linhas).

O corpo verbatim vive nas 3 partes (classes simples, sem ``TestCase``) e
os helpers no ``_base``; a fachada preserva o nome da classe e os ids.
"""

from django.test import TestCase

from .test_backend_ocr_servico_base import OcrServiceBackendBase
from .test_backend_ocr_servico_processar_parte1 import (
    OcrServiceBackendTestsParte1,
)
from .test_backend_ocr_servico_processar_parte2 import (
    OcrServiceBackendTestsParte2,
)
from .test_backend_ocr_servico_processar_parte3 import (
    OcrServiceBackendTestsParte3,
)


class OcrServiceBackendTests(
    OcrServiceBackendTestsParte1,
    OcrServiceBackendTestsParte2,
    OcrServiceBackendTestsParte3,
    OcrServiceBackendBase,
    TestCase,
):
    """Nome preservado para os ids de teste; corpo nas partes 1–3."""

