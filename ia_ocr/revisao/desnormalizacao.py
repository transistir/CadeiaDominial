"""Payload A3 → linhas de revisão (desnormalização e placeholders)."""

from dominial.models import LancamentoTipo

from ..models import CampoSugerido
from ..rotulos import resolver_tipo
from .campos_payload import _de_ato, _de_campo, _de_parte, _placeholder
from .estruturas import (
    CAMPOS_DA_ORIGEM, CAMPOS_DA_TRANSMISSAO, _OBRIGATORIOS_ATO,
    _OBRIGATORIOS_DOCUMENTO, _eh_folha, linha_ignorada,
)
from .linhas import _contexto_revisao
from .tipos import _caminhos_do_tipo, _rotulo_do_payload, _tem_folha, _tipos_efetivos


def desnormalizar(extracao, payload, paginas) -> list[CampoSugerido]:
    """Payload A3 → linhas de ``CampoSugerido`` não salvas, em ordem estável.

    ``paginas`` é a lista de ``PaginaOcr`` do job: a evidência só aponta
    para página que existe ali, e o trecho só é mantido se for substring
    literal do texto vigente daquela página — ``texto_corrigido`` (decisão
    #290) ou, sem ele, o ``texto_ocr`` puro.

    Os campos exigidos pelo tipo efetivo (``LancamentoTipo.requer_*``)
    ausentes no payload também viram placeholder editável: sem a linha, a
    tela acusa pendência sem controle para resolvê-la. Uma query única
    resolve as configurações dos tipos presentes no payload.
    """
    texto_paginas = {
        pagina.numero_pagina: pagina.texto_corrigido or pagina.texto_ocr
        for pagina in paginas
    }
    # Sem pk não há como resolver ``LancamentoTipo`` sem tocar o banco; o
    # fluxo real sempre desnormaliza com a extração já salva.
    configuracoes = (
        _configuracoes_do_payload(payload)
        if extracao.pk is not None else {}
    )
    linhas = _folhas(extracao, '/document', payload.get('document'), texto_paginas)
    linhas += _placeholders_documento(extracao, payload.get('document'))
    for indice, ato in enumerate(payload.get('acts') or []):
        linhas += _ato(
            extracao, f'/acts/{indice}', ato, texto_paginas, configuracoes,
        )
    linhas += _folhas(extracao, '/closure', payload.get('closure'), texto_paginas)
    return linhas


def _configuracoes_do_payload(payload):
    """Tipos efetivos do payload → ``LancamentoTipo`` (uma query).

    P1-2 (#322 rodada 7): usa resolver_tipo com precedência rotulo -> sugerido
    (sem edição do usuário no payload cru).
    """
    tipos = set()
    for ato in payload.get('acts') or []:
        if not isinstance(ato, dict):
            continue
        campo = ato.get('tipo_sugerido')
        tipo_sug = (
            campo.get('normalized')
            if _eh_folha(campo)
            and isinstance(campo.get('normalized'), str) else None
        )
        tipo, _, _ = resolver_tipo(None, _rotulo_do_payload(ato), tipo_sug)
        if tipo is not None:
            tipos.add(tipo)
    if not tipos:
        return {}
    configuracoes = {}
    for tipo in LancamentoTipo.objects.filter(
        tipo__in=tipos,
    ).order_by('pk'):
        configuracoes.setdefault(tipo.tipo, tipo)
    return configuracoes

def _origem_do_payload(ato):
    """Bloco ``origem`` do ato no payload A3 (objeto), ou ``{}``.

    O schema aceita ``origem: null`` — nulo e ausente são o mesmo "sem origem".
    """
    origem = ato.get('origem')
    return origem if isinstance(origem, dict) else {}


def _ato_tem_origem(ato):
    """O payload do ato traz ao menos uma folha da origem (#324)?"""
    return any(_eh_folha(no) for no in _origem_do_payload(ato).values())


def _folhas(extracao, ponteiro, no, texto_paginas):
    """Recursão genérica: uma linha por folha editável do ramo.

    Folhas com nome em ``LINHAS_IGNORADAS`` não viram linha — nem no payload
    novo, nem na re-extração.
    """
    if linha_ignorada(ponteiro):
        return []
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


