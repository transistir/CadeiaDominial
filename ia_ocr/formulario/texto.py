"""Nomes de cadastro, conversão para texto de input e evidência da linha."""

import re
from datetime import date
from decimal import Decimal

from ..mascaras import _mascarar_evidencia
from ..revisao import MOTIVO_BAIXA_CONFIANCA

# Data numérica inequívoca no ``raw``: o mesmo formato do A3 normalizado e
# os dois separadores completos usuais. Texto por extenso/ambíguo, dígito
# único ou separadores misturados NÃO vira data aqui.
_DATA_ISO = re.compile(r'(?P<ano>\d{4})-(?P<mes>\d{2})-(?P<dia>\d{2})')
_DATA_PONTOS = re.compile(r'(?P<dia>\d{2})\.(?P<mes>\d{2})\.(?P<ano>\d{4})')
_DATA_BARRAS = re.compile(r'(?P<dia>\d{2})/(?P<mes>\d{2})/(?P<ano>\d{4})')


def data_do_raw(texto):
    """``date`` de um ``raw`` numérico completo, ou ``None`` se não casar 100%.

    Aceita SÓ ``aaaa-mm-dd`` e ``dd.mm.aaaa``/``dd/mm/aaaa`` completos (dois
    dígitos de dia/mês, quatro de ano, separadores iguais). Não completa
    dígitos, não corrige separador e não interpreta texto por extenso: fora
    do formato exato (ou do calendário) devolve ``None``.
    """
    if not isinstance(texto, str):
        return None
    valor = texto.strip()
    achado = (
        _DATA_ISO.fullmatch(valor)
        or _DATA_PONTOS.fullmatch(valor)
        or _DATA_BARRAS.fullmatch(valor)
    )
    if achado is None:
        return None
    try:
        return date(
            int(achado.group('ano')),
            int(achado.group('mes')),
            int(achado.group('dia')),
        )
    except ValueError:
        return None


def _nomes(modelo, ids):
    """``{pk: nome}`` dos cadastros — uma query, nenhuma sem ids."""
    if not ids:
        return {}
    return dict(modelo.objects.filter(pk__in=ids).values_list('pk', 'nome'))


def _como_texto(valor):
    """Valor tipado → texto do input; vazio (ou só espaços) → ``None``."""
    if valor is None:
        return None
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        # 'f' evita a notação científica que o input de área não aceita.
        return format(valor, 'f')
    texto = str(valor)
    return texto if texto.strip() else None


def _evidencia(linhas, chave):
    """``{pagina, trecho, confianca_baixa}`` da linha, ou ``None`` sem evidência."""
    campo = linhas.get(chave)
    if campo is None or campo.status_revisao == 'descartado':
        return None
    trecho = _mascarar_evidencia(campo.evidencia_trecho or '')
    if campo.evidencia_pagina is None and not trecho:
        return None
    return {
        'pagina': campo.evidencia_pagina,
        'trecho': trecho,
        'confianca_baixa': MOTIVO_BAIXA_CONFIANCA in (campo.motivos_revisao or ()),
    }
