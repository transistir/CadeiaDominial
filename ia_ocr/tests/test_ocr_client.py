"""Fachadas dos testes de ``ocr_client`` (Etapa 13, limite de 400 linhas).

Cada cenário mantém o módulo, a classe e os IDs históricos. Os corpos estão
em mixins simples nos arquivos por cenário; ``SimpleTestCase`` fica por último
na MRO, para que o ``setUp`` da parte prevaleça quando houver um.
"""

from django.test import SimpleTestCase

from .test_ocr_client_adaptador import AdaptadorComPrazoProxyTestsParte
from .test_ocr_client_log import LogDeCabecalhosTestsParte
from .test_ocr_client_parte1 import OcrServiceClientTestsParte1
from .test_ocr_client_parte2 import OcrServiceClientTestsParte2
from .test_ocr_client_prazo import PrazoAbsolutoTestsParte
from .test_ocr_client_tls import PrazoAbsolutoTlsTestsParte


class AdaptadorComPrazoProxyTests(
    AdaptadorComPrazoProxyTestsParte, SimpleTestCase
):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class LogDeCabecalhosTests(LogDeCabecalhosTestsParte, SimpleTestCase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class OcrServiceClientTests(
    OcrServiceClientTestsParte1, OcrServiceClientTestsParte2, SimpleTestCase
):
    """Fachada com o ID histórico; corpo nas partes 1–2."""


class PrazoAbsolutoTests(PrazoAbsolutoTestsParte, SimpleTestCase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class PrazoAbsolutoTlsTests(PrazoAbsolutoTlsTestsParte, SimpleTestCase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""