def _ato(extracao, ponteiro, ato, texto_paginas, configuracoes=None):
    """Linha estrutural do ato + placeholders + folhas + partes."""
    linhas = [_de_ato(extracao, ponteiro, ato, texto_paginas)]
    tipo_sugerido = ato.get('tipo_sugerido')
    tipo_sugerido_norm = (
        tipo_sugerido.get('normalized')
        if _eh_folha(tipo_sugerido)
        and isinstance(tipo_sugerido.get('normalized'), str) else None
    )
    tipo_efetivo, _, _ = resolver_tipo(
        None, _rotulo_do_payload(ato), tipo_sugerido_norm,
    )
    for nome in _OBRIGATORIOS_ATO:
        if _eh_folha(ato.get(nome)):
            continue
        # P1-2 (rodada 7): com o tipo resolvido, a ausência
        # do tipo_sugerido não é pendência de revisão.
        linhas.append(_placeholder(
            extracao, f'{ponteiro}/{nome}',
            requer_revisao=not (
                nome == 'tipo_sugerido' and tipo_efetivo is not None
            ),
        ))
    configuracao = (configuracoes or {}).get(tipo_efetivo)
    caminhos = _caminhos_do_tipo(tipo_efetivo, configuracao)
    for caminho in caminhos:
        chave = f'{ponteiro}/{caminho}'
        if not _tem_folha(ato, caminho):
            linhas.append(_placeholder(extracao, chave, requer_revisao=False))
    if 'origem/cartorio' in caminhos or _ato_tem_origem(ato):
        origem = _origem_do_payload(ato)
        for nome in CAMPOS_DA_ORIGEM:
            if not _eh_folha(origem.get(nome)):
                linhas.append(_placeholder(
                    extracao, f'{ponteiro}/origem/{nome}',
                    requer_revisao=False,
                ))
    for nome in CAMPOS_DA_TRANSMISSAO:
        if not _eh_folha(ato.get(nome)):
            linhas.append(_placeholder(
                extracao, f'{ponteiro}/{nome}', requer_revisao=False,
            ))
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

def garantir_placeholders_obrigatorios(extracao):
    """Cria as linhas exigidas pelo tipo efetivo que ainda não existem.

    Chamado depois de salvar um bloco: mudar ``tipo_sugerido`` pode passar a
    exigir título/descrição/cartório de origem. ``requer_revisao=False``
    porque a ausência já é bloqueada por ``obrigatorio_ausente``; duplicar a
    pendência só polui a tela. Devolve as linhas não salvas.

    Tipo que exige ``origem/cartorio`` leva a origem INTEIRA (#324): as cinco
    chaves de ``CAMPOS_DA_ORIGEM`` que ainda não existirem nascem vazias, como
    no desmonte inicial (``_ato``). Sem elas, um ato que a IA leu sem origem e
    o revisor passou a início de matrícula ficaria só com o cartório — sem onde
    declarar número/tipo/livro/folha/data — e a importação gravaria sem
    ``LancamentoOrigem``, sem Documento de origem e sem a FK. Só o cartório é
    exigido (``_caminhos_do_tipo``); as outras cinco são opcionais.
    """
    linhas, atos = _contexto_revisao(extracao)
    tipos_por_ato, configuracoes = _tipos_efetivos(linhas, atos)
    # Inclui descartadas: uma linha descartada ainda ocupa a chave única e
    # não pode virar placeholder de novo (IntegrityError).
    existentes = set(extracao.campos.values_list('chave', flat=True))
    novas = []
    for ato in atos:
        tipo_efetivo = tipos_por_ato.get(ato.chave)
        configuracao = configuracoes.get(tipo_efetivo)
        caminhos = _caminhos_do_tipo(tipo_efetivo, configuracao)
        if 'origem/cartorio' in caminhos:
            caminhos += tuple(f'origem/{nome}' for nome in CAMPOS_DA_ORIGEM)
        for caminho in caminhos:
            chave = f'{ato.chave}/{caminho}'
            if chave in existentes:
                continue
            novas.append(_placeholder(extracao, chave, requer_revisao=False))
            existentes.add(chave)
    if novas:
        CampoSugerido.objects.bulk_create(novas)
    return novas
