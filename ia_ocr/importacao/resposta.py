"""Leitura de linhas e rótulo efetivo, compartilhadas com a revisão."""
from .. import revisao


def _linhas_por_chave(extracao):
    return {campo.chave: campo for campo in extracao.campos.all()}


def _rotulo_efetivo(chave, linhas):
    """Rótulo que DECIDE tipo/número na gravação: ``valor_final``,
    ``normalized`` ou ``raw``.

    P1 (#322 rodada 4): no payload real o rótulo chega com
    ``normalized=None`` e o carimbo no ``raw`` — a linha estrutural do ato
    (``/acts/N``, a que o ``_rotulo`` exibe) só guarda o ``normalized``, e
    ler só ela escondia o rótulo: o ``tipo_sugerido`` decidia sozinho, a
    gravação divergia do ``classificar_atos`` (que lê ``normalized or
    raw``) e a duplicata que a base bloqueava passava. O ``raw`` vive na
    FOLHA ``/acts/N/rotulo`` (linha de conferência, ``SEM_DESTINO``), que
    traz os dois campos do payload.

    P1 (#322 rodada 5): o rótulo CORRIGIDO pelo revisor (``valor_final``)
    vence — sem ele a correção feita na tela era ignorada e a gravação
    decidia pelo carimbo do OCR que ficou no ``normalized``/``raw``.
    ``valor_final`` VAZIO (revisor limpou o campo: ``aplicar_linha``
    grava ``''``) não decide nada — a leitura cai no ``normalized``/``raw``
    de antes.

    P1 (#322 rodada 6): linha DESCARTADA não decide — ``aplicar_linha``
    com ``incluir=False`` preserva o ``valor_final`` da edição e só marca
    ``descartado``; ler o valor sem olhar o status deixava a edição
    descartada vencer e a gravação criava o lançamento que o usuário tinha
    descartado. Descarte PULA o candidato (mesma convenção de
    ``revisao.identidade_parte``): a folha descartada cai na linha
    estrutural e a estrutural descartada cai na folha; as duas
    descartadas não decidem nada.

    Devolve, na folha e, sem ela, na linha estrutural, o primeiro não
    vazio entre ``valor_final``, ``normalized`` e ``raw`` — ``None``
    quando nada existe (o parser devolve ``reconhecido=False`` e o
    ``tipo_sugerido`` decide). A leitura é a MESMA da revisão
    (``revisao.rotulo_efetivo``, #322 rodada 7): uma única regra decide o
    tipo nos dois caminhos.
    """
    return revisao.rotulo_efetivo(chave, linhas)
