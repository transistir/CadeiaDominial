"""Nomes de cadastro, conversão para texto de input e evidência da linha."""

from datetime import date
from decimal import Decimal

from ..revisao import MOTIVO_BAIXA_CONFIANCA


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
    # Importação tardia: ``views`` vai consumir este módulo (fase 2) e a
    # máscara de CPF/RG mora lá.
    from ..views import _mascarar_evidencia

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
