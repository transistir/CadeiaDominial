"""Pendências bloqueantes da revisão."""

from dominial.models import Cartorios, Pessoas

from .. import destinos, valores
from .estruturas import (
    MOTIVO_CRIAR_NOVO_SEM_NOME, MOTIVO_UNIDADE_AREA, _AREA_DE_ATO,
    _OBRIGATORIOS_ATO, _OBRIGATORIOS_DOCUMENTO,
)
from .linhas import (
    _campo_ausente, _contexto_revisao, _destino_da_linha, _valor_efetivo,
    _valor_para_limite,
)
from .tipos import (
    _caminhos_do_tipo, _tipo_da_origem_sem_leitura, _tipos_efetivos,
)


def pendencias(extracao) -> list[dict]:
    """Bloqueios das linhas incluídas e dos destinos obrigatórios ausentes."""
    linhas, atos = _contexto_revisao(extracao)
    if not atos:
        return [{'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True}]
    return _pendencias_de_linhas(linhas, atos)


def pendencias_sem_atos(extracao) -> list[dict]:
    """Bloqueios de campo do documento mesmo sem atos (issue #262).

    ``pendencias()`` retorna cedo quando ``acts`` está vazio, então os
    bloqueios de campo nunca seriam avaliados. Esta função roda as mesmas
    checagens sobre as linhas existentes, sem exigir atos, para que a
    confirmação "sem atos" não destrave campo obrigatório não revisado.
    """
    linhas, atos = _contexto_revisao(extracao)
    return _pendencias_de_linhas(linhas, atos)


def _pendencias_de_linhas(linhas, atos) -> list[dict]:
    resultado = []

    def adicionar(chave, motivo):
        resultado.append({'chave': chave, 'motivo': motivo, 'bloqueante': True})

    escolhas = [
        campo for campo in linhas.values()
        if campo.tipo_valor in ('parte', 'cartorio')
    ]
    pessoas = set(Pessoas.objects.filter(
        pk__in={campo.pessoa_escolhida_id for campo in escolhas
                if campo.pessoa_escolhida_id}
    ).values_list('pk', flat=True))
    cartorios = set(Cartorios.objects.filter(
        pk__in={campo.cartorio_escolhido_id for campo in escolhas
                if campo.cartorio_escolhido_id}
    ).values_list('pk', flat=True))

    obrigatorios = [f'/document/{nome}' for nome in _OBRIGATORIOS_DOCUMENTO]
    tipos_por_ato, configuracoes = _tipos_efetivos(linhas, atos)
    for ato in atos:
        # P1-2 (#322 rodada 7): com o tipo resolvido pelo resolvedor, o
        # ``tipo_sugerido`` deixa de ser obrigatório — a importação decide
        # pelo tipo efetivo e a tela não precisa pedir um campo que não decide
        # nada. Sem tipo resolvido, continua obrigatório como antes.
        tipo_efetivo = tipos_por_ato.get(ato.chave)
        obrigatorios.extend(
            f'{ato.chave}/{nome}' for nome in _OBRIGATORIOS_ATO
            if nome != 'tipo_sugerido'
            or tipo_efetivo is None
        )
        tipo = configuracoes.get(tipo_efetivo)
        obrigatorios.extend(
            f'{ato.chave}/{caminho}'
            for caminho in _caminhos_do_tipo(tipo_efetivo, tipo)
        )
    ausentes_obrigatorios = [
        chave for chave in obrigatorios if _campo_ausente(linhas, chave)
    ]

    for campo in linhas.values():
        if campo.requer_revisao and campo.status_revisao == 'sugerido':
            adicionar(campo.chave, 'revisao_pendente')
        if campo.tipo_valor in ('parte', 'cartorio'):
            # Papéis de contexto (cônjuge, representante) não viram destino
            # em LancamentoPessoa; exigir escolha ali bloquearia sem uso.
            exige_escolha = (
                campo.tipo_valor == 'cartorio'
                or _valor_efetivo(campo) in destinos.PAPEIS_COM_DESTINO
            )
            if exige_escolha and not (
                campo.pessoa_escolhida_id or campo.cartorio_escolhido_id
                or campo.criar_novo
            ):
                adicionar(campo.chave, 'escolha_pendente')
            elif exige_escolha and (
                (
                    campo.pessoa_escolhida_id
                    and campo.pessoa_escolhida_id not in pessoas
                ) or (
                    campo.cartorio_escolhido_id
                    and campo.cartorio_escolhido_id not in cartorios
                )
            ):
                adicionar(campo.chave, 'decisao_perdida')
        if campo.tipo_valor == 'cartorio' and campo.criar_novo:
            # "Criar novo" sem nome não aponta para cadastro nenhum; vale para
            # cartório obrigatório e opcional (o destino precisa do nome).
            # Se a ausência já vira ``obrigatorio_ausente``, um card não ganha
            # dois motivos.
            valor = _valor_efetivo(campo)
            if (
                campo.chave not in ausentes_obrigatorios
                and (valor is None or (
                    isinstance(valor, str) and not valor.strip()
                ))
            ):
                adicionar(campo.chave, MOTIVO_CRIAR_NOVO_SEM_NOME)
        if (
            'match_invalidado' in campo.motivos_revisao
            and campo.status_revisao == 'sugerido'
        ):
            adicionar(campo.chave, 'match_invalidado')
        if (
            campo.tipo_valor == 'area'
            and _AREA_DE_ATO.fullmatch(campo.chave)
            and MOTIVO_UNIDADE_AREA in campo.motivos_revisao
            and not campo.area_convertida
        ):
            adicionar(campo.chave, MOTIVO_UNIDADE_AREA)
        destino = _destino_da_linha(campo.chave, linhas)
        valor_efetivo = _valor_efetivo(campo)
        if campo.chave.endswith('/tipo_sugerido') and (
            valor_efetivo is None
            or (isinstance(valor_efetivo, str) and not valor_efetivo.strip())
        ):
            motivo = None
        elif _tipo_da_origem_sem_leitura(campo, valor_efetivo):
            motivo = None
        else:
            motivo = valores.validar_destino(destino, valor_efetivo)
        if motivo:
            adicionar(campo.chave, motivo)
        else:
            motivo_limite = valores.validar_limites(
                destino, _valor_para_limite(destino, valor_efetivo), campo,
            )
            if motivo_limite:
                adicionar(campo.chave, motivo_limite)

    for chave in ausentes_obrigatorios:
        adicionar(chave, 'obrigatorio_ausente')
    return resultado
