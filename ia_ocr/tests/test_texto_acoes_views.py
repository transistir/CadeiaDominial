"""Fachada das ações da tela de confirmação do texto OCR (Etapa 16)."""

from .base_texto import TelaTextoBase
from .test_texto_acoes_views_base import _botao
from .test_texto_acoes_views_extracao import (
    CamposPendenteViewTestParte,
    ExtrairCamposViewTestParte,
)
from .test_texto_acoes_views_gerais import (
    ConfirmarTodasViewTestParte,
    PermissaoAcoesGeraisTestParte,
    ReprocessarViewTestParte,
)

__all__ = ['_botao']


class PermissaoAcoesGeraisTest(PermissaoAcoesGeraisTestParte, TelaTextoBase):
    """Fachada com o ID histórico."""


class ConfirmarTodasViewTest(ConfirmarTodasViewTestParte, TelaTextoBase):
    """Fachada com o ID histórico."""


class ReprocessarViewTest(ReprocessarViewTestParte, TelaTextoBase):
    """Fachada com o ID histórico."""


class ExtrairCamposViewTest(ExtrairCamposViewTestParte, TelaTextoBase):
    """Fachada com o ID histórico."""


class CamposPendenteViewTest(CamposPendenteViewTestParte, TelaTextoBase):
    """Fachada com o ID histórico."""
