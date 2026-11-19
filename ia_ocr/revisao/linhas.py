"""Estado e aplicação das linhas de revisão."""

import hashlib
import json

from django.utils import timezone

from .. import destinos, valores
from .estruturas import (
    EscolhaIncompativel, EscolhaInvalida, MOTIVO_UNIDADE_AREA, _so_digitos,
    linha_ignorada,
)


def versao_linha(campo) -> str:
    """Versão estável do estado revisável da linha, incluindo a autoria temporal."""
    estado = [
        campo.status_revisao,
        campo.valor_final,
        campo.escolha_explicita,
        campo.motivos_revisao,
        campo.pessoa_escolhida_id,
        campo.cartorio_escolhido_id,
        campo.criar_novo,
        campo.area_convertida,
        campo.revisado_em.isoformat() if campo.revisado_em else None,
    ]
    canonico = json.dumps(
        estado, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    )
    return hashlib.sha256(canonico.encode('utf-8')).hexdigest()[:16]


def aplicar_linha(
    campo, *, incluir, valor=None, conferido=False, escolha=None,
    ha_convertido=None, confirmo_conversao=False, usuario=None, agora=None,
):
    """Aplica a revisão em memória e registra autoria só quando algo muda."""
    campos_escolha = (
        'pessoa_escolhida_id', 'cartorio_escolhido_id', 'criar_novo',
    )
    if escolha is not None:
        # Escolher pessoa numa linha de cartório (ou vice-versa) não é uma
        # decisão válida: recusar em vez de deixar a pendência "sumir".
        if (
            campo.tipo_valor == 'parte'
            and escolha.get('cartorio_escolhido_id') is not None
        ) or (
            campo.tipo_valor == 'cartorio'
            and escolha.get('pessoa_escolhida_id') is not None
        ):
            raise EscolhaIncompativel(campo.chave)
        # A tela só oferece quem está em ``match_candidatos``. Um id de fora
        # é estado antigo (identidade mudou e o reload ainda está diferido):
        # aceitá-lo regravaria a pessoa/cartório que o servidor acabou de
        # invalidar.
        candidatos = campo.match_candidatos or []
        for nome in ('pessoa_escolhida_id', 'cartorio_escolhido_id'):
            escolhido = escolha.get(nome)
            if escolhido is not None and escolhido not in candidatos:
                raise EscolhaInvalida(campo.chave)
    antes = versao_linha(campo)

    if not incluir:
        campo.status_revisao = 'descartado'
    elif (
        campo.tipo_valor == 'area'
        and (
            MOTIVO_UNIDADE_AREA in campo.motivos_revisao
            or campo.area_convertida
        )
        and destinos.destino_de(campo.chave) != destinos.SEM_DESTINO
    ):
        if ha_convertido and confirmo_conversao:
            canonico = valores.do_formulario(
                'area', ha_convertido, destinos.destino_de(campo.chave)
            )
            campo.valor_final = canonico
            campo.area_convertida = True
            campo.status_revisao = (
                'aceito' if conferido and canonico == campo.normalized
                else 'editado'
            )
            campo.motivos_revisao = [
                motivo for motivo in campo.motivos_revisao
                if motivo != MOTIVO_UNIDADE_AREA
            ]
        elif ha_convertido is None and not confirmo_conversao:
            campo.area_convertida = False
            campo.valor_final = None
            campo.status_revisao = 'sugerido'
            # Uma conversão limpa volta a exigir decisão sobre a unidade.
            if MOTIVO_UNIDADE_AREA not in campo.motivos_revisao:
                campo.motivos_revisao = [
                    *campo.motivos_revisao, MOTIVO_UNIDADE_AREA,
                ]
        else:
            raise valores.ValorInvalido('conversao_incompleta')
    else:
        # Cartório digitado é texto; escolher um cadastro existente vence o
        # texto (mesmo comportamento de antes: valor_final fica nulo).
        escolha_existente = bool(
            campo.tipo_valor == 'cartorio'
            and escolha is not None
            and not escolha.get('criar_novo')
            and escolha.get('cartorio_escolhido_id')
        )
        if campo.tipo_valor == 'cartorio':
            canonico = (
                campo.normalized if escolha_existente or valor is None else
                valores.do_formulario(
                    'texto', valor, destinos.destino_de(campo.chave)
                )
            )
        else:
            canonico = (
                valores.do_formulario(
                    campo.tipo_valor, valor, destinos.destino_de(campo.chave)
                )
                if valor is not None else campo.normalized
            )
        if valor is None and campo.tipo_valor == 'enum':
            # Conferir/reincluir também valida o valor que será preservado.
            valores.do_formulario(
                'enum',
                _valor_efetivo(campo) if campo.status_revisao == 'descartado' else canonico,
                destinos.destino_de(campo.chave),
            )
        if canonico != campo.normalized:
            campo.status_revisao = 'editado'
            campo.valor_final = canonico
        elif campo.status_revisao == 'descartado' and valor is None:
            # Reincluir sem novo valor recupera a edição preservada.
            campo.status_revisao = (
                'editado' if campo.valor_final is not None else 'sugerido'
            )
        else:
            campo.valor_final = None
            campo.status_revisao = 'aceito' if conferido else 'sugerido'

    if incluir and (valor is not None or conferido):
        # P1 (#322/PR #327): decisão com valor enviado — mesmo IGUAL ao
        # sugerido, caso em que o ``valor_final`` fica nulo — ou conferida
        # marca que o revisor passou pelo card. Descartar e reincluir sem
        # valor não mudam a flag: a escolha anterior continua valendo.
        campo.escolha_explicita = True

    if escolha is not None:
        for nome in campos_escolha:
            if nome in escolha:
                setattr(campo, nome, escolha[nome])
        # Escolher um existente e "criar novo" se excluem: vence o que veio.
        if escolha.get('criar_novo'):
            campo.pessoa_escolhida_id = None
            campo.cartorio_escolhido_id = None
        elif escolha.get('pessoa_escolhida_id') or escolha.get(
            'cartorio_escolhido_id'
        ):
            campo.criar_novo = False

    if versao_linha(campo) != antes:
        campo.revisado_por = usuario
        campo.revisado_em = agora if agora is not None else timezone.now()
    return campo


