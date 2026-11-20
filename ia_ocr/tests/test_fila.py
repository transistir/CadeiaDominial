"""Fachadas dos testes da fila OCR (Etapa 13, limite de 400 linhas).

Os cenários estão em mixins simples, mas estas classes preservam os módulos,
nomes e IDs históricos. ``TestCase`` fica por último para que o ``setUp`` da
parte vença na MRO. Os backends são reexportados porque ``override_settings``
os resolve por ``ia_ocr.tests.test_fila.<Backend>``.
"""

from django.test import TestCase

from .test_fila_base import (
    BackendDatabaseError as BackendDatabaseError,
    BackendErroForaDoContrato as BackendErroForaDoContrato,
    BackendErroGenerico as BackendErroGenerico,
    BackendFalhaContratual as BackendFalhaContratual,
    BackendOrigemInvalida as BackendOrigemInvalida,
    BackendOrigemTextoEmbutido as BackendOrigemTextoEmbutido,
    BackendSemOrigem as BackendSemOrigem,
    BackendSucesso as BackendSucesso,
    BackendTimingsSuspeitos as BackendTimingsSuspeitos,
    BackendVazaPii as BackendVazaPii,
)
from .test_fila_cadencia import CadenciaReapCommandTestParte
from .test_fila_claim import ClaimProximoJobTestParte
from .test_fila_comando_parte1 import ComandoProcessOcrQueueTestParte1
from .test_fila_comando_parte2 import ComandoProcessOcrQueueTestParte2
from .test_fila_finalizacao import FinalizacaoTardiaTestParte
from .test_fila_reap import ReapJobsExpiradosTestParte
from .test_fila_reprocessar import ReprocessarTestParte
from .test_fila_validacao import ValidacaoResultadoOcrTestParte


class CadenciaReapCommandTest(CadenciaReapCommandTestParte, TestCase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class ClaimProximoJobTest(ClaimProximoJobTestParte, TestCase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class ComandoProcessOcrQueueTest(
    ComandoProcessOcrQueueTestParte1, ComandoProcessOcrQueueTestParte2,
    TestCase,
):
    """Fachada com o ID histórico; corpo nas partes 1–2."""


class FinalizacaoTardiaTest(FinalizacaoTardiaTestParte, TestCase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class ReapJobsExpiradosTest(ReapJobsExpiradosTestParte, TestCase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class ReprocessarTest(ReprocessarTestParte, TestCase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class ValidacaoResultadoOcrTest(ValidacaoResultadoOcrTestParte, TestCase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""
