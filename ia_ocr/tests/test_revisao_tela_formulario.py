"""Contrato de apresentação da tela por ato (I-11a, #321) — migração
VERBATIM de ``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de
400 linhas).

``FormularioPorAtoTest`` tem 613 linhas e não cabe em um arquivo de 400.
O corpo verbatim vive nas 2 partes (classes simples, sem ``TestCase``);
a fachada preserva o nome da classe e os ids de teste.
"""

from .test_revisao_tela_base import TelaRevisaoBase
from .test_revisao_tela_formulario_parte1 import (
    FormularioPorAtoTestParte1,
)
from .test_revisao_tela_formulario_parte2 import (
    FormularioPorAtoTestParte2,
)


class FormularioPorAtoTest(
    FormularioPorAtoTestParte1,
    FormularioPorAtoTestParte2,
    TelaRevisaoBase,
):
    """Nome preservado para os ids de teste; corpo nas partes 1–2."""
