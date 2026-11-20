"""Parser de rótulos de lançamento (I-11b / #322).

Rótulo é o carimbo que abre cada ato na matrícula: ``'R-1'``,
``'Av: 2-237'``, ``'M-3-14511'``. Decisão do cliente (Hiure, 09/11):
lançamento SEMPRE começa com ``R`` (registro) ou ``Av`` (averbação);
``M`` é número de matrícula — rótulo válido, mas nunca um lançamento;
``"R: 1-237"`` traz número de ato ``1`` e matrícula ``237``, e o texto
depois do carimbo (protocolo, data, comarca) é ignorado.

Módulo PURO, sem Django e sem I/O. ``analisar_rotulo`` NUNCA levanta
exceção: entrada vazia, estranha, com prefixo desconhecido ou SEM número
do ato cai em ``reconhecido=False`` com um ``motivo`` — o destino do
bucket de não reconhecidos é decisão da UI (#321). ``classificar_atos``
consome o payload da extração (``document`` + ``acts``) e devolve o
cabeçalho do início de matrícula (que NÃO é um ato), os lançamentos em
ordem REVERSA (maior ``ordem`` primeiro; sem ``ordem`` válida, o índice
do payload + 1 — a mesma regra da revisão) e os não reconhecidos.

Pacote desde a Etapa 8 do imposto de 400 linhas: o antigo
``ia_ocr/rotulos.py`` virou módulos por responsabilidade e este
``__init__`` reexporta tudo que o módulo único tinha no nível de topo.
Módulo PURO, sem alvo de ``patch`` nos testes (``grep "patch.*rotulos"``
vazio) — todos os consumidores podem seguir importando do pacote
(``from ia_ocr.rotulos import analisar_rotulo``) sem mudança nenhuma.
"""

from .analise import (
    _dois_numeros,
    analisar_rotulo,
    resolver_tipo,
    tipo_do_rotulo,
)
from .classificacao import CAMPOS_INICIO_MATRICULA, classificar_atos
from .numeros import (
    _ordem_ordenavel,
    _valor_do_campo,
    compor_numero_lancamento,
    normalizar_numero_lancamento,
)
from .tipos import TIPOS_SUGERIDOS, Classificacao, Rotulo, _nao_reconhecido

__all__ = [
    'CAMPOS_INICIO_MATRICULA',
    'Classificacao',
    'Rotulo',
    'TIPOS_SUGERIDOS',
    '_dois_numeros',
    '_nao_reconhecido',
    '_ordem_ordenavel',
    '_valor_do_campo',
    'analisar_rotulo',
    'classificar_atos',
    'compor_numero_lancamento',
    'normalizar_numero_lancamento',
    'resolver_tipo',
    'tipo_do_rotulo',
]
