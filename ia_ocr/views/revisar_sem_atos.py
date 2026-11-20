"""Conclusão da revisão sem atos (#262) pela revisão por formulário (#341).

Extraído do ``revisar_extras``. Decisão do dono (#341, PR #366, opção a):
sem atos nada é importado, então a conclusão não exige a revisão dos campos
de cabeçalho — a tela é só a confirmação. A regra mora no serviço
(``services.pode_finalizar_sem_atos`` / ``services.finalizar_revisao``):
flag ligada, serviço com ``acts: []`` e a única pendência ``nenhum_ato``.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .. import estados, revisao_ato, services, views
from ..estados import TransicaoConcorrente, TransicaoInvalida
from .jobs import _contexto_job, _kwargs_job
from .resposta import _url_tela
from .revisar_extras import _url_documento

logger = logging.getLogger(__name__)

MENSAGEM_SEM_ATOS_CONCLUIDA = (
    '✅ Revisão concluída: a extração foi finalizada sem atos.'
)


def destino_sem_atos(request, tis, imovel, documento, job, extracao,
                     kwargs_job):
    """Resposta do ramo sem atos da entrada; ``None`` volta ao ramo antigo.

    O chamador já garantiu ``job.status`` em ``extraido/revisado`` e que
    ``atos_da_revisao`` é vazio. Só oferece a confirmação quando o serviço
    a aceitaria — nunca uma ação que não pode vencer.
    """
    if job.status != estados.EXTRAIDO:
        return None
    if not services.pode_finalizar_sem_atos(extracao):
        return None
    return renderizar_sem_atos(
        request, tis, imovel, documento, job, extracao, kwargs_job,
    )


def renderizar_sem_atos(request, tis, imovel, documento, job, extracao,
                        kwargs_job):
    """GET da confirmação "concluir sem atos" (#262) pela revisão (#341).

    O POST desta página é ``revisar_sem_atos_ocr``, que revalida o
    ``versao`` sob trava.
    """
    return views.render(request, 'ia_ocr/revisao_sem_atos.html', {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'job': job,
        'extracao': extracao,
        'versao': services.versao_bloco(extracao),
        'url_sem_atos': reverse('revisar_sem_atos_ocr', kwargs=kwargs_job),
        'url_texto': _url_tela(kwargs_job),
        'url_documento': _url_documento(tis, imovel, documento),
    })


@login_required
@require_POST
def revisar_sem_atos_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Conclui a revisão sem atos (#262).

    O ``versao`` exibido no GET valida o estado sob trava; o serviço é
    atômico — em qualquer falha nada é gravado.
    """
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id,
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)
    entrada = reverse('revisar_job_ocr', kwargs=kwargs_job)
    # Sem o token que a tela exibiu, não há como saber se a revisão mudou:
    # ``finalizar_revisao`` com ``versao_cliente=None`` dispensaria a
    # comparação — exatamente o que um POST malformado não pode ganhar.
    versao = request.POST.get('versao')
    if not isinstance(versao, str) or not versao:
        return HttpResponseBadRequest('Campo "versao" ausente ou inválido.')
    extracao = job.extracao_vigente()
    if extracao is None:
        raise Http404('Extração indisponível.')
    # A rota é só do caso sem atos (achado do Opus no review da #341):
    # concluir por aqui pularia a revisão de cada ato.
    if revisao_ato.atos_da_revisao(extracao):
        raise Http404('A rota sem atos não se aplica a esta extração.')
    try:
        services.finalizar_revisao(
            extracao, request.user, versao_cliente=versao,
            confirmar_sem_atos=True,
        )
    except services.ConflitoVersao:
        messages.warning(request, (
            '⚠️ A revisão mudou depois que esta página foi aberta; '
            'recarregue. Nada foi gravado.'
        ))
        return redirect(entrada)
    except services.RevisaoIncompleta:
        messages.warning(request, (
            '⚠️ Esta extração tem pendências além da ausência de atos; '
            'revise o documento antes de concluir. Nada foi gravado.'
        ))
        return redirect(entrada)
    except (services.ExtracaoRecusada, TransicaoInvalida, TransicaoConcorrente):
        messages.error(
            request,
            'Este processamento não permite concluir no estado atual.',
        )
        return redirect(entrada)
    messages.success(request, MENSAGEM_SEM_ATOS_CONCLUIDA)
    return redirect(_url_documento(tis, imovel, documento))
