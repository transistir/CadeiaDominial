"""Helpers de gravação compartilhados entre a importação e a revisão.

O motor em lote (``importar``, ``resumo``, ``_atos_marcados``,
``_importar_ato`` e o savepoint por ato — I-6/#263) foi aposentado na
fase 4 da #341 junto com a tela de cards: a gravação agora é um ato por
vez, pela revisão no formulário (``revisao_ato.salvar_ato``). Ficam as
peças que o caminho novo TAMBÉM usa:

- resolução de tipo/número a partir do rótulo (``ato_documento``);
- leitura de linhas e rótulo efetivo (``resposta``);
- vínculos de auditoria e marcação de linhas importadas
  (``orquestracao``).

#
# Pacote desde a Etapa 2 do imposto de 400 linhas: o antigo
# ``ia_ocr/importacao.py`` virou módulos por responsabilidade e este
# ``__init__`` reexporta os nomes no nível de topo — os consumidores
# seguem fazendo ``from ia_ocr import importacao`` e
# ``from ia_ocr.importacao import X`` sem mudança nenhuma.
#
# Os call sites dos nomes que os testes fazem ``patch.object`` no pacote
# resolvem o nome AQUI (``from .. import importacao`` no submódulo),
# então o patch continua valendo depois do split.
"""

from .ato_documento import (
    PREFIXO_TIPO_DOCUMENTO,
    _NUMERO_SIMPLES,
    _numero_de_ato_do_campo,
    _resolver_tipo_e_numero,
    _tipo_documento_da_origem,
)
from .orquestracao import (
    _marcar_importadas,
    _vincular,
)
from .resposta import (
    _linhas_por_chave,
    _rotulo_efetivo,
)

__all__ = [
    'PREFIXO_TIPO_DOCUMENTO',
    '_NUMERO_SIMPLES',
    '_linhas_por_chave',
    '_marcar_importadas',
    '_numero_de_ato_do_campo',
    '_resolver_tipo_e_numero',
    '_rotulo_efetivo',
    '_tipo_documento_da_origem',
    '_vincular',
]
