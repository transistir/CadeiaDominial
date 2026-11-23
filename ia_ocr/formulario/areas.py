"""Área que não pôde virar hectares (#341/#373): pendência de decisão."""

import re

from dominial.utils.area_br import AreaInvalida, parse_area_br

_CANONICO_TRES_CASAS = re.compile(r'^\s*([0-9]{1,3})[.,]([0-9]{3})\s*$')

from .. import importacao
from ..revisao import MOTIVO_UNIDADE_AREA
from .numeros import _numero_legivel

# Área lida em unidade que não é hectare: o input é em ha, então o valor NÃO
# entra nele (120 m² viraria 120 ha). Mesmo motivo estável da revisão antiga.
MOTIVO_AREA_EM_OUTRA_UNIDADE = MOTIVO_UNIDADE_AREA
ROTULO_DA_AREA = 'Área'
# Enum ``unidade`` do A3 → como o revisor lê a unidade.
UNIDADES_DE_AREA = {'ha': 'ha', 'm2': 'm²', 'alqueires': 'alqueires', 'ares': 'ares'}
TEXTO_AREA_EM_OUTRA_UNIDADE = (
    '{lido} no documento{complemento} — o campo Área (em hectares) ficou '
    'vazio: converta o valor e preencha o campo, ou marque o descarte '
    'explícito abaixo. Nada é convertido ou descartado sem a sua decisão.'
)


def area_para_input(valor):
    """Canônico do ato no formato que o parser único aceita sem ambiguidade.

    O canônico do A3 é **decimal com ponto** (não é entrada de usuário). Se ele
    vier com exatamente 3 casas (``74.675``), o parser do #396 o classificaria
    como ambíguo — correto para o que o usuário digita, errado para o que o
    sistema já resolveu. Aqui só esse caso é normalizado para 4 casas; todo o
    resto passa intacto (``12.50`` continua ``12.50``).
    """
    if valor in (None, ''):
        return None
    texto = valor if isinstance(valor, str) else f'{valor}'
    achado = _CANONICO_TRES_CASAS.match(texto)
    if achado and not achado.group(1).startswith('0'):
        return f'{achado.group(1)}.{achado.group(2)}0'
    return valor


def _unidade_da_area_no_payload(extracao, indice):
    """Código da unidade (``m2``, ``alqueires``...) da área do ato, ou ``None``."""
    payload = extracao.payload_servico or extracao.payload or {}
    atos = payload.get('acts') or []
    ato = atos[indice] if indice < len(atos) else {}
    folha = ato.get('area') if isinstance(ato, dict) else None
    unidade = folha.get('unidade') if isinstance(folha, dict) else None
    return unidade if isinstance(unidade, str) else None


def _area_em_outra_unidade(extracao, indice, linhas, chave):
    """Pendência da área lida em unidade que não é hectare; ``None`` se não há.

    O input do formulário é em hectares. A linha de área marcada com
    ``unidade_area`` (e ainda sem conversão confirmada) traz o número na
    unidade do documento: colocá-lo no input trocaria a unidade em silêncio
    — 120 m² seriam gravados como 120 ha (#341, M3). Quando a unidade é
    explicitamente conversível (``ha``, ``m²``) ou o texto é composto
    hectare/are/centiare, a desnormalização já converte (#373) e este
    motivo nem existe; aqui só chega o que NÃO pôde ser convertido sem
    inventar (``alqueires``, unidade ausente, texto ilegível). Aí o valor
    original vira pendência e quem preenche à mão é o revisor. Linha
    descartada, ou convertida na revisão (``area_convertida``, cujo
    ``valor_final`` já está em ha), segue o caminho normal.
    """
    campo = linhas.get(f'{chave}/area')
    if (
        campo is None or campo.status_revisao == 'descartado'
        or campo.area_convertida
        or MOTIVO_UNIDADE_AREA not in (campo.motivos_revisao or ())
    ):
        return None
    numero = _numero_legivel(campo.normalized)
    unidade = UNIDADES_DE_AREA.get(_unidade_da_area_no_payload(extracao, indice))
    if numero:
        lido = f'{numero} {unidade}' if unidade else numero
        complemento = '' if unidade else ' (unidade não identificada)'
    else:
        # Sem canônico (normalização inválida): o texto como foi lido.
        lido = (campo.raw or '').strip()
        complemento = ''
    if not lido:
        return None
    return {
        'motivo': MOTIVO_AREA_EM_OUTRA_UNIDADE,
        'rotulo': ROTULO_DA_AREA,
        'texto': TEXTO_AREA_EM_OUTRA_UNIDADE.format(
            lido=lido, complemento=complemento,
        ),
        'rotulo_descarte': (
            f'Área lida em {unidade or "unidade não identificada"}, '
            'descartada pelo revisor.'
        ),
        'bloqueante': True,
    }


def area_exige_decisao(extracao, indice, linhas=None):
    """Se o ato tem área não-ha que exige preenchimento ou descarte explícito."""
    linhas = (
        linhas if linhas is not None
        else importacao._linhas_por_chave(extracao)
    )
    chave = f'/acts/{int(indice)}'
    return _area_em_outra_unidade(extracao, int(indice), linhas, chave) is not None
