"""Tela de revisão de campos (I-5): render, escape, pendências e somente
leitura — migração VERBATIM de ``ia_ocr/tests/test_revisao_tela.py``
(Etapa 10 do plano de 400 linhas).

``RevisaoTelaTest`` tem 1.056 linhas e não cabe em um arquivo de 400.
O corpo verbatim vive nas 3 partes (classes simples, sem ``TestCase``);
a fachada preserva o nome da classe e os ids de teste. As partes vêm
ANTES de ``TelaRevisaoBase`` na MRO para o setUp da base valer para
todas.
"""

from .test_revisao_tela_base import TelaRevisaoBase
from .test_revisao_tela_navegacao_parte1 import (
    RevisaoTelaTestParte1,
)
from .test_revisao_tela_navegacao_parte2 import (
    RevisaoTelaTestParte2,
)
from .test_revisao_tela_navegacao_parte3 import (
    RevisaoTelaTestParte3,
)


class RevisaoTelaTest(
    RevisaoTelaTestParte1,
    RevisaoTelaTestParte2,
    RevisaoTelaTestParte3,
    TelaRevisaoBase,
):
    """Nome preservado para os ids de teste; corpo nas partes 1–3."""