def _valor_efetivo(campo):
    return campo.valor_final if campo.valor_final is not None else campo.normalized


def _valor_explicito(campo):
    """Valor que o revisor ESCOLHEU de fato, ou None (P1 #322/PR #327).

    Linha descartada não decide; com edição, o ``valor_final``; com o
    sugerido CONFIRMADO (``escolha_explicita``, mesmo com o ``valor_final``
    nulo que a confirmação deixa), o ``normalized``; sem decisão nenhuma,
    None. Fonte única da precedência do tipo — ``tipo_explicito`` do
    ``dados_revisados`` e de ``_tipos_efetivos``.
    """
    if campo is None or campo.status_revisao == 'descartado':
        return None
    if campo.valor_final is not None:
        return campo.valor_final
    if campo.escolha_explicita:
        return campo.normalized
    return None

def _destino_da_linha(chave, linhas):
    """Destino da linha com os valores efetivos de contexto (§2.A, #296).

    A linha de ``documento_identificacao/valor`` só conhece o alvo
    (``Pessoas.rg`` 20 / ``Pessoas.cpf`` 11) com o ``tipo`` efetivo da mesma
    parte; sem ele cai no limite genérico do ``SEM_DESTINO`` e a revisão
    finaliza com valor que a importação (I-6) não consegue gravar.
    """
    campo = linhas.get(chave)
    contexto = [None] if campo is None else [_valor_efetivo(campo)]
    if chave.endswith('/documento_identificacao/valor'):
        tipo = linhas.get(chave.rsplit('/', 1)[0] + '/tipo')
        contexto.insert(0, _valor_efetivo(tipo) if tipo is not None else None)
    return destinos.destino_de(chave, *contexto)


