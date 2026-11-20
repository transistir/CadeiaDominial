"""Fachadas dos testes de prefill do formulário (Etapa 13).

Os corpos dos cenários estão em mixins simples por responsabilidade. Estas
fachadas preservam os nomes e IDs históricos. ``PrefillBase`` mantém
``ImportacaoFixture`` e ``TestCase``; ele vem por último na MRO, para que o
``setUp`` de uma parte prevaleça caso o cenário passe a defini-lo.
"""

from .test_revisao_formulario_prefill_area_outra_unidade import (
    AreaEmOutraUnidadeTestParte,
)
from .test_revisao_formulario_prefill_base import PrefillBase
from .test_revisao_formulario_prefill_contrato import ContratoDaFuncaoTestParte
from .test_revisao_formulario_prefill_evidencia import EvidenciaTestParte
from .test_revisao_formulario_prefill_forma_titulo import FormaETituloTestParte
from .test_revisao_formulario_prefill_origem import OrigemTestParte
from .test_revisao_formulario_prefill_partes import PartesTestParte
from .test_revisao_formulario_prefill_sem_lugar import SemLugarNoFormularioTestParte
from .test_revisao_formulario_prefill_tipo_numero import TipoENumeroTestParte
from .test_revisao_formulario_prefill_transmissao_textos import (
    TransmissaoETextosTestParte,
)


class AreaEmOutraUnidadeTest(AreaEmOutraUnidadeTestParte, PrefillBase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class ContratoDaFuncaoTest(ContratoDaFuncaoTestParte, PrefillBase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class EvidenciaTest(EvidenciaTestParte, PrefillBase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class FormaETituloTest(FormaETituloTestParte, PrefillBase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class OrigemTest(OrigemTestParte, PrefillBase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class PartesTest(PartesTestParte, PrefillBase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class SemLugarNoFormularioTest(SemLugarNoFormularioTestParte, PrefillBase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class TipoENumeroTest(TipoENumeroTestParte, PrefillBase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""


class TransmissaoETextosTest(TransmissaoETextosTestParte, PrefillBase):
    """Fachada com o ID histórico; corpo no mixin do cenário."""
