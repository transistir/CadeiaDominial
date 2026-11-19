"""Avisos produzidos pela importação que o replay não recalcula.

Os registros (código + tipos) vão para ``ExtracaoSugerida.payload`` sob
``CHAVE_PAYLOAD_IMPORTACAO`` e o replay devolve o MESMO texto pelo mesmo
gerador da primeira resposta (#324 rodada 4).
"""


# Avisos que a importação PRODUZ e que o replay não consegue recalcular
# (#324 rodada 4, P2 do Codex). O de homônimo de outro tipo (#267) depende do
# cadastro ANTES do ato: depois da importação o documento declarado já existe
# e a checagem devolve ``None``. Por isso a importação grava o que produziu
# em ``ExtracaoSugerida.payload`` — JSON que já existe, sem modelo nem
# migration — sob uma chave própria, fora do contrato A3 (``payload_servico``,
# de onde a revisão lê, fica intacto). Por ato entram só o CÓDIGO e os dois
# TIPOS documentais: nunca número, cartório, id ou nome (PII). O replay
# devolve o mesmo texto pelo mesmo gerador da primeira resposta.
CHAVE_PAYLOAD_IMPORTACAO = '_importacao'
VERSAO_AVISOS_GRAVADOS = 1
AVISO_HOMONIMO_OUTRO_TIPO = 'homonimo_outro_tipo'


def _texto_ou_none(valor):
    """Texto sem bordas; vazio de verdade (``None``, ``''``, só espaços) é None."""
    return (valor or '').strip() or None


_NOME_DO_TIPO_DA_ORIGEM = {'matricula': 'matrícula', 'transcricao': 'transcrição'}


def _aviso_homonimo(tipo_declarado, tipo_existente):
    """Aviso do #267: fala do TIPO do homônimo, nunca do número nem de ids."""
    existente = _NOME_DO_TIPO_DA_ORIGEM.get(tipo_existente, 'documento')
    declarado = _NOME_DO_TIPO_DA_ORIGEM.get(tipo_declarado, tipo_declarado)
    return (
        f'Já existe uma {existente} com o mesmo número neste cartório '
        f'(outro tipo). A origem foi mantida como {declarado}, como '
        'declarada; confira o tipo.'
    )


def _registro_homonimo(tipo_declarado, tipo_existente):
    """O que se grava do aviso de homônimo: código e os dois tipos, só isso."""
    return {
        'codigo': AVISO_HOMONIMO_OUTRO_TIPO,
        'tipo_declarado': tipo_declarado,
        'tipo_existente': tipo_existente,
    }


def _texto_do_aviso_gravado(registro):
    """Texto do aviso a partir do registro gravado (primeira resposta e replay).

    Registro de código desconhecido ou malformado não vira texto: o que está
    no JSON pode ser mais velho que o código que o lê.
    """
    if not isinstance(registro, dict):
        return None
    if registro.get('codigo') != AVISO_HOMONIMO_OUTRO_TIPO:
        return None
    declarado = registro.get('tipo_declarado')
    existente = registro.get('tipo_existente')
    if not isinstance(declarado, str) or not isinstance(existente, str):
        return None
    return _aviso_homonimo(declarado, existente)


def _gravar_avisos_da_importacao(extracao, avisos_gravados):
    """Grava no payload da extração os avisos que a importação produziu (#324).

    Atribuição, não acréscimo: o bloco é refeito inteiro, então repetir a
    gravação nunca duplica o aviso. Sem aviso a gravar o payload não é
    tocado. Roda DENTRO da transação do ``importar``: se qualquer ato
    falhar, o rollback leva o bloco junto e a nova tentativa grava só o
    que ela mesma produziu.
    """
    if not avisos_gravados:
        return
    # Cópia rasa montada à parte: o dict do chamador só é substituído de uma
    # vez, imediatamente antes do save — nunca fica com ``_importacao``
    # pela metade se algo falhar antes.
    payload = {
        **extracao.payload,
        CHAVE_PAYLOAD_IMPORTACAO: {
            'versao': VERSAO_AVISOS_GRAVADOS,
            'avisos': {
                chave: list(registros)
                for chave, registros in avisos_gravados.items()
            },
        },
    }
    extracao.payload = payload
    extracao.save(update_fields=['payload'])


def _avisos_gravados_da_extracao(extracao):
    """``{chave do ato: [registro, ...]}`` que a importação gravou (ou ``{}``)."""
    payload = extracao.payload
    bloco = (
        payload.get(CHAVE_PAYLOAD_IMPORTACAO) if isinstance(payload, dict)
        else None
    )
    avisos = bloco.get('avisos') if isinstance(bloco, dict) else None
    return avisos if isinstance(avisos, dict) else {}
