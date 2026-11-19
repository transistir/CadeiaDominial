"""Resolução do tipo efetivo dos atos."""

import re

from dominial.models import LancamentoTipo

from ..rotulos import resolver_tipo, tipo_do_rotulo
from .estruturas import _eh_folha
from .linhas import _contexto_revisao, _valor_explicito
from .obrigatorio import rotulo_efetivo


def _tipo_do_rotulo_do_ato(linhas, ato):
    """Tipo que o rótulo efetivo do ato declara (só R/Av), ou None."""
    return tipo_do_rotulo(rotulo_efetivo(ato.chave, linhas))


def _rotulo_do_payload(ato):
    """Rótulo do payload A3 (``normalized`` → ``raw``), ou None.

    Mesma leitura do ``classificar_atos``/``_rotulo_efetivo`` antes de as
    linhas existirem (``desnormalizar``).
    """
    rotulo = ato.get('rotulo') if isinstance(ato, dict) else None
    if not isinstance(rotulo, dict):
        return None
    if rotulo.get('normalized') is not None:
        return rotulo['normalized']
    return rotulo.get('raw')

def tipo_da_origem(tipo_informado, numero):
    """Tipo documental da origem: o informado, ou inferido do prefixo M/T.

    A MESMA regra da importação (que delega para cá): sem tipo válido, ``T…``
    é transcrição e o resto — inclusive só dígitos — é matrícula.
    """
    if tipo_informado in ('matricula', 'transcricao'):
        return tipo_informado
    return 'transcricao' if (numero or '')[:1].upper() == 'T' else 'matricula'

def _resolver_tipo_do_ato(linhas, ato):
    """``(tipo, origem)`` de UM ato pela precedência única (rodada 10).

    Lê as linhas do ato (escolha explícita, rótulo efetivo, sugestão) e
    delega a ``rotulos.resolver_tipo``, que já devolve a origem. Reusado
    por ``_tipos_efetivos`` e ``resolucoes_de_tipo``: a view NÃO recalcula
    a precedência — a cópia que existia lá divergia em dois estados
    alcançáveis (linha de tipo descartada e valor explícito fora de
    ``TIPOS_SUGERIDOS``, P2 do review Opus #322/PR #327).
    """
    campo_tipo = linhas.get(f'{ato.chave}/tipo_sugerido')
    tipo_explicito = _valor_explicito(campo_tipo)
    rotulo_txt = rotulo_efetivo(ato.chave, linhas)
    tipo_sug = (
        campo_tipo.normalized
        if campo_tipo is not None
        and campo_tipo.status_revisao != 'descartado'
        else None
    )
    tipo, _divergencia, origem = resolver_tipo(
        tipo_explicito, rotulo_txt, tipo_sug,
    )
    return tipo, origem


def _tipos_efetivos(linhas, atos):
    """Tipo efetivo de cada ato segundo a precedência (#322 rodada 7).

    A escolha EXPLÍCITA do usuário não pode ser sobrescrita pelo rótulo
    (precedência em ``_resolver_tipo_do_ato`` → ``rotulos.resolver_tipo``):
    1. /acts/N/tipo_sugerido com escolha do revisor (``_valor_explicito`` —
       edição em ``valor_final`` ou sugestão confirmada na flag, P1 da
       #322/PR #327);
    2. Rótulo efetivo com prefixo R/Av (valor_final -> normalized -> raw);
    3. /acts/N/tipo_sugerido normalizado.

    A MESMA regra é compartilhada com importacao._resolver_tipo_e_numero
    através de rotulos.resolver_tipo.
    """
    tipos_por_ato = {}
    for ato in atos:
        tipo, _origem = _resolver_tipo_do_ato(linhas, ato)
        tipos_por_ato[ato.chave] = tipo
    configuracoes = {}
    for tipo in LancamentoTipo.objects.filter(
        tipo__in={t for t in tipos_por_ato.values() if t is not None}
    ).order_by('pk'):
        configuracoes.setdefault(tipo.tipo, tipo)
    return tipos_por_ato, configuracoes


