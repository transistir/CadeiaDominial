"""Cliente HTTP de baixo nível para o serviço OCR v1.0.1.

Pacote desde a Etapa 5 do imposto de 400 linhas: o antigo
``ia_ocr/ocr_client.py`` (662 linhas) virou módulos por responsabilidade e
este ``__init__`` reexporta o que os consumidores importam hoje
(``backends.py``, ``extracao_client.py``,
``management/commands/ocr_smoke.py`` e os testes) sem mudança nenhuma.

- ``time`` é o alvo de patch via pacote: ``patch('ia_ocr.ocr_client.time',
  relogio)`` substitui o atributo AQUI, e os call sites de ``_restante`` e
  ``_aguardar_backoff`` resolvem ``ocr_client.time`` a cada chamada
  (``from .. import ocr_client`` em ``http.py``/``cliente.py``) — então o
  patch continua valendo depois do split. Os demais usos de ``time``
  (``multipart``, ``prazo``) ficam com o ``import time`` local do próprio
  módulo.
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
