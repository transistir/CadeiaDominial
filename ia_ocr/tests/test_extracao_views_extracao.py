"""Fachada de ``ExtracaoViewsTest`` — migração VERBATIM de
``ia_ocr/tests/test_extracao_views.py`` (Etapa 12 do plano de 400 linhas).

O corpo verbatim vive nas 3 partes (classes simples, sem ``TestCase``);
a fachada preserva o nome da classe, o decorator e os ids de teste.
"""

from django.test import override_settings

from .base_texto import TelaTextoBase
from .test_extracao_views_extracao_parte1 import ExtracaoViewsTestParte1
from .test_extracao_views_extracao_parte2 import ExtracaoViewsTestParte2
from .test_extracao_views_extracao_parte3 import ExtracaoViewsTestParte3


@override_settings(EXTRACAO_HTTP_TIMEOUT_SECONDS=30)
class ExtracaoViewsTest(
    ExtracaoViewsTestParte1,
    ExtracaoViewsTestParte2,
    ExtracaoViewsTestParte3,
    TelaTextoBase,
):
    """Nome preservado para os ids de teste; corpo nas partes 1–3."""

