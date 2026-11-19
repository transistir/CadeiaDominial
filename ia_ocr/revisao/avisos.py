"""Avisos não bloqueantes da revisão."""

from dominial.models import Cartorios
from dominial.services.lancamento_origem_service import LancamentoOrigemService

from .linhas import (
    _campo_ausente, _cartorio_id_da_linha, _contexto_revisao, _valor_efetivo,
)
from .obrigatorio import _local_da_chave
from .tipos import _tipos_efetivos, tipo_da_origem


MOTIVO_LIVRO_ORIGEM_NAO_CONSTA = 'livro_origem_nao_consta'
MOTIVO_FOLHA_ORIGEM_NAO_CONSTA = 'folha_origem_nao_consta'
MOTIVOS_NAO_CONSTA = frozenset({
    MOTIVO_LIVRO_ORIGEM_NAO_CONSTA, MOTIVO_FOLHA_ORIGEM_NAO_CONSTA,
})
MOTIVO_ORIGEM_HOMONIMA = 'origem_homonimo_outro_tipo'

# Texto CANÔNICO do "não consta" por campo (#324): UMA frase por motivo, usada
# nos dois caminhos — a tela (``descrever_aviso``) e a resposta da importação
# (``importacao._avisos_livro_folha_da_origem``, um aviso por campo ausente).
# Mudar a frase aqui muda as duas; os testes comparam com igualdade exata.
TEXTO_NAO_CONSTA = {
    MOTIVO_LIVRO_ORIGEM_NAO_CONSTA: 'Livro da origem não consta no documento',
    MOTIVO_FOLHA_ORIGEM_NAO_CONSTA: 'Folha da origem não consta no documento',
}

# Rótulo do aviso por motivo (#324). O padrão é o texto que todo aviso tinha
# antes; motivo conhecido ganha a frase própria em vez do genérico.
_ROTULO_AVISO = {
    **TEXTO_NAO_CONSTA,
    MOTIVO_ORIGEM_HOMONIMA: (
        'Há um documento de outro tipo com este número no cartório da '
        'origem — confira o tipo'
    ),
}
_ROTULO_AVISO_PADRAO = 'Campo recomendado não preenchido'


def descrever_aviso(item: dict) -> dict:
    """Texto de negócio de um aviso; chave/motivo crus seguem para suporte.

    Mesmo desenho de ``descrever_pendencia``: o ``local`` identifica o campo
    e o ``rotulo`` diz o que há com ele (motivo fora do mapa → o genérico).
    """
    chave, motivo = item['chave'], item['motivo']
    return dict(
        item,
        local=_local_da_chave(chave),
        rotulo=_ROTULO_AVISO.get(motivo, _ROTULO_AVISO_PADRAO),
    )


def _origem_nao_consta(linhas, ato):
    """Livro/folha da origem que o documento não traz (#324).

    Só quando o ato cita uma origem COM número — sem número não há documento
    de origem citado e a ausência de livro/folha não diz nada. Vale para
    qualquer tipo de lançamento (não depende do ``requer_*_origem``) e é
    informativo: nunca entra em ``pendencias`` nem desabilita o "Finalizar".
    O campo não é pré-preenchido: o revisor informa ou segue sem.
    """
    if _campo_ausente(linhas, f'{ato.chave}/origem/numero'):
        return []
    achados = []
    for nome, motivo in (
        ('livro', MOTIVO_LIVRO_ORIGEM_NAO_CONSTA),
        ('folha', MOTIVO_FOLHA_ORIGEM_NAO_CONSTA),
    ):
        chave = f'{ato.chave}/origem/{nome}'
        if _campo_ausente(linhas, chave):
            achados.append({
                'chave': chave, 'motivo': motivo, 'bloqueante': False,
            })
    return achados


