"""Linhas de folha/estruturais/placeholder montadas do payload A3."""

from .. import destinos, valores
from ..models import CampoSugerido
from .area_ha import converter_para_hectares
from .estruturas import (
    _AREA_DE_ATO,
    _TIPOS_NORMALIZAVEIS,
    LIMIAR_CONFIANCA,
    MATCH_PESSOA_CANDIDATOS,
    MOTIVO_BAIXA_CONFIANCA,
    MOTIVO_CLOSURE,
    MOTIVO_EVIDENCIA_INVALIDA,
    MOTIVO_NORMALIZACAO_INVALIDA,
    MOTIVO_TRECHO_AUSENTE,
    MOTIVO_UNIDADE_AREA,
    _eh_folha,
)


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
    unidade = campo.get('unidade')
    eh_area_de_ato = bool(_AREA_DE_ATO.fullmatch(ponteiro))
    convertida = False
    if eh_area_de_ato and (normalized is None or unidade != 'ha'):
        # #373: unidade explícita (ha, m²) ou composto hectare/are/centiare
        # vira hectares na desnormalização. Sem conversão inequívoca, a
        # unidade continua pendência do revisor.
        convertido = converter_para_hectares(campo.get('raw'), unidade)
        if convertido is not None:
            normalized = f'{convertido:.4f}'
            convertida = True
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
    if eh_area_de_ato and unidade != 'ha' and not convertida:
        motivos.append(MOTIVO_UNIDADE_AREA)

    confianca = campo.get('confianca')
    _checar_confianca(confianca, motivos)
    if ponteiro.startswith('/closure'):
        motivos.append(MOTIVO_CLOSURE)
    pagina, trecho, bbox = _resolver_evidencia(
        campo.get('evidencia'), texto_paginas, motivos
    )
    candidatos, escolhido = [], None
    if tipo_valor == 'cartorio':
        sugestao = campo.get('match_sugerido')
        if isinstance(sugestao, dict):
            candidatos, escolhido = _candidatos_do_match(
                sugestao.get('cartorio_id'), sugestao.get('candidatos'),
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
        match_candidatos=candidatos,
        cartorio_escolhido_id=escolhido,
        evidencia_pagina=pagina,
        evidencia_trecho=trecho,
        evidencia_bbox=bbox,
    )


def _de_ato(extracao, ponteiro, ato, texto_paginas):
    """Linha estrutural do ato: chave ``/acts/{i}``, normalized = rótulo."""
    motivos = []
    confianca = _checar_confianca(ato.get('confianca'), motivos)
    pagina, trecho, bbox = _resolver_evidencia(
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
        evidencia_bbox=bbox,
    )


def _de_parte(extracao, ponteiro, parte, texto_paginas):
    """Linha estrutural da parte: normalized = papel efetivo."""
    motivos = []
    confianca = _checar_confianca(parte.get('confianca'), motivos)
    pagina, trecho, bbox = _resolver_evidencia(
        parte.get('evidencia'), texto_paginas, motivos
    )
    candidatos, escolhido = _candidatos_do_match(
        parte.get('match_pessoa_id'), parte.get(MATCH_PESSOA_CANDIDATOS),
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
        match_candidatos=candidatos,
        pessoa_escolhida_id=escolhido,
        evidencia_pagina=pagina,
        evidencia_trecho=trecho,
        evidencia_bbox=bbox,
    )


def _id_valido(valor):
    return type(valor) is int and valor > 0


def _candidatos_do_match(unico, candidatos=None):
    """``(match_candidatos, escolhido_id|None)`` a partir do enriquecimento.

    Só ids do payload enriquecido: único → ``([id], id)``; mais de um
    candidato → ``(ids, None)`` (o revisor escolhe); nenhum → ``([], None)``.
    """
    if _id_valido(unico):
        return [unico], unico
    ids = []
    for valor in candidatos if isinstance(candidatos, list) else []:
        if _id_valido(valor) and valor not in ids:
            ids.append(valor)
    if len(ids) == 1:
        return ids, ids[0]
    return ids, None


def _placeholder(extracao, chave, requer_revisao=True):
    """Destino obrigatório ausente: linha vazia, editável em revisão."""
    return CampoSugerido(
        extracao=extracao,
        chave=chave,
        raw=None,
        normalized=None,
        tipo_valor=destinos.destino_de(chave).tipo_valor,
        confianca=None,
        requer_revisao=requer_revisao,
        motivos_revisao=[],
        evidencia_pagina=None,
        evidencia_trecho='',
        evidencia_bbox=None,
    )

def _checar_confianca(confianca, motivos):
    """Não nula e < limiar → ``baixa_confianca``; devolve a confiança."""
    if confianca is not None and confianca < LIMIAR_CONFIANCA:
        motivos.append(MOTIVO_BAIXA_CONFIANCA)
    return confianca


def _bbox_valido(bbox):
    """bbox aproveitável: lista JSON de exatamente 4 números (bool excluído)."""
    return (
        isinstance(bbox, list)
        and len(bbox) == 4
        and all(
            isinstance(valor, (int, float)) and not isinstance(valor, bool)
            for valor in bbox
        )
    )


def _resolver_evidencia(evidencia, texto_paginas, motivos):
    """(pagina, trecho, bbox) confiáveis; acumula motivos quando não são.

    Página fora do job → ``evidencia_invalida`` (pagina vira ``None``).
    Trecho que não é substring do texto vigente da página — ou página
    inexistente, onde nada é verificável — → ``trecho_ausente`` (trecho
    vira ``''``). Sem evidência (``None``) não é pendência: o A3 a admite
    nula.

    ``bbox`` (decisão #290/17-10, pixels do OCR) é preservado só quando é
    lista de 4 números; fora disso vira ``None`` e NÃO é pendência — é
    conveniência de template, e a conversão pixel→ponto de PDF (dpi do
    job) não é desta camada.
    """
    if not isinstance(evidencia, dict):
        return None, '', None
    bbox = evidencia.get('bbox')
    if not _bbox_valido(bbox):
        bbox = None
    numero = evidencia.get('pagina')
    if numero in texto_paginas:
        pagina = numero
    else:
        pagina = None
        motivos.append(MOTIVO_EVIDENCIA_INVALIDA)
    trecho = evidencia.get('trecho')
    texto = texto_paginas.get(pagina) if pagina is not None else None
    if texto is not None and isinstance(trecho, str) and trecho in texto:
        return pagina, trecho, bbox
    motivos.append(MOTIVO_TRECHO_AUSENTE)
    return pagina, '', bbox
