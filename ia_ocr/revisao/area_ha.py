"""Área lida no documento → hectares com 4 casas (#373).

Decisão de produto (Hiure, 21/11/2026): a área é sempre persistida em
**hectares com 4 casas decimais**, arredondando com ``ROUND_HALF_UP`` (não
é o *banker's rounding* do ``Decimal`` padrão).

O parser não procura "o primeiro número": extrai **pares número+unidade**
(``120,00 m²``, ``169 hectares``, ``9 ares``, ``40 ca.``) e só converte
quando a expressão inteira é inequívoca:

- ``m²``/``m2`` → divide por 10.000;
- ``ha``/``ha.``/``hectare(s)`` → valor como está;
- composto ``"<N> hectares, <A> ares e <C> centiares"`` (``ha``/``a``/``ca``)
  → ``N + A/100 + C/10000``; ``A`` e ``C`` só valem de 0 a 99 e, no
  composto, o ponto de ``N`` é milhar (``1.069 hectares`` → 1069);
- ``alqueires`` (falta o fator aprovado), unidade ausente, zero, negativo,
  número fora do par ou dois pares → ``None``.

Número pt-BR estrito: com vírgula o ponto é milhar em grupos de 3 (primeiro
grupo de 1 a 3 dígitos); sem vírgula, ponto agrupando 3 em 3 é **ambíguo**
(milhar ou decimal) e devolve ``None``; mais de um separador do mesmo tipo,
vírgula solta e texto vazio também. Unidade do texto divergente do enum do
A3, ou valor convertido que não bate com o ``normalized`` do A3 (tolerância
``0.00005``; em ``m2`` depois de ÷10.000), devolve ``None``: quem chama trata
como pendência do revisor, nunca como zero. A função não levanta exceção —
dado de OCR é entrada hostil.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, localcontext

CASAS_DECIMAIS = 4
_QUANTUM = Decimal('0.0001')
_MAXIMO = Decimal('99999999.9999')
_M2_POR_HA = Decimal(10000)
_ARES_POR_HA = Decimal(100)
_CENTIARES_POR_HA = Decimal(10000)
_TOLERANCIA = Decimal('0.00005')

# Número pt-BR: começa em dígito, termina em dígito ("1.234,5678", "169").
# ``O``/``l`` nunca entram: dígito é ``\d``, não caractere parecido.
_NUMERO = r'\d(?:[\d.,]*\d)?'
# Unidade não pode ser seguida de letra/dígito ("ha" em "hectares").
_FIM_DA_UNIDADE = r'(?![^\W_])'
_UNIDADE_M2 = r'(?:m²|m2)'
_UNIDADE_HA = r'(?:hectares|hectare|ha\.?)'
_UNIDADE_ARES = r'(?:ares|are|a\.?)'
_UNIDADE_CENTIARES = r'(?:centiares|centiare|ca\.?)'
_UNIDADE_ALQUEIRE = r'(?:alqueires|alqueire)'
_UNIDADE_TODAS = (
    rf'(?:{_UNIDADE_ALQUEIRE}|{_UNIDADE_CENTIARES}|{_UNIDADE_HA}'
    rf'|{_UNIDADE_M2}|{_UNIDADE_ARES})'
)

_SEPARADOR = r'(?:,\s*(?:e\s+)?|\s+e\s+|\s+)'
_COMPOSTO = re.compile(
    rf'(?<![\d.,])(?P<hectares>{_NUMERO})\s*{_UNIDADE_HA}'
    rf'{_FIM_DA_UNIDADE}{_SEPARADOR}'
    rf'(?P<ares>{_NUMERO})\s*{_UNIDADE_ARES}{_FIM_DA_UNIDADE}'
    rf'(?:{_SEPARADOR}'
    rf'(?P<centiares>{_NUMERO})\s*{_UNIDADE_CENTIARES}'
    rf'{_FIM_DA_UNIDADE})?',
    re.IGNORECASE,
)
_PAR = re.compile(
    rf'(?<![\d.,])(?P<numero>{_NUMERO})\s*(?P<unidade>{_UNIDADE_TODAS})'
    rf'{_FIM_DA_UNIDADE}',
    re.IGNORECASE,
)
_UNIDADE_SOLTA = re.compile(
    rf'(?:{_UNIDADE_TODAS}){_FIM_DA_UNIDADE}', re.IGNORECASE,
)
_UNIDADE_LONGA = re.compile(
    r'hectares?|alqueires?|centiares?|ares', re.IGNORECASE,
)
_ALQUEIRE = re.compile(r'alqueire', re.IGNORECASE)
_DIGITO = re.compile(r'\d')
_MENOS = re.compile(r'[-−]')

_UNIDADES_DO_ENUM = {
    'ha': 'ha', 'hectare': 'ha', 'hectares': 'ha',
    'm2': 'm2', 'm²': 'm2',
    'are': 'ares', 'ares': 'ares',
    'centiare': 'centiares', 'centiares': 'centiares',
    'alqueire': 'alqueires', 'alqueires': 'alqueires',
}


def converter_para_hectares(raw, unidade, normalizado=None):
    """Converte a área lida para ``Decimal`` em ha (4 casas), ou ``None``.

    ``raw`` é o texto do documento, ``unidade`` o enum do A3
    (``'ha'``/``'m2'``/``'alqueires'``/``None``...) e ``normalizado`` o
    ``normalized`` numérico do A3, quando houver: o valor convertido precisa
    bater com ele. Devolve ``None`` sempre que a conversão não é inequívoca —
    o chamador marca a pendência e deixa o revisor decidir. Nunca levanta
    exceção.
    """
    try:
        return _converter(raw, unidade, normalizado)
    except (ArithmeticError, TypeError, ValueError):
        return None


def unidade_do_texto(raw):
    """Código da unidade lida (``ha``/``m2``/``ares``/``centiares``/
    ``alqueires``) ou ``None``.

    Serve ao chamador para detectar divergência entre o texto e o enum do
    A3 mesmo quando o valor do A3 já está em hectares.
    """
    if not isinstance(raw, str):
        return None
    texto = raw.strip()
    if not texto:
        return None
    par = _PAR.search(texto)
    if par is not None:
        return _codigo_da_unidade(par.group('unidade'))
    achado = _UNIDADE_SOLTA.search(texto)
    return _codigo_da_unidade(achado.group(0)) if achado else None


def unidades_divergem(raw, unidade):
    """O texto e o enum do A3 trazem unidades incompatíveis?"""
    do_texto = unidade_do_texto(raw)
    do_enum = _unidade_do_enum(unidade)
    return (
        do_texto is not None
        and do_enum is not None
        and do_texto != do_enum
    )


def quantizar_hectares(valor):
    """Valor do A3 em hectares → texto com no máximo 4 casas, ou ``None``.

    Só reescreve quando o valor tem mais de 4 casas (o campo do formulário
    recusa o excedente, sem pendência que explique); o que já cabe volta
    como veio.
    """
    try:
        numero = _decimal_do_normalizado(valor)
        if numero is None:
            return None
        expoente = numero.as_tuple().exponent
        if isinstance(expoente, int) and expoente >= -CASAS_DECIMAIS:
            return valor if isinstance(valor, str) else format(numero, 'f')
        with localcontext() as contexto:
            contexto.prec = 50
            quantizado = numero.quantize(_QUANTUM, rounding=ROUND_HALF_UP)
        return f'{quantizado:.4f}'
    except (ArithmeticError, TypeError, ValueError):
        return None


def _converter(raw, unidade, normalizado):
    if not isinstance(raw, str):
        return None
    texto = raw.strip()
    if not texto:
        return None
    codigo = _unidade_do_enum(unidade)
    if codigo == 'alqueires' or _ALQUEIRE.search(texto):
        # Sem fator aprovado: converter seria inventar unidade.
        return None
    with localcontext() as contexto:
        contexto.prec = 50
        composto = _COMPOSTO.search(texto)
        if composto is not None:
            return _hectares_do_composto(
                texto, composto, codigo, normalizado,
            )
        pares = list(_PAR.finditer(texto))
        if len(pares) != 1:
            # Nenhum par ou mais de um (duas unidades diferentes): ambíguo.
            return None
        return _hectares_do_par(texto, pares[0], codigo, normalizado)


def _hectares_do_composto(texto, composto, codigo, normalizado):
    """``N hectares, A ares e C centiares`` → hectares."""
    if codigo not in (None, 'ha'):
        return None
    hectares = _numero_composto(composto.group('hectares'))
    ares = _numero(composto.group('ares'))
    texto_centiares = composto.group('centiares')
    centiares = _numero(texto_centiares) if texto_centiares else Decimal(0)
    if hectares is None or ares is None or centiares is None:
        return None
    if not (0 <= ares <= 99 and 0 <= centiares <= 99):
        return None
    if _sobra_unidade(texto, composto) or _tem_menos(texto, composto.end()):
        return None
    valor = (
        hectares
        + ares / _ARES_POR_HA
        + centiares / _CENTIARES_POR_HA
    )
    if not _bate_com_normalizado(normalizado, valor, 'ha'):
        return None
    return _normalizar(valor)


def _hectares_do_par(texto, par, codigo, normalizado):
    """Par único ``N ha``/``N m²`` → hectares; ares/centiares/alqueires → None."""
    if _tem_menos(texto, par.end()) or _sobra_unidade(texto, par):
        return None
    numero = _numero(par.group('numero'))
    if numero is None:
        return None
    do_texto = _codigo_da_unidade(par.group('unidade'))
    if do_texto not in ('ha', 'm2'):
        return None
    if codigo is not None and codigo != do_texto:
        return None
    valor = numero / _M2_POR_HA if do_texto == 'm2' else numero
    if not _bate_com_normalizado(normalizado, valor, do_texto):
        return None
    return _normalizar(valor)


def _sobra_unidade(texto, achado):
    """Fora do par/composto: outro número ou outra unidade → ambíguo."""
    resto = texto[:achado.start()] + texto[achado.end():]
    return bool(_DIGITO.search(resto)) or bool(_UNIDADE_LONGA.search(resto))


def _tem_menos(texto, fim):
    """``-``/``−`` no trecho numérico ou antes dele → sinal, nunca absoluto."""
    return bool(_MENOS.search(texto[:fim]))


def _bate_com_normalizado(normalizado, valor, codigo):
    """Sem ``normalized`` numérico não há confronto; divergência → não bate."""
    esperado = _decimal_do_normalizado(normalizado)
    if esperado is None:
        return True
    if codigo == 'm2':
        esperado = esperado / _M2_POR_HA
    return abs(esperado - valor) <= _TOLERANCIA


def _codigo_da_unidade(texto):
    chave = texto.strip().rstrip('.').lower()
    if chave in ('m2', 'm²'):
        return 'm2'
    if chave in ('ha', 'hectare', 'hectares'):
        return 'ha'
    if chave in ('a', 'are', 'ares'):
        return 'ares'
    if chave in ('ca', 'centiare', 'centiares'):
        return 'centiares'
    if chave in ('alqueire', 'alqueires'):
        return 'alqueires'
    return None


def _unidade_do_enum(unidade):
    if not isinstance(unidade, str):
        return None
    codigo = unidade.strip().lower()
    if not codigo:
        return None
    return _UNIDADES_DO_ENUM.get(codigo, codigo)


def _numero_composto(texto):
    """Hectares do composto: ponto é milhar; vírgula é decimal."""
    if ',' in texto:
        return _numero(texto)
    if '.' in texto:
        grupos = texto.split('.')
        if not 1 <= len(grupos[0]) <= 3:
            return None
        if any(len(grupo) != 3 for grupo in grupos[1:]):
            return None
        return Decimal(''.join(grupos))
    return Decimal(texto) if texto.isdigit() else None


def _numero(texto):
    """Número pt-BR → ``Decimal``; formato ambíguo/inválido → ``None``.

    Com vírgula, o ponto é separador de milhar e precisa agrupar de 3 em 3,
    com o primeiro grupo de 1 a 3 dígitos (``"12.345,67"``). Sem vírgula,
    ponto agrupando 3 em 3 (``"1.234"``) é ambíguo — milhar ou decimal —
    e devolve ``None``; ponto com outra quantidade de casas é decimal.
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
        if not inteira or not fracionaria or not fracionaria.isdigit():
            return None
        if '.' in inteira:
            grupos = inteira.split('.')
            if not 1 <= len(grupos[0]) <= 3:
                return None
            if any(len(grupo) != 3 for grupo in grupos[1:]):
                return None
            inteira = ''.join(grupos)
        if not inteira.isdigit():
            return None
        canonico = f'{inteira}.{fracionaria}'
    elif '.' in texto:
        if texto.count('.') != 1:
            return None
        inteira, _, fracionaria = texto.partition('.')
        if not inteira.isdigit() or not fracionaria.isdigit():
            return None
        if len(fracionaria) == 3 and len(inteira) <= 3:
            return None
        canonico = texto
    else:
        if not texto.isdigit():
            return None
        canonico = texto
    try:
        numero = Decimal(canonico)
    except ArithmeticError:
        return None
    return numero if numero.is_finite() else None


def _decimal_do_normalizado(valor):
    """``normalized`` do A3 → ``Decimal``; não numérico/ausente → ``None``."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, Decimal):
        numero = valor
    elif isinstance(valor, (int, float)):
        numero = Decimal(str(valor))
    elif isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return None
        try:
            numero = Decimal(texto)
        except ArithmeticError:
            return None
    else:
        return None
    return numero if numero.is_finite() else None


def _normalizar(numero):
    """4 casas, ``ROUND_HALF_UP``; zero/negativo/fora do campo → ``None``."""
    if numero is None or not numero.is_finite():
        return None
    hectare = numero.quantize(_QUANTUM, rounding=ROUND_HALF_UP)
    if hectare <= 0 or hectare > _MAXIMO:
        return None
    return hectare