def _valor_para_limite(destino, valor_efetivo):
    """CPF conta apenas os dígitos contra o ``max_length=11`` (#296 item 1).

    A importação grava os dígitos; validar o texto mascarado
    (``123.456.789-00``, 14 caracteres) bloquearia um CPF válido à toa.
    """
    if (
        destino.campo_modelo == 'dominial.Pessoas.cpf'
        and isinstance(valor_efetivo, str)
    ):
        return _so_digitos(valor_efetivo)
    return valor_efetivo


def identidade_parte(chave, linhas):
    """Identidade revisada usada para invalidar a escolha de cadastro da parte."""
    identidade = []
    for sufixo in ('nome', 'documento_identificacao/tipo', 'documento_identificacao/valor'):
        campo = linhas.get(f'{chave}/{sufixo}')
        identidade.append(
            _valor_efetivo(campo)
            if campo is not None and campo.status_revisao != 'descartado' else None
        )
    return tuple(identidade)


def _contexto_revisao(extracao, ignorar_descarte_de=None, por_chave=None):
    """Indexa as linhas incluídas, respeitando o descarte dos ancestrais.

    Linhas com nome em ``LINHAS_IGNORADAS`` (extrações antigas já salvaram
    ``valor_transacao``/``detalhes``) não entram: nem ``dados_revisados``,
    nem ``pendencias``, nem a importação as veem.

    ``ignorar_descarte_de`` (chave de UM ato, ``/acts/N``): a caminhada de
    ancestrais NÃO quebra no descarte DESSA chave — é o contexto com que a
    rodada 12 resolve o tipo do ato DESCARTADO, cujo card continua na
    tela. O descarte das linhas de DENTRO do ato continua valendo (a
    caminhada testa cada linha, a própria inclusive) e os ancestrais
    ACIMA da chave ignorada seguem sendo checados.

    ``por_chave`` (``{chave: campo}`` de ``extracao.campos``): quando vem
    pronto, a leitura de ``extracao.campos.all()`` é pulada —
    ``resolucoes_de_tipo`` monta o dicionário UMA vez e o reusa em todas
    as caminhadas, uma leitura única do banco (rodada 13).
    """
    if por_chave is None:
        por_chave = {campo.chave: campo for campo in extracao.campos.all()}
    incluidas = {}
    for chave, campo in por_chave.items():
        if linha_ignorada(chave):
            continue
        ancestral = chave
        while ancestral:
            if ancestral != ignorar_descarte_de:
                linha = por_chave.get(ancestral)
                if (
                    linha is not None
                    and linha.status_revisao == 'descartado'
                ):
                    break
            ancestral = ancestral.rsplit('/', 1)[0]
        else:
            incluidas[chave] = campo
    atos = [campo for campo in incluidas.values() if campo.tipo_valor == 'ato']
    return incluidas, atos


def _cartorio_id_da_linha(linhas, chave):
    """Cadastro de cartório que a linha escolheu, ou ``None``.

    Fonte única do ``cartorio_id`` da revisão (``dados_revisados`` e o aviso
    de homônimo): "criar novo" não tem cadastro; escolha explícita vence;
    sem escolha, só um candidato único decide.
    """
    campo = linhas.get(chave)
    if campo is None or campo.criar_novo:
        return None
    if campo.cartorio_escolhido_id is not None:
        return campo.cartorio_escolhido_id
    if len(campo.match_candidatos) == 1:
        return campo.match_candidatos[0]
    return None

def _campo_ausente(linhas, chave):
    campo = linhas.get(chave)
    if campo is None:
        return True
    # Escolher um cartório existente resolve a ausência de nome digitado.
    if campo.tipo_valor == 'cartorio' and campo.cartorio_escolhido_id is not None:
        return False
    valor = _valor_efetivo(campo)
    return valor is None or (isinstance(valor, str) and not valor.strip())
