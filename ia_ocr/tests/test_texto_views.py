"""Fachada dos cenários da tela de confirmação de texto OCR."""

from .base_texto import TelaTextoBase
from .test_texto_views_permissao_render import (
    PermissaoTelaTextoTestParte,
    RenderTelaTextoTestParte,
)
from .test_texto_views_contrato_html_js import (
    ContratoHtmlJsTestParte,
)
from .test_texto_views_confirmar_autoextrair import (
    ConfirmarPaginaViewTestParte,
    AutoExtrairTelaTextoTestParte,
    AutoExtrairCliqueManualTestParte,
)


class PermissaoTelaTextoTest(PermissaoTelaTextoTestParte, TelaTextoBase):
    """Nome preservado para os ids deste cenário."""


class RenderTelaTextoTest(RenderTelaTextoTestParte, TelaTextoBase):
    """Nome preservado para os ids deste cenário."""


class ContratoHtmlJsTest(ContratoHtmlJsTestParte, TelaTextoBase):
    """Nome preservado para os ids deste cenário."""


class ConfirmarPaginaViewTest(ConfirmarPaginaViewTestParte, TelaTextoBase):
    """Nome preservado para os ids deste cenário."""


class AutoExtrairTelaTextoTest(AutoExtrairTelaTextoTestParte, TelaTextoBase):
    """Nome preservado para os ids deste cenário."""


class AutoExtrairCliqueManualTest(AutoExtrairCliqueManualTestParte, TelaTextoBase):
    """Nome preservado para os ids deste cenário."""