def resolucoes_de_tipo(extracao):
    """``{chave do ato: (tipo | None, origem)}`` — resolução por ato.

    P2 (#322/PR #327, rodada 10): o ``tipo_exibido`` do card sai DAQUI,
    não de uma cópia da precedência na view. A ``origem`` é a de
    ``rotulos.resolver_tipo`` ('explicito', 'limpo', 'rotulo', 'sugerido',
    'nenhum'): só ela distingue o select APAGADO ('limpo' → o card exibe
    vazio, P2-1) do tipo resolvido que a importação vai usar.

    Rodada 12 (review Opus r11): TODO ato tem entrada, inclusive o
    DESCARTADO — o card dele continua na tela com o checkbox de
    reinclusão, e o select precisa marcar o que a importação usaria ao
    reincluir. A resolução é a do MESMO ``_resolver_tipo_do_ato``, no
    contexto que ignora apenas o descarte do próprio ato: o fallback de
    ``valor_final``/``normalized`` que a view fazia divergia do resolvedor
    no rótulo divergente sem escolha, no valor explícito fora do contrato
    e na linha de tipo descartada.

    Custo (rodada 13, P2 Greptile): O(N + D × N) no pior caso de
    caminhada — N linhas, D atos descartados, cada um rewalks os
    ancestrais no contexto que ignora só o descarte dele — mas com UMA
    leitura única de ``extracao.campos``: ``por_chave`` é montado uma
    vez e reusado na caminhada inicial e nas D caminhadas dos
    descartados. O ``assertNumQueries`` de ``ResolucoesDeTipoCustoTest``
    trava essa leitura única (a contagem não cresce com D).
    """
    por_chave = {campo.chave: campo for campo in extracao.campos.all()}
    linhas, atos = _contexto_revisao(extracao, por_chave=por_chave)
    resolucoes = {
        ato.chave: _resolver_tipo_do_ato(linhas, ato)
        for ato in atos
    }
    for ato in por_chave.values():
        # Fora de ``resolucoes`` só resta o ato descartado: a caminhada de
        # ``_contexto_revisao`` exclui o ramo inteiro dele.
        if ato.tipo_valor != 'ato' or ato.chave in resolucoes:
            continue
        linhas_do_ato, _ = _contexto_revisao(
            extracao, ignorar_descarte_de=ato.chave, por_chave=por_chave,
        )
        resolucoes[ato.chave] = _resolver_tipo_do_ato(linhas_do_ato, ato)
    return resolucoes


def tipos_efetivos(extracao):
    """Tipo efetivo de cada ato da extração: {chave do ato: tipo | None}.

    P2-2 (#322/PR #327): a tela de revisão precisa mostrar o MESMO tipo
    que as pendências e a importação resolvem — este é o acesso público
    da MESMA regra (``_contexto_revisao`` + ``_tipos_efetivos``) para a
    view montar o ``tipo_exibido`` do card.

    P3-2 (review Opus, rodada 13): o mapa devolve também atos
    DESCARTADOS (rodada 12) — a importação não os grava; consumidor
    novo que só queira atos válidos precisa filtrar o
    ``status_revisao`` da linha do ato.
    """
    return {
        chave: tipo
        for chave, (tipo, _origem) in resolucoes_de_tipo(extracao).items()
    }


def _caminhos_do_tipo(tipo_efetivo, configuracao):
    """Campos que o tipo efetivo exige, pelos mesmos ``requer_*`` do modelo.

    Só destinos criáveis: ``tipo_sugerido``/``data`` já são tratados por
    ``_OBRIGATORIOS_ATO``. ``inicio_matricula`` exige cartório de origem
    mesmo que a configuração desligue o flag (mesma regra de
    ``Lancamento.clean`` e de ``pendencias``).
    """
    caminhos = []
    if configuracao is not None:
        if configuracao.requer_titulo:
            caminhos.append('titulo')
        if configuracao.requer_descricao:
            caminhos.append('descricao')
    if (
        tipo_efetivo == 'inicio_matricula'
        or (configuracao is not None and configuracao.requer_cartorio_origem)
    ):
        caminhos.append('origem/cartorio')
    return tuple(caminhos)


def _tem_folha(no, caminho):
    """O caminho termina numa folha editável (objeto com ``normalized``)?"""
    for parte in caminho.split('/'):
        if not isinstance(no, dict):
            return False
        no = no.get(parte)
    return _eh_folha(no)

_TIPO_DA_ORIGEM = re.compile(r'/acts/\d+/origem/tipo_documento')


def _tipo_da_origem_sem_leitura(campo, valor_efetivo):
    """``origem/tipo_documento`` que a leitura nunca trouxe e segue vazio.

    Enum vazio é ``valor_incompativel_destino`` para quem LEU um tipo e o
    apagou (decisão do revisor, fixada pelos testes da tela). O campo que
    nasceu vazio (#324: linha criada só para o revisor poder preencher) é
    outra coisa: a importação infere o tipo pelo prefixo M/T do número
    (``_tipo_documento_da_origem``), então vazio é ausência de informação.

    "Nunca trouxe" é ``raw`` E ``normalized`` ausentes: um tipo que a IA LEU
    (``raw`` presente) mas não conseguiu normalizar não é isento — esvaziá-lo
    cai na regra normal, não num placeholder vazio silencioso.
    """
    return (
        campo.raw is None
        and campo.normalized is None
        and _TIPO_DA_ORIGEM.fullmatch(campo.chave) is not None
        and (
            valor_efetivo is None
            or (isinstance(valor_efetivo, str) and not valor_efetivo.strip())
        )
    )
