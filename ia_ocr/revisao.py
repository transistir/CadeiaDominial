"""Desnormalização do payload A3 em linhas de revisão (I-5, §18).

``desnormalizar`` é pura: percorre o payload e devolve ``CampoSugerido``
NÃO salvos — uma linha por folha editável (objeto com ``normalized``),
mais as linhas estruturais de ato (``/acts/{i}``, normalized = rótulo) e
de parte (``/acts/{i}/partes/{j}``, normalized = papel), mais
placeholders dos destinos obrigatórios ausentes. Nenhuma query, nenhuma
gravação: quem persiste é o chamador.

Toda pendência vira motivo estável em ``motivos_revisao`` com
``requer_revisao=True`` — nunca silêncio:

- ``normalizacao_invalida`` — ``normalized`` de data/decimal/área fora do
  canônico (vira ``normalized=None``; o raw é preservado);
- ``unidade_area`` — área de ato em unidade ≠ ha (conversão é decisão
  humana, nunca silenciosa);
- ``baixa_confianca`` — confiança < 0.70 (força revisão mesmo com o
  payload dizendo ``requer_revisao=False``);
- ``closure`` — qualquer linha ``/closure/*`` (classificação de fim de
  cadeia é SEMPRE decisão humana);
- ``evidencia_invalida`` — página da evidência fora das páginas do job;
- ``trecho_ausente`` — trecho não é substring do ``texto_ocr`` da página.
"""

import re

from . import destinos, valores
from .models import CampoSugerido

LIMIAR_CONFIANCA = 0.70

MOTIVO_NORMALIZACAO_INVALIDA = 'normalizacao_invalida'
MOTIVO_UNIDADE_AREA = 'unidade_area'
MOTIVO_BAIXA_CONFIANCA = 'baixa_confianca'
MOTIVO_CLOSURE = 'closure'
MOTIVO_EVIDENCIA_INVALIDA = 'evidencia_invalida'
MOTIVO_TRECHO_AUSENTE = 'trecho_ausente'

# Destinos obrigatórios (§2.A): ausentes no payload → placeholder em revisão.
_OBRIGATORIOS_DOCUMENTO = ('tipo', 'data', 'cartorio')
_OBRIGATORIOS_ATO = ('tipo_sugerido', 'data')

_TIPOS_NORMALIZAVEIS = ('data', 'decimal', 'area')

_AREA_DE_ATO = re.compile(r'/acts/\d+/area')


def desnormalizar(extracao, payload, paginas) -> list[CampoSugerido]:
    """Payload A3 → linhas de ``CampoSugerido`` não salvas, em ordem estável.

    ``paginas`` é a lista de ``PaginaOcr`` do job: a evidência só aponta
    para página que existe ali, e o trecho só é mantido se for substring
    literal do ``texto_ocr`` daquela página.
    """
    texto_paginas = {
        pagina.numero_pagina: pagina.texto_ocr for pagina in paginas
    }
    linhas = _folhas(extracao, '/document', payload.get('document'), texto_paginas)
    linhas += _placeholders_documento(extracao, payload.get('document'))
    for indice, ato in enumerate(payload.get('acts') or []):
        linhas += _ato(extracao, f'/acts/{indice}', ato, texto_paginas)
    linhas += _folhas(extracao, '/closure', payload.get('closure'), texto_paginas)
    return linhas


def _eh_folha(no):
    """Folha editável do A3: objeto com a chave ``normalized``."""
    return isinstance(no, dict) and 'normalized' in no


def _folhas(extracao, ponteiro, no, texto_paginas):
    """Recursão genérica: uma linha por folha editável do ramo."""
    if _eh_folha(no):
        return [_de_campo(extracao, ponteiro, no, texto_paginas)]
    if isinstance(no, dict):
        linhas = []
        for chave, valor in no.items():
            linhas += _folhas(
                extracao, f'{ponteiro}/{chave}', valor, texto_paginas
            )
        return linhas
    if isinstance(no, list):
        linhas = []
        for indice, item in enumerate(no):
            linhas += _folhas(
                extracao, f'{ponteiro}/{indice}', item, texto_paginas
            )
        return linhas
    return []


def _ato(extracao, ponteiro, ato, texto_paginas):
    """Linha estrutural do ato + placeholders + folhas + partes."""
    linhas = [_de_ato(extracao, ponteiro, ato, texto_paginas)]
    for nome in _OBRIGATORIOS_ATO:
        if not _eh_folha(ato.get(nome)):
            linhas.append(_placeholder(extracao, f'{ponteiro}/{nome}'))
    for nome, valor in ato.items():
        if nome != 'partes':
            linhas += _folhas(
                extracao, f'{ponteiro}/{nome}', valor, texto_paginas
            )
    for indice, parte in enumerate(ato.get('partes') or []):
        linhas += _parte(
            extracao, f'{ponteiro}/partes/{indice}', parte, texto_paginas
        )
    return linhas


def _parte(extracao, ponteiro, parte, texto_paginas):
    """Linha estrutural da parte (normalized = papel) + folhas."""
    linhas = [_de_parte(extracao, ponteiro, parte, texto_paginas)]
    for nome, valor in parte.items():
        linhas += _folhas(
            extracao, f'{ponteiro}/{nome}', valor, texto_paginas
        )
    return linhas


def _placeholders_documento(extracao, document):
    if not isinstance(document, dict):
        document = {}
    return [
        _placeholder(extracao, f'/document/{nome}')
        for nome in _OBRIGATORIOS_DOCUMENTO
        if not _eh_folha(document.get(nome))
    ]


