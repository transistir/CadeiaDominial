"""Área lida no documento → hectares com 4 casas (#373).

Decisão de produto (Hiure, 21/11/2026): a área é sempre persistida em
**hectares com 4 casas decimais**, arredondando com ``ROUND_HALF_UP`` (não
é o *banker's rounding* do ``Decimal`` padrão).

O parser não procura "o primeiro número": extrai **pares número+unidade**
(``120,00 m²``, ``169 hectares``, ``9 ares``, ``40 ca.``) e só converte
quando a expressão inteira é inequívoca:

- ``m²``/``m2`` → divide por 10.000;
- ``ha``/``ha.``/``has``/``há``/``hectare(s)`` → valor como está;
- composto ``"<N> hectares, <A> ares e <C> centiares"`` (``ha``/``a``/``ca``)
  → ``N + A/100 + C/10000``; ``A`` e ``C`` só valem de 0 a 99 e, no
  composto, o ponto de ``N`` é milhar (``1.069 hectares`` → 1069);
- ``alqueires`` (falta o fator aprovado), unidade ausente, zero, negativo,
  número fora do par ou dois pares → ``None``.

Número pt-BR estrito: com vírgula o ponto é milhar em grupos de 3 (primeiro
grupo de 1 a 3 dígitos); sem vírgula, ponto agrupando 3 em 3 é **ambíguo**
(milhar ou decimal) e devolve ``None``; mais de um separador do mesmo tipo,
vírgula solta e texto vazio também. O número precisa começar fora de letra
(``l20``/``O50`` não são número) e a sobra fora do par/composto só pode ser
espaço, pontuação ou palavra sem dígito nem unidade: ``120 m²/ha`` e
``169 ha, 9 a e quarenta ca`` são ambíguos. Unidade do texto divergente do
enum do A3, ou valor convertido que não bate com o ``normalized`` do A3
(tolerância ``0.00005``; em ``m2`` depois de ÷10.000), devolve ``None``: quem
chama trata como pendência do revisor, nunca como zero. A função não levanta
exceção — dado de OCR é entrada hostil.
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from .area_ha_padroes import (
    _ALQUEIRE,
    _COMPOSTO,
    _DIGITO,
    _MENOS,
    _PAR,
    _UNIDADE_NA_SOBRA,
    _codigo_da_unidade,
    _unidade_do_enum,
)

CASAS_DECIMAIS = 4
_QUANTUM = Decimal('0.0001')
_MAXIMO = Decimal('99999999.9999')
_M2_POR_HA = Decimal(10000)
_ARES_POR_HA = Decimal(100)
_CENTIARES_POR_HA = Decimal(10000)
_TOLERANCIA = Decimal('0.00005')


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


def hectares_confirmados(raw, normalizado):
    """``normalized`` do A3 em ha, quantizado e conferido com o texto.

    Texto convertível igual ao canônico (tolerância ``0.00005``) → o
    canônico quantizado; texto convertível divergente ou canônico não
    numérico → ``None`` (pendência do revisor, nunca o canônico sozinho);
    texto sem par número+unidade inequívoco → o canônico quantizado, pois
    aí não há o que confrontar.
    """
    quantizado = quantizar_hectares(normalizado)
    if quantizado is None:
        return None
    convertido = converter_para_hectares(raw, 'ha')
    if convertido is None:
        return quantizado
    esperado = _decimal_do_normalizado(quantizado)
    if esperado is None or abs(esperado - convertido) > _TOLERANCIA:
        return None
    return quantizado


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
    """Fora do par/composto: dígito, unidade ou ``/`` → expressão ambígua."""
    resto = texto[:achado.start()] + texto[achado.end():]
    return (
        bool(_DIGITO.search(resto))
        or '/' in resto
        or bool(_UNIDADE_NA_SOBRA.search(resto))
    )


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
