"""Padrões de leitura da área no documento e unidade do texto (#373).

Número pt-BR: começa e termina em dígito ASCII ("1.234,5678", "169");
``O``/``l`` nunca entram. Número colado a letra ("l20", "O50") não é
número, e separador decimal sem parte inteira (",5", ".5") também não: o
separador denuncia OCR quebrado. A unidade colada ao número (par/composto)
não pode ser seguida de letra/dígito ("ha" em "hectares"). Unidade solta
(sem número) exige borda dos dois lados: o "a" de "área" e o "ha" de
"Ilha" não são unidade; as formas curtas (``a``, ``ha``, ``ca``) só valem
coladas ao número. ``has``/``há`` são hectares. O composto só consome
``ares``/``a`` (o singular ``are`` fica como sobra ambígua). Na sobra do
par/composto, ``a``/``a.`` é ares mesmo separado do número; só a
preposição imediatamente antes do número ("equivalente a 12,50 ha") é
descartada.
"""

import re

_NUMERO = r'[0-9](?:[0-9.,]*[0-9])?'
_BORDA_ESQUERDA = r'(?<![0-9A-Za-zÀ-ÿ])'
# Número não pode vir colado a separador decimal (",5"/".5"): seria OCR
# quebrado lendo só o sufixo ASCII.
_BORDA_NUMERO = r'(?<![0-9A-Za-zÀ-ÿ.,])'
_FIM_DA_UNIDADE = r'(?![^\W_])'
_UNIDADE_M2 = r'(?:m²|m2)'
_UNIDADE_HA = r'(?:hectares|hectare|has|há|ha\.?)'
_UNIDADE_ARES = r'(?:ares|a\.?)'
_UNIDADE_CENTIARES = r'(?:centiares|centiare|ca\.?)'
_UNIDADE_ALQUEIRE = r'(?:alqueires|alqueire)'
_UNIDADE_TODAS = (
    rf'(?:{_UNIDADE_ALQUEIRE}|{_UNIDADE_CENTIARES}|{_UNIDADE_HA}'
    rf'|{_UNIDADE_M2}|{_UNIDADE_ARES})'
)

_SEPARADOR = r'(?:,\s*(?:e\s+)?|\s+e\s+|\s+)'
_COMPOSTO = re.compile(
    rf'{_BORDA_NUMERO}(?P<hectares>{_NUMERO})\s*{_UNIDADE_HA}'
    rf'{_FIM_DA_UNIDADE}{_SEPARADOR}'
    rf'{_BORDA_NUMERO}(?P<ares>{_NUMERO})\s*{_UNIDADE_ARES}'
    rf'{_FIM_DA_UNIDADE}(?:{_SEPARADOR}'
    rf'{_BORDA_NUMERO}(?P<centiares>{_NUMERO})\s*{_UNIDADE_CENTIARES}'
    rf'{_FIM_DA_UNIDADE})?',
    re.IGNORECASE,
)
_PAR = re.compile(
    rf'{_BORDA_NUMERO}(?P<numero>{_NUMERO})\s*'
    rf'(?P<unidade>{_UNIDADE_TODAS}){_FIM_DA_UNIDADE}',
    re.IGNORECASE,
)
_UNIDADE_SOLTA = re.compile(
    r'(?<![0-9A-Za-zÀ-ÿ])'
    r'(?:hectares?|ares|centiares?|alqueires?|has|há|m²|m2)'
    r'(?![0-9A-Za-zÀ-ÿ])',
    re.IGNORECASE,
)
# Sobra do par/composto: qualquer forma de unidade (inclusive as curtas e
# o singular "are", que o composto não consome) torna a expressão ambígua,
# colada ou não ao número. ``a``/``a.`` na sobra é sempre ares — inclusive
# no fim do texto ("169 ha e nove a"). A preposição ("equivalente a 12,50
# ha") não chega aqui: ``_sobra_unidade`` remove o ``a`` que precede o
# número no texto original antes de testar (#381).
_UNIDADE_NA_SOBRA = re.compile(
    r'(?<![0-9A-Za-zÀ-ÿ])'
    r'(?:hectares?|centiares?|alqueires?|ares|are|has|há|m²|m2'
    r'|alqs?\.?|ha\.?|a\.?|ca\.?)'
    r'(?![0-9A-Za-zÀ-ÿ])',
    re.IGNORECASE,
)
# ``a`` isolado terminando o texto antes do número: preposição
# ("equivalente a 12,50 ha"), não ares.
_PREPOSICAO_A = re.compile(r'(?<![0-9A-Za-zÀ-ÿ])a\s*$', re.IGNORECASE)
_ALQUEIRE = re.compile(r'alqueire', re.IGNORECASE)
_DIGITO = re.compile(r'[0-9]')
_MENOS = re.compile(r'[-−]')

_UNIDADES_DO_ENUM = {
    'ha': 'ha', 'has': 'ha', 'há': 'ha', 'hectare': 'ha', 'hectares': 'ha',
    'm2': 'm2', 'm²': 'm2',
    'are': 'ares', 'ares': 'ares',
    'centiare': 'centiares', 'centiares': 'centiares',
    'alqueire': 'alqueires', 'alqueires': 'alqueires',
}


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


def _codigo_da_unidade(texto):
    chave = texto.strip().rstrip('.').lower()
    if chave in ('m2', 'm²'):
        return 'm2'
    if chave in ('ha', 'has', 'há', 'hectare', 'hectares'):
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
