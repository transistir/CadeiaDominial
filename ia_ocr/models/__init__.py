"""Modelos do app ia_ocr, divididos em módulos ≤400 linhas (Etapa 6).

``ia_ocr.models`` continua sendo a superfície pública: importe sempre do
pacote (``from ia_ocr.models import OcrJob``), nunca de um submódulo.
"""
from .job import (
    ESTADO_CONFIRMADA,
    ESTADO_EDITADA,
    ESTADO_NAO_CONFIRMADA,
    ESTADO_PAGINA_ROTULOS,
    ORIGEM_CHOICES,
    OcrJob,
    OcrJobTransicao,
    PaginaOcr,
)
from .extracao import (
    STATUS_REVISAO_CHOICES,
    TIPO_VALOR_CHOICES,
    CampoSugerido,
    ExtracaoSugerida,
)
from .registro import ImportacaoIA, PendenciaLimpezaArquivo

__all__ = [
    'CampoSugerido',
    'ESTADO_CONFIRMADA',
    'ESTADO_EDITADA',
    'ESTADO_NAO_CONFIRMADA',
    'ESTADO_PAGINA_ROTULOS',
    'ExtracaoSugerida',
    'ImportacaoIA',
    'OcrJob',
    'OcrJobTransicao',
    'ORIGEM_CHOICES',
    'PaginaOcr',
    'PendenciaLimpezaArquivo',
    'STATUS_REVISAO_CHOICES',
    'TIPO_VALOR_CHOICES',
]
