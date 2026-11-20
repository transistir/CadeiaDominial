"""Finalização da revisão: transição para ``revisado`` e paliativa "sem atos".
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .. import estados
from ..models import ExtracaoSugerida
from ..revisao import pendencias
from .blocos import (
    _com_bloqueios_de_campo, _travar_extracao_revisao, versao_bloco,
)
from .erros import ConflitoVersao, ExtracaoRecusada, RevisaoIncompleta


def pode_finalizar_sem_atos(extracao, bloqueios=None) -> bool:
    """Flag ligada e a única coisa que falta são os atos (issue #262).

    A paliativa existe porque o **serviço** devolve ``acts: []``. Se
    ``payload_servico`` traz atos, a ausência na tela vem de descarte do
    revisor — finalizar "sem atos" seria falso — e atos descartados pelo
    revisor não contam para liberar a finalização.

    Decisão do dono (#341, PR #366, opção a): a conclusão NÃO exige a
    revisão dos campos de cabeçalho. Sem atos nada é gravado em
    ``Documento``/``Lancamento``, então campo de cabeçalho não revisado (ou
    sem escolha de cadastro) não é dado perdido. A revisão do cabeçalho vale
    para o caminho COM atos (formulário do ato).
    """
    if not getattr(settings, 'OCR_PERMITIR_FINALIZAR_SEM_ATOS', False):
        return False
    payload = extracao.payload_servico
    if payload is None or payload.get('acts'):
        return False
    if bloqueios is None:
        bloqueios = pendencias(extracao)
    return (
        bool(bloqueios)
        and all(item['motivo'] == 'nenhum_ato' for item in bloqueios)
    )


def finalizar_revisao(
    extracao, usuario, versao_cliente=None, confirmar_sem_atos=False,
) -> ExtracaoSugerida:
    """Finaliza a revisão vigente sem pendências e audita uma única transição.

    `versao_cliente` é o token que a tela exibiu; divergir do bloco travado é
    conflito. None (chamada interna) dispensa a comparação.

    Issue #262 (I-5): enquanto o serviço devolve ``acts: []``, a pendência
    ``nenhum_ato`` continua existindo (é visível na tela e no histórico). A
    flag ``OCR_PERMITIR_FINALIZAR_SEM_ATOS`` só destrava a finalização quando
    o revisor confirma explicitamente (``confirmar_sem_atos``) e TODAS as
    pendências restantes são ``nenhum_ato`` — nunca fabrica atos nem descarta
    outra pendência. A transição é auditada com motivo próprio.
    """
    with transaction.atomic():
        travada = _travar_extracao_revisao(extracao)
        # Finalizar não muda o token: o reenvio da mesma tela ainda casa.
        if versao_cliente is not None and versao_cliente != versao_bloco(travada):
            # Sem versões por linha no corpo, não há chave a apontar.
            raise ConflitoVersao([])
        # Uma repetição chega com o job já revisado (ou importado).
        if travada.finalizada_em is not None:
            return travada
        job = travada.ocr_job
        if job.status != estados.EXTRAIDO:
            raise ExtracaoRecusada('estado_invalido')
        bloqueios = pendencias(travada)
        sem_atos = (
            confirmar_sem_atos is True
            and pode_finalizar_sem_atos(travada, bloqueios)
        )
        if bloqueios and not sem_atos:
            # O 422 precisa explicar também os bloqueios de campo que
            # ``pendencias()`` esconde atrás de ``nenhum_ato``.
            raise RevisaoIncompleta(
                _com_bloqueios_de_campo(bloqueios, travada)
            )

        travada.finalizada_em = timezone.now()
        travada.finalizada_por = usuario
        travada.save(update_fields=['finalizada_em', 'finalizada_por'])
        job.transicionar(
            estados.REVISADO, usuario=usuario,
            motivo=(
                'revisao_finalizada_sem_atos' if sem_atos
                else 'revisao_finalizada'
            ),
        )
    return travada
