"""Forma, título e data do instrumento (item 4 do brief da entrega).

A regra é determinística: classifica cada texto como instrumento (marcas do
brief) ou natureza, troca só quando o instrumento veio no input errado,
extrai a data explícita do texto do instrumento e valida o calendário. O
vocabulário da natureza fica em ``prefill`` (é outra responsabilidade).
"""

import re
import unicodedata
from datetime import date

from ..classe_pendencia import eh_bloqueante

MARCAS_DE_INSTRUMENTO = (
    'escritura', 'transcri', 'carta de', 'formal de partilha',
    'alvara', 'mandado', 'termo de', 'instrumento',
)
MOTIVO_FORMA_TITULO_REINTERPRETADOS = 'forma_titulo_reinterpretados'
ROTULO_FORMA_E_TITULO = 'Forma e título'
TEXTO_FORMA_TITULO_REINTERPRETADOS = (
    "Forma e título reinterpretados: o instrumento '{instrumento}' foi para "
    "o título e a natureza '{natureza}' para a forma; confira antes de salvar."
)
MOTIVO_DATA_TRANSACAO_DO_INSTRUMENTO = 'data_transacao_do_instrumento'
ROTULO_DATA_TRANSACAO = 'Data da transmissão'
TEXTO_DATA_TRANSACAO_DO_INSTRUMENTO = (
    'Data da transmissão ajustada para a data do instrumento ({data}).'
)
TEXTO_DATA_TRANSACAO_DIVERGENTE = (
    'Data da transmissão do A3 ({a3}) difere da data do instrumento '
    '({data}); vale a data do instrumento.'
)

_MESES_PT_SEM_ACENTO = {
    'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'abril': 4, 'maio': 5,
    'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10,
    'novembro': 11, 'dezembro': 12,
}

# Data numérica COMPLETA no texto. Os dois separadores iguais, dia/mês com
# dois dígitos e ano com quatro. As bordas recusam casar dentro de um
# identificador maior em qualquer família: dígito/letra/ponto/barra antes;
# dígito/letra ou ponto/barra seguido de dígito depois. Um ponto final de
# frase continua valendo, mas não um ".999"/"/999" de token.
_DATA_PONTOS_NO_TEXTO = re.compile(
    r'(?<![\dA-Za-z./])(?P<dia>\d{2})\.(?P<mes>\d{2})\.'
    r'(?P<ano>\d{4})(?![\dA-Za-z])(?![./]\d)'
)
_DATA_BARRAS_NO_TEXTO = re.compile(
    r'(?<![\dA-Za-z./])(?P<dia>\d{2})/(?P<mes>\d{2})/'
    r'(?P<ano>\d{4})(?![\dA-Za-z])(?![./]\d)'
)
_DATA_POR_EXTENSO = re.compile(
    r'(?<!\d)(?P<dia>\d{1,2})\s+de\s+(?P<mes>[a-z]+)\s+de\s+'
    r'(?P<ano>\d{4})(?!\d)'
)


def _sem_acento(texto):
    """Texto em minúsculas e sem acento (classificação e meses pt-BR)."""
    decomposto = unicodedata.normalize('NFKD', texto)
    return ''.join(
        caractere for caractere in decomposto
        if not unicodedata.combining(caractere)
    ).lower()


def _classe_da_forma(texto):
    """``'instrumento'``, ``'natureza'`` ou ``None`` para texto vazio."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    normalizado = _sem_acento(texto)
    if any(marca in normalizado for marca in MARCAS_DE_INSTRUMENTO):
        return 'instrumento'
    return 'natureza'


def _forma_e_titulo(forma, titulo):
    """``(forma, titulo, instrumento, houve_swap, chave_do_instrumento)``.

    Troca SÓ quando o instrumento veio em ``forma`` e o outro é natureza: é
    o único caso em que os valores mudam de input. Forma=natureza com
    título=instrumento já é o mapeamento do A3 (sem swap, sem pendência).
    Mesma classe (ou texto ausente) mantém o mapeamento atual.
    """
    classe_forma = _classe_da_forma(forma)
    classe_titulo = _classe_da_forma(titulo)
    chave_do_instrumento = (
        'forma' if classe_forma == 'instrumento'
        else 'titulo' if classe_titulo == 'instrumento'
        else None
    )
    if (
        classe_forma is not None and classe_titulo is not None
        and classe_forma != classe_titulo
        and classe_forma == 'instrumento'
    ):
        return titulo, forma, forma, True, 'forma'
    instrumento = forma if classe_forma == 'instrumento' else (
        titulo if classe_titulo == 'instrumento' else None
    )
    return forma, titulo, instrumento, False, chave_do_instrumento


def _data_valida(dia, mes, ano):
    try:
        return date(int(ano), int(mes), int(dia))
    except (TypeError, ValueError):
        return None


def _datas_validas(normalizado):
    """Conjunto de datas distintas e válidas no texto normalizado."""
    datas = set()
    for padrao in (_DATA_PONTOS_NO_TEXTO, _DATA_BARRAS_NO_TEXTO):
        for achado in padrao.finditer(normalizado):
            data = _data_valida(
                achado.group('dia'), achado.group('mes'), achado.group('ano'),
            )
            if data is not None:
                datas.add(data)
    for achado in _DATA_POR_EXTENSO.finditer(normalizado):
        mes = _MESES_PT_SEM_ACENTO.get(achado.group('mes'))
        if mes is None:
            continue
        data = _data_valida(achado.group('dia'), mes, achado.group('ano'))
        if data is not None:
            datas.add(data)
    return datas


def data_do_instrumento(texto):
    """Data explícita no texto do instrumento, ou ``None``.

    Só deriva quando há EXATAMENTE UMA data válida distinta no texto —
    numérica (``dd.mm.aaaa``/``dd/mm/aaaa``, separadores iguais, fora de
    identificadores) ou por extenso (``dd de <mês> de aaaa``). Duas datas
    distintas não elegem a do instrumento: mantém o A3.
    """
    if not isinstance(texto, str) or not texto.strip():
        return None
    datas = _datas_validas(_sem_acento(texto))
    if len(datas) != 1:
        return None
    return datas.pop()


def _data_transacao_do_instrumento(instrumento, data_do_a3):
    """``(data, pendência, derivou)``: a data do instrumento vence a do A3.

    Data derivada igual à do A3 não gera pendência (nada foi reinterpretado).
    """
    data = data_do_instrumento(instrumento)
    if data is None:
        return data_do_a3, None, False
    if data == data_do_a3:
        return data, None, True
    if data_do_a3 is not None:
        texto = TEXTO_DATA_TRANSACAO_DIVERGENTE.format(
            a3=data_do_a3, data=data.isoformat(),
        )
    else:
        texto = TEXTO_DATA_TRANSACAO_DO_INSTRUMENTO.format(
            data=data.isoformat(),
        )
    return data, {
        'motivo': MOTIVO_DATA_TRANSACAO_DO_INSTRUMENTO,
        'rotulo': ROTULO_DATA_TRANSACAO,
        'texto': texto,
        'bloqueante': eh_bloqueante(MOTIVO_DATA_TRANSACAO_DO_INSTRUMENTO),
    }, True
