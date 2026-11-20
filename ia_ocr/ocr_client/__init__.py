"""Cliente HTTP de baixo nível para o serviço OCR v1.0.1.

Pacote desde a Etapa 5 do imposto de 400 linhas: o antigo
``ia_ocr/ocr_client.py`` (662 linhas) virou módulos por responsabilidade e
este ``__init__`` reexporta o que os consumidores importam hoje
(``backends.py``, ``extracao_client.py``,
``management/commands/ocr_smoke.py`` e os testes) sem mudança nenhuma.

- ``time`` é o alvo de patch via pacote: ``patch('ia_ocr.ocr_client.time',
  relogio)`` substitui o atributo AQUI, e TODOS os call sites de relógio
  (``_restante`` em ``http.py``, ``_aguardar_backoff`` em ``cliente.py``,
  ``_PrazoAbsoluto`` em ``prazo.py`` e ``_conferir_prazo`` em
  ``multipart.py``) resolvem ``ocr_client.time`` a cada chamada
  (``from .. import ocr_client``) — então o patch alcança o pacote inteiro,
  como alcançava o monólito.
- ``patch('ia_ocr.ocr_client.time.sleep')`` muta o módulo ``time``
  compartilhado e vale para o pacote inteiro.
- ``assertLogs('ia_ocr.ocr_client', ...)`` pega os logs por PROPAGAÇÃO: o
  módulo que loga usa ``getLogger(__name__)``
  (``ia_ocr.ocr_client.http``, filho de ``ia_ocr.ocr_client``).
"""

import time  # alvo de patch: ia_ocr.ocr_client.time (lido via pacote)

from ..backends import OrcamentoEsgotado
from .cliente import OcrServiceClient
from .http import _ClienteHttpComPrazo
from .prazo import (
    _AdaptadorComPrazo,
    _PrazoAbsoluto,
    _PoolHttpComPrazo,
    _PoolHttpsComPrazo,
)

__all__ = [
    'OcrServiceClient',
    'OrcamentoEsgotado',
    'time',
    '_AdaptadorComPrazo',
    '_ClienteHttpComPrazo',
    '_PrazoAbsoluto',
    '_PoolHttpComPrazo',
    '_PoolHttpsComPrazo',
]
