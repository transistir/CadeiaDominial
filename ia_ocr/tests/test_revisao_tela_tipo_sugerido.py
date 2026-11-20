"""Card do tipo sugerido como <select> (Tarefa B, #322/PR #327) — migração
VERBATIM de ``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de
400 linhas).

``TipoSugeridoSelectTest`` tem 410 linhas e não cabe em um arquivo de
400. O corpo verbatim vive nas 2 partes (classes simples, sem
``TestCase``); a fachada preserva o nome da classe e os ids de teste.
"""

from .test_revisao_tela_base import TelaRevisaoBase
from .test_revisao_tela_tipo_sugerido_parte1 import (
    TipoSugeridoSelectTestParte1,
)
from .test_revisao_tela_tipo_sugerido_parte2 import (
    TipoSugeridoSelectTestParte2,
)


class TipoSugeridoSelectTest(
    TipoSugeridoSelectTestParte1,
    TipoSugeridoSelectTestParte2,
    TelaRevisaoBase,
):
    """Nome preservado para os ids de teste; corpo nas partes 1–2."""
