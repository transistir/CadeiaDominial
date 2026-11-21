"""Área lida no documento → hectares com 4 casas (#373).

Decisão de produto (Hiure, 21/11/2026): a área é sempre persistida em
**hectares com 4 casas decimais**, arredondando com ``ROUND_HALF_UP`` (não
é o *banker's rounding* do ``Decimal`` padrão). A unidade explícita no
texto autoriza a conversão:

- ``m²``/``m2`` → divide por 10.000;
- ``ha``/``hectare(s)`` → valor como está;
- composto ``"<N> hectares, <A> ares e <C> centiares"`` (também ``ha, a e
  ca``) → ``N + A/100 + C/10000`` — é o formato do caso real M237.

Sem unidade explícita e sem o padrão composto **não há conversão**:
``alqueires`` (falta o fator aprovado), unidade ausente, zero, negativo e
texto não numérico devolvem ``None``. Quem chama trata ``None`` como
pendência para o revisor, nunca como zero. A função não levanta exceção:
dado de OCR é entrada hostil.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, localcontext

CASAS_DECIMAIS = 4
_QUANTUM = Decimal('0.0001')
_M2_POR_HA = Decimal(10000)
_ARES_POR_HA = Decimal(100)
_CENTIARES_POR_HA = Decimal(10000)

_UNIDADES_M2 = frozenset({'m2', 'm²'})
_UNIDADES_HA = frozenset({'ha', 'hectare', 'hectares'})
_UNIDADES_ALQUEIRE = frozenset({'alqueire', 'alqueires'})

# Número pt-BR: "1.234,5678", "1234,5678", "12.345,67", "169".
_NUM = r'\d+(?:[.,]\d+)*'
_COMPOSTO = re.compile(
    rf'\b(?P<hectares>{_NUM})\s*(?:hectares?|ha)\b'
    rf'\s*(?:,\s*|e\s+|\s+)'
    rf'(?P<ares>{_NUM})\s*(?:ares?|a)\b'
    rf'(?:\s*(?:,\s*|e\s+|\s+)'
    rf'(?P<centiares>{_NUM})\s*(?:centiares?|ca)\b)?',
    re.IGNORECASE,
)
_SUFIXO_HA = re.compile(r'\b(?:ha|hectares?)\b', re.IGNORECASE)
_INICIO_NUMERO = re.compile(rf'(?<![\d.,])(?P<numero>{_NUM})')
_NEGATIVO = re.compile(r'\s*-\s*\d')


def converter_para_hectares(raw, unidade):
    """Converte a área lida para ``Decimal`` em ha (4 casas), ou ``None``.

    ``raw`` é o texto do documento e ``unidade`` o enum do A3
    (``'ha'``/``'m2'``/``'alqueires'``/``None``...). Devolve ``None`` sempre
    que a conversão não é inequívoca — o chamador marca a pendência e deixa
    o revisor decidir. Nunca levanta exceção.
    """
    try:
        return _converter(raw, unidade)
    except (ArithmeticError, TypeError, ValueError):
        return None


def _converter(raw, unidade):
    if not isinstance(raw, str):
        return None
    texto = raw.strip()
    if not texto:
        return None
    codigo = _unidade_normalizada(unidade)
    if codigo in _UNIDADES_ALQUEIRE or 'alqueire' in texto.lower():
        # Sem fator aprovado: converter seria inventar unidade.
        return None
    if codigo is None or codigo in _UNIDADES_HA:
        composto = _composto(texto)
        if composto is not None:
            return composto
        if codigo is None and not _SUFIXO_HA.search(texto):
            return None
        return _normalizar(_numero_inicial(texto))
    if codigo in _UNIDADES_M2:
        numero = _numero_inicial(texto)
        if numero is None:
            return None
        return _normalizar(numero / _M2_POR_HA)
    return None


def _unidade_normalizada(unidade):
    if not isinstance(unidade, str):
        return None
    return unidade.strip().lower() or None


def _composto(texto):
    """``N ha + A ares + C centiares`` do texto, ou ``None``."""
    achado = _COMPOSTO.search(texto)
    if achado is None:
        return None
    hectares = _numero(achado.group('hectares'))
    ares = _numero(achado.group('ares'))
    centiares_texto = achado.group('centiares')
    centiares = _numero(centiares_texto) if centiares_texto else Decimal(0)
    if hectares is None or ares is None or centiares is None:
        return None
    return _normalizar(
        hectares + ares / _ARES_POR_HA + centiares / _CENTIARES_POR_HA
    )


def _numero_inicial(texto):
    """Primeiro número do texto (o ``raw`` pode vir com prefixo descritivo)."""
    if _NEGATIVO.match(texto):
        return None
    achado = _INICIO_NUMERO.search(texto)
    return _numero(achado.group('numero')) if achado else None


def _numero(texto):
    """Número pt-BR → ``Decimal``; formato ambíguo/inválido → ``None``.

    Com vírgula, o ponto é separador de milhar e precisa agrupar de 3 em 3
    (``"12.345,67"``). Ponto sozinho é separador decimal (``"12.5"``): o
    formato de milhar sem decimais é ambíguo e seria um erro de 1000×.
    """
    if not isinstance(texto, str):
        return None
    texto = texto.strip()
    if not texto:
        return None
    if ',' in texto:
        if texto.count(',') != 1:
            return None
        inteira, _, fracionaria = texto.partition(',')
        if not inteira or not fracionaria:
            return None
        if '.' in inteira:
            grupos = inteira.split('.')
            if not grupos[0] or any(
                len(grupo) != 3 for grupo in grupos[1:]
            ):
                return None
            inteira = ''.join(grupos)
        canonico = f'{inteira}.{fracionaria}'
    elif '.' in texto:
        if texto.count('.') != 1:
            return None
        canonico = texto
    else:
        canonico = texto
    try:
        numero = Decimal(canonico)
    except ArithmeticError:
        return None
    return numero if numero.is_finite() else None


def _normalizar(numero):
    """4 casas, ``ROUND_HALF_UP``; zero/negativo/não finito → ``None``."""
    if numero is None:
        return None
    with localcontext() as contexto:
        contexto.prec = 50
        hectare = numero.quantize(_QUANTUM, rounding=ROUND_HALF_UP)
    if not hectare.is_finite() or hectare <= 0:
        return None
    return hectare