def _valor_do_payload(tipo, valor):
    """Valor do A3 → campo do modelo preservando ``None``.

    ``valores.do_payload`` converte ``None`` em ``''``, o que perderia a
    distinção entre "não normalizado" e "vazio" (``raw``/``normalized``
    aceitam NULL no modelo): ``None`` permanece ``None`` e só
    ``str``/``bool`` passam pelo codec.
    """
    if valor is None:
        return None
    return valores.do_payload(tipo, valor)


def _de_campo(extracao, ponteiro, campo, texto_paginas):
    """Linha de uma folha editável, com tipos/motivos do §18."""
    tipo_valor = destinos.destino_de(ponteiro).tipo_valor
    motivos = []

    normalized = _valor_do_payload(tipo_valor, campo.get('normalized'))
    if tipo_valor in _TIPOS_NORMALIZAVEIS:
        if normalized is None:
            # Não normalizado (null) ≠ vazio: sem canônico, há pendência.
            motivos.append(MOTIVO_NORMALIZACAO_INVALIDA)
        else:
            try:
                valores.para_python(tipo_valor, normalized)
            except valores.ValorInvalido:
                motivos.append(MOTIVO_NORMALIZACAO_INVALIDA)
                normalized = None
    if _AREA_DE_ATO.fullmatch(ponteiro) and campo.get('unidade') != 'ha':
        motivos.append(MOTIVO_UNIDADE_AREA)

    confianca = campo.get('confianca')
    _checar_confianca(confianca, motivos)
    if ponteiro.startswith('/closure'):
        motivos.append(MOTIVO_CLOSURE)
    pagina, trecho = _resolver_evidencia(
        campo.get('evidencia'), texto_paginas, motivos
    )

    return CampoSugerido(
        extracao=extracao,
        chave=ponteiro,
        raw=_valor_do_payload(tipo_valor, campo.get('raw')),
        normalized=normalized,
        tipo_valor=tipo_valor,
        confianca=confianca,
        requer_revisao=bool(campo.get('requer_revisao')) or bool(motivos),
        motivos_revisao=motivos,
        evidencia_pagina=pagina,
        evidencia_trecho=trecho,
    )


def _de_ato(extracao, ponteiro, ato, texto_paginas):
    """Linha estrutural do ato: chave ``/acts/{i}``, normalized = rótulo."""
    motivos = []
    confianca = _checar_confianca(ato.get('confianca'), motivos)
    pagina, trecho = _resolver_evidencia(
        ato.get('evidencia'), texto_paginas, motivos
    )
    rotulo = ato.get('rotulo') if _eh_folha(ato.get('rotulo')) else {}
    return CampoSugerido(
        extracao=extracao,
        chave=ponteiro,
        raw=None,
        normalized=_valor_do_payload('ato', rotulo.get('normalized')),
        tipo_valor='ato',
        confianca=confianca,
        requer_revisao=bool(ato.get('requer_revisao')) or bool(motivos),
        motivos_revisao=motivos,
        evidencia_pagina=pagina,
        evidencia_trecho=trecho,
    )


def _de_parte(extracao, ponteiro, parte, texto_paginas):
    """Linha estrutural da parte: normalized = papel efetivo."""
    motivos = []
    confianca = _checar_confianca(parte.get('confianca'), motivos)
    pagina, trecho = _resolver_evidencia(
        parte.get('evidencia'), texto_paginas, motivos
    )
    return CampoSugerido(
        extracao=extracao,
        chave=ponteiro,
        raw=None,
        normalized=parte.get('papel'),
        tipo_valor='parte',
        confianca=confianca,
        requer_revisao=bool(parte.get('requer_revisao')) or bool(motivos),
        motivos_revisao=motivos,
        evidencia_pagina=pagina,
        evidencia_trecho=trecho,
    )


def _placeholder(extracao, chave):
    """Destino obrigatório ausente: linha vazia, sempre em revisão."""
    return CampoSugerido(
        extracao=extracao,
        chave=chave,
        raw=None,
        normalized=None,
        tipo_valor=destinos.destino_de(chave).tipo_valor,
        confianca=None,
        requer_revisao=True,
        motivos_revisao=[],
        evidencia_pagina=None,
        evidencia_trecho='',
    )


def _checar_confianca(confianca, motivos):
    """Não nula e < limiar → ``baixa_confianca``; devolve a confiança."""
    if confianca is not None and confianca < LIMIAR_CONFIANCA:
        motivos.append(MOTIVO_BAIXA_CONFIANCA)
    return confianca


def _resolver_evidencia(evidencia, texto_paginas, motivos):
    """(pagina, trecho) confiáveis; acumula motivos quando não são.

    Página fora do job → ``evidencia_invalida`` (pagina vira ``None``).
    Trecho que não é substring do ``texto_ocr`` da página — ou página
    inexistente, onde nada é verificável — → ``trecho_ausente`` (trecho
    vira ``''``). Sem evidência (``None``) não é pendência: o A3 a admite
    nula.
    """
    if not isinstance(evidencia, dict):
        return None, ''
    numero = evidencia.get('pagina')
    if numero in texto_paginas:
        pagina = numero
    else:
        pagina = None
        motivos.append(MOTIVO_EVIDENCIA_INVALIDA)
    trecho = evidencia.get('trecho')
    texto = texto_paginas.get(pagina) if pagina is not None else None
    if texto is not None and isinstance(trecho, str) and trecho in texto:
        return pagina, trecho
    motivos.append(MOTIVO_TRECHO_AUSENTE)
    return pagina, ''
