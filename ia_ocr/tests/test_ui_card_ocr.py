"""Fachada dos testes da UI do card OCR (Etapa 16, limite de 400 linhas)."""

from .test_ui_card_ocr_base import (
    CardOcrUploadBase,
    _atributos,
    _elementos,
    _texto,
    _texto_de_estilos,
)
from .test_ui_card_ocr_parte1 import CardOcrUploadTestCaseParte1
from .test_ui_card_ocr_parte2 import CardOcrUploadTestCaseParte2

__all__ = ['_atributos', '_elementos', '_texto', '_texto_de_estilos']


class CardOcrUploadTestCase(
    CardOcrUploadTestCaseParte1, CardOcrUploadTestCaseParte2, CardOcrUploadBase
):
    """Fachada com o ID histórico; corpos nas duas partes."""