def _origens_homonimas(linhas, atos, documentos_queryset):
    """Avisos de homônimo de outro tipo na origem, por ato, em LOTE (#267).

    Só com o escopo do chamador (``documentos_queryset``) e com o cartório da
    origem JÁ cadastrado e escolhido: "criar novo" não tem documentos. O tipo
    é o lido ou o inferido do prefixo — a mesma regra da importação.

    O item a item fazia 5 consultas POR ATO (cartório, resolução da
    identidade, origem restrita e candidatos): o recálculo dos avisos no
    save da revisão crescia com o número de atos (#324, PR #343, MUST-FIX do
    review). Agora é uma leitura dos cartórios escolhidos e o lote do
    ``homonimos_outro_tipo`` — o total não depende do número de atos.
    Devolve ``{chave do ato: aviso}`` só dos atos com homônimo.
    """
    consultas = {}
    chave_numero_por_ato = {}
    cartorios_ids = set()
    for ato in atos:
        chave_numero = f'{ato.chave}/origem/numero'
        if _campo_ausente(linhas, chave_numero):
            continue
        cartorio_id = _cartorio_id_da_linha(linhas, f'{ato.chave}/origem/cartorio')
        if cartorio_id is None:
            continue
        numero = _valor_efetivo(linhas[chave_numero]).strip()
        tipo_linha = linhas.get(f'{ato.chave}/origem/tipo_documento')
        tipo = tipo_da_origem(
            _valor_efetivo(tipo_linha) if tipo_linha is not None else None,
            numero,
        )
        consultas[ato.chave] = (tipo, numero, cartorio_id)
        chave_numero_por_ato[ato.chave] = chave_numero
        cartorios_ids.add(cartorio_id)
    if not consultas:
        return {}
    # Uma leitura para todos os cartórios escolhidos: id que não existe mais
    # (FK obsoleta) fica de fora, como o ``.first()`` que devolvia None.
    cartorios = Cartorios.objects.in_bulk(cartorios_ids)
    homonimos = LancamentoOrigemService.homonimos_outro_tipo(
        {
            chave: (tipo, numero, cartorios[cartorio_id])
            for chave, (tipo, numero, cartorio_id) in consultas.items()
            if cartorio_id in cartorios
        },
        documentos_queryset=documentos_queryset,
    )
    return {
        chave: {
            'chave': chave_numero_por_ato[chave],
            'motivo': MOTIVO_ORIGEM_HOMONIMA,
            'bloqueante': False,
        }
        for chave, homonimo in homonimos.items()
        if homonimo is not None
    }


def avisos(extracao, documentos_queryset=None) -> list[dict]:
    """Campos recomendados pelo tipo efetivo; nunca impedem a revisão.

    Um aviso só por chave: o "livro/folha da origem não consta" (#324) é o
    fato específico e vence o genérico ``requer_*_origem`` da mesma linha.

    ``documentos_queryset`` (o escopo do usuário, ``documentos_for_user``)
    liga a checagem de homônimo de outro tipo (#267); sem ele ela é pulada —
    nada de documento de outra TI participa do aviso.
    """
    linhas, atos = _contexto_revisao(extracao)
    tipos_por_ato, configuracoes = _tipos_efetivos(linhas, atos)
    # Homônimo em lote ANTES do laço: a ordem dos avisos por ato segue a
    # mesma do item a item (logo depois do "não consta" da origem).
    homonimos = (
        _origens_homonimas(linhas, atos, documentos_queryset)
        if documentos_queryset is not None else {}
    )
    resultado = []
    for ato in atos:
        nao_consta = _origem_nao_consta(linhas, ato)
        resultado.extend(nao_consta)
        if documentos_queryset is not None:
            aviso_homonimo = homonimos.get(ato.chave)
            if aviso_homonimo is not None:
                resultado.append(aviso_homonimo)
        ja_avisadas = {item['chave'] for item in nao_consta}
        tipo = configuracoes.get(tipos_por_ato.get(ato.chave))
        if tipo is None:
            continue
        for flag, caminho in (
            ('requer_forma', 'forma'),
            ('requer_observacao', 'observacoes'),
            ('requer_livro_origem', 'origem/livro'),
            ('requer_folha_origem', 'origem/folha'),
            ('requer_data_origem', 'origem/data'),
        ):
            chave = f'{ato.chave}/{caminho}'
            if chave in ja_avisadas:
                continue
            if getattr(tipo, flag) and _campo_ausente(linhas, chave):
                resultado.append({
                    'chave': chave, 'motivo': flag, 'bloqueante': False,
                })
        if tipo.requer_transmissao:
            papeis = {
                _valor_efetivo(campo) for campo in linhas.values()
                if campo.tipo_valor == 'parte'
                and campo.chave.startswith(f'{ato.chave}/partes/')
            }
            if not {'transmitente', 'adquirente'} <= papeis:
                resultado.append({
                    'chave': f'{ato.chave}/partes',
                    'motivo': 'requer_transmissao', 'bloqueante': False,
                })
    return resultado
