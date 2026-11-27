"""Banner da revisão em DOIS grupos: bloqueios × avisos (#332).

O grupo bloqueante mostra o que o próximo "salvar" recusaria. Sem rascunho
(GET), é o que o pré-preenchimento consegue provar — início sem origem/data e
a área sem decisão. Com rascunho (POST recusado ou restaurado da sessão, sempre
um ``QueryDict``), vale o POST: o que o usuário já resolveu sai do banner.

O grupo informativo nunca impede a gravação; ele é o que fica registrado no
lançamento para correção posterior (``avisos_registrados``).

O checkbox de descarte da área aparece nos DOIS grupos, enquanto a decisão
estiver pendente: no bloqueante com o valor vazio e no informativo quando o
rascunho já marcou o descarte. Ele nunca some no reenvio — era o trap da #320.
"""

from .. import importacao, revisao
from ..classe_pendencia import eh_bloqueante
from ..formulario import input_do_campo
from .bloqueios import (
    MOTIVO_AREA_SEM_DECISAO, bloqueios_do_post_itens, bloqueios_do_prefill,
)

MOTIVO_AREA_DESCARTADA = 'area_descartada'
MOTIVO_REQUER_TRANSMISSAO = 'requer_transmissao'


def avisos_do_formulario(prefill, extracao, indice, post=None):
    """Informativos do ato sem a pendência de área (tratada à parte).

    Com ``post`` (rascunho), o mesmo filtro do snapshot: o ``requer_*`` que o
    revisor já preencheu deixa de aparecer e de ser registrado.
    """
    avisos = [
        item for item in prefill.get('pendencias', ())
        if not eh_bloqueante(item['motivo'])
        and item['motivo'] != MOTIVO_AREA_SEM_DECISAO
    ]
    avisos.extend(_avisos_da_revisao(extracao, indice, post))
    return _dedupe_por_motivo(avisos)


def aviso_resolvido_no_post(aviso, post):
    """Se o input que o aviso pede já veio preenchido no POST.

    Só vale para ``requer_*`` (informativo de campo recomendado) e para
    ``requer_transmissao``. ``*_nao_consta`` e ``lido_sem_campo`` nunca são
    descartados; ``origem/data`` não tem input e por isso permanece.
    """
    if post is None:
        return False
    motivo = aviso.get('motivo') or ''
    if motivo == MOTIVO_REQUER_TRANSMISSAO:
        return _transmissao_preenchida(post)
    chave = aviso.get('chave') or ''
    if not motivo.startswith('requer_') or chave.endswith('/origem/data'):
        return False
    nome = input_do_campo(chave)
    if nome is None:
        return False
    nomes = [nome]
    if chave.endswith('/forma'):
        nomes.append('forma_averbacao')
    return any(_campo_preenchido(post, item) for item in nomes)


def _campo_preenchido(post, nome):
    return bool(
        (post.get(nome) or '').strip()
        or (post.get(f'{nome}[]') or '').strip()
    )


def _transmissao_preenchida(post):
    transmitente = (
        _campo_preenchido(post, 'transmitente')
        or _campo_preenchido(post, 'transmitente_nome')
    )
    adquirente = (
        _campo_preenchido(post, 'adquirente')
        or _campo_preenchido(post, 'adquirente_nome')
    )
    return transmitente and adquirente


def _dedupe_por_motivo(avisos):
    vistos = set()
    resultado = []
    for aviso in avisos:
        motivo = aviso.get('motivo')
        if motivo in vistos:
            continue
        vistos.add(motivo)
        resultado.append(aviso)
    return resultado


def grupos_do_banner(prefill, extracao, indice, rascunho=None):
    """``{'bloqueios': [...], 'avisos': [...]}`` do banner do ato ``indice``.

    Sem rascunho (GET): bloqueios do prefill (início sem origem/data) mais as
    pendências bloqueantes; avisos informativos do prefill mais
    ``revisao.avisos`` filtrados ao ato. Com rascunho (POST recusado ou
    sessão): só os bloqueios do POST — o que ainda falta para salvar.
    """
    indice = int(indice)
    if rascunho is None:
        pendencias = list(prefill.get('pendencias', ()))
        bloqueios = bloqueios_do_prefill(prefill)
        bloqueios.extend(
            item for item in pendencias if eh_bloqueante(item['motivo'])
        )
        avisos = avisos_do_formulario(prefill, extracao, indice)
    else:
        linhas = importacao._linhas_por_chave(extracao)
        bloqueios = bloqueios_do_post_itens(
            rascunho, extracao, indice, linhas,
        )
        avisos = avisos_do_formulario(prefill, extracao, indice, post=rascunho)
        avisos.extend(_area_descartada(prefill, rascunho))
        avisos = _dedupe_por_motivo(avisos)
    return {'bloqueios': bloqueios, 'avisos': avisos}


def _area_descartada(prefill, post):
    """Checkbox da área preservado quando o rascunho já a descartou."""
    if post.get('descartar_area') != '1':
        return []
    area = next(
        (item for item in prefill.get('pendencias', ())
         if item['motivo'] == 'unidade_area'),
        None,
    )
    if area is None:
        return []
    rotulo_descarte = area.get('rotulo_descarte', '')
    return [{
        'motivo': MOTIVO_AREA_DESCARTADA,
        'rotulo': area['rotulo'],
        'texto': rotulo_descarte,
        'rotulo_descarte': rotulo_descarte,
    }]


def _avisos_da_revisao(extracao, indice, post=None):
    """``revisao.avisos`` do ato, já descritos em texto de negócio.

    ``post`` descarta o ``requer_*`` que o revisor já preencheu — a mesma
    regra usada no snapshot persistido.
    """
    chave = f'/acts/{int(indice)}'
    resultado = []
    for aviso in revisao.avisos(extracao):
        chave_do_aviso = aviso.get('chave') or ''
        if chave_do_aviso != chave and not chave_do_aviso.startswith(
            f'{chave}/',
        ):
            continue
        if aviso_resolvido_no_post(aviso, post):
            continue
        descrito = revisao.descrever_aviso(aviso)
        resultado.append({
            'motivo': descrito['motivo'],
            'rotulo': descrito['rotulo'],
            'texto': descrito.get('local', ''),
        })
    return resultado
