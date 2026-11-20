"""Fachada dos testes do comando de evidência ocr_smoke (Etapa 16)."""

from django.test import TestCase

from .test_ocr_smoke_base import TEXTO_MARCADOR

__all__ = ['TEXTO_MARCADOR']

from .test_ocr_smoke_documento_digital import OcrSmokeDocumentoDigitalTestsParte
from .test_ocr_smoke_pdf import OcrSmokePdfTestsParte


class OcrSmokePdfTests(OcrSmokePdfTestsParte, TestCase):
    """Fachada com o ID histórico."""


class OcrSmokeDocumentoDigitalTests(OcrSmokeDocumentoDigitalTestsParte, TestCase):
    """Fachada com o ID histórico."""
