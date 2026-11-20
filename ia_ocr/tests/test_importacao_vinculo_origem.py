"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.

``VinculoDocumentoOrigemTest`` tem 816 linhas e não cabe em um arquivo
de 400. O corpo verbatim vive nas 3 partes (classes simples, sem
``TestCase``); a fachada preserva o nome da classe e os ids de teste.
As partes vêm ANTES de ``ImportacaoBase`` para o ``setUp`` da parte
vencer o no-op herdado de ``TestCase``.
"""


from .test_importacao_base import ImportacaoBase
from .test_importacao_vinculo_origem_parte1 import (
    VinculoDocumentoOrigemParte1,
)
from .test_importacao_vinculo_origem_parte2 import (
    VinculoDocumentoOrigemParte2,
)
from .test_importacao_vinculo_origem_parte3 import (
    VinculoDocumentoOrigemParte3,
)


class VinculoDocumentoOrigemTest(
    VinculoDocumentoOrigemParte1,
    VinculoDocumentoOrigemParte2,
    VinculoDocumentoOrigemParte3,
    ImportacaoBase,
):
    """#324 (I-11d): a importação grava ``Lancamento.documento_origem``.

    Só a importação assistida grava essa FK (o fluxo manual segue como
    está). O documento só é CRIADO pela regra anti-órfão (início de
    matrícula); nos demais tipos o vínculo vale quando a identidade
    (tipo + número + cartório) já existe NO ESCOPO do usuário.
    """
