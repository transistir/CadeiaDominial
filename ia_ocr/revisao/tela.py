"""Agrupamento das linhas nas seções da tela de revisão."""

import copy

from .. import rotulos
from .obrigatorio import (
    _CHAVE_ATO_LOCAL, ROTULOS_CAMPO, _ORDEM_DOCUMENTO, _TEXTO_LONGO,
    _TEXTO_NAO_RECONHECIDO, _ordem_no_formulario_do_ato, rotulo_de_campo,
    rotulo_efetivo,
)


def secoes_da_tela(campos, payload=None, tipos_display=None):
    """Linhas da revisão agrupadas como o formulário de lançamento (#321).

    Ordem das seções: **Documento** (campos do cabeçalho que o formulário
    tem), um bloco por **ato** em ordem REVERSA de ``/acts/{n}`` (título
    ``Ato {rotulo}`` pelo ``rotulo_efetivo``, senão ``Ato {n+1}``),
    **Não reconhecidos** (só quando
    ``rotulos.classificar_atos(payload)`` devolve itens — informativo,
    sem card) e **Outros dados lidos** (o que não é campo do formulário,
    recolhido por padrão na tela). Cada seção devolve
    ``{'tipo', 'titulo', 'chave_ato', 'campos'}``; a de ato ainda traz
    ``tipo_codigo``/``tipo_display`` do ``tipo_exibido`` do resolvedor e
    ``descartado`` da linha estrutural, sempre a primeira do bloco.

    Função PURA — nenhuma query nem alteração das linhas recebidas.
    ``campos`` entra como a view prepara (com ``tipo_exibido`` na linha
    de tipo); além de agrupar, anota em uma cópia de cada
    linha ``rotulo_tela`` (rótulo de negócio), ``grupo_rotulo``
    (``'Partes'``/``'Origem'`` para o cabeçalho do grupo no template) e
    ``texto_longo`` (descrições e campos de texto viram ``<textarea>``).
    """
    documento, outros = [], []
    atos = {}
    linhas = {}
    for campo in campos:
        campo = copy.copy(campo)
        chave = getattr(campo, 'chave', '')
        if isinstance(chave, str):
            linhas[chave] = campo
        campo.rotulo_tela = rotulo_de_campo(chave)
        campo.grupo_rotulo = None
        campo.texto_longo = (
            isinstance(chave, str)
            and chave.rstrip('/').rsplit('/', 1)[-1] in _TEXTO_LONGO
        )
        if isinstance(chave, str) and chave.startswith('/document/'):
            if chave[len('/document/'):] in _ORDEM_DOCUMENTO:
                documento.append(campo)
            else:
                outros.append(campo)
            continue
        achado = (
            _CHAVE_ATO_LOCAL.fullmatch(chave)
            if isinstance(chave, str) else None
        )
        if achado is None:
            outros.append(campo)
            continue
        indice, resto = achado.groups()
        ato = atos.setdefault(
            f'/acts/{indice}', {'tipo': None, 'campos': [], 'descartado': False},
        )
        if not resto:
            # O Incluir desta linha decide o descarte do ato inteiro.
            campo.ordem_formulario = (-1, 0, '', '')
            ato['campos'].append(campo)
            ato['descartado'] = campo.status_revisao == 'descartado'
            continue
        ordem = _ordem_no_formulario_do_ato(resto)
        if ordem is None:
            outros.append(campo)
            continue
        if resto == 'tipo_sugerido':
            ato['tipo'] = getattr(campo, 'tipo_exibido', None) or None
        if resto.startswith('partes/'):
            campo.grupo_rotulo = ROTULOS_CAMPO['partes']
        elif resto == 'origem' or resto.startswith('origem/'):
            campo.grupo_rotulo = ROTULOS_CAMPO['origem']
        campo.ordem_formulario = ordem
        ato['campos'].append(campo)

    secoes = [{
        'tipo': 'documento',
        'titulo': 'Documento',
        'chave_ato': None,
        'campos': sorted(
            documento,
            key=lambda campo: _ORDEM_DOCUMENTO[
                campo.chave[len('/document/'):]
            ],
        ),
    }]
    for chave_ato in sorted(
        atos, key=lambda chave: int(chave.rsplit('/', 1)[1]), reverse=True,
    ):
        ato = atos[chave_ato]
        numero = int(chave_ato.rsplit('/', 1)[1]) + 1
        rotulo = rotulo_efetivo(chave_ato, linhas)
        secoes.append({
            'tipo': 'ato',
            'titulo': f'Ato {rotulo}' if rotulo else f'Ato {numero}',
            'chave_ato': chave_ato,
            'descartado': ato['descartado'],
            'tipo_codigo': ato['tipo'],
            'tipo_display': (
                (tipos_display or {}).get(ato['tipo'])
                if ato['tipo'] else None
            ),
            'campos': sorted(ato['campos'], key=lambda c: c.ordem_formulario),
        })
    if payload is not None:
        nao_reconhecidos = rotulos.classificar_atos(payload).nao_reconhecidos
        if nao_reconhecidos:
            secoes.append({
                'tipo': 'nao_reconhecidos',
                'titulo': 'Não reconhecidos',
                'chave_ato': None,
                'campos': [
                    {
                        'ordem': item.get('ordem'),
                        'rotulo': item.get('rotulo'),
                        'motivo': _TEXTO_NAO_RECONHECIDO.get(
                            item.get('motivo'), 'rótulo não reconhecido',
                        ),
                    }
                    for item in nao_reconhecidos
                ],
            })
    if outros:
        secoes.append({
            'tipo': 'outros',
            'titulo': 'Outros dados lidos',
            'chave_ato': None,
            'campos': outros,
            'pendente': any(getattr(campo, 'pendente', False) for campo in outros),
        })
    return secoes
