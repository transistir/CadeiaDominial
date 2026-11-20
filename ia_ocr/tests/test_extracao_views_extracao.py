"""Fachada de ``ExtracaoViewsTest`` — migração VERBATIM de
``ia_ocr/tests/test_extracao_views.py`` (Etapa 12 do plano de 400 linhas).

O corpo verbatim vive nas partes (classes simples, sem ``TestCase``);
a fachada preserva o nome da classe, o decorator e os ids de teste.
A parte 2 (endpoint ``salvar_bloco_ocr``) saiu com a rota, aposentada
na fase 4 da #341.
"""

from django.test import override_settings

from .base_texto import TelaTextoBase
from .test_extracao_views_extracao_parte1 import ExtracaoViewsTestParte1
from .test_extracao_views_extracao_parte3 import ExtracaoViewsTestParte3


@override_settings(EXTRACAO_HTTP_TIMEOUT_SECONDS=30)
class ExtracaoViewsTest(
    ExtracaoViewsTestParte1,
    ExtracaoViewsTestParte3,
    TelaTextoBase,
):
    """Nome preservado para os ids de teste; corpo nas partes 1 e 3."""
