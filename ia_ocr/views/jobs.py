"""Tela split-view do texto OCR (``texto_job_ocr``) e os helpers de
contexto da hierarquia TI→Imóvel→Documento→job.

Extraídos do monólito de views (etapa 3, limite de 400 linhas).
``render`` e ``_disponibilidade_extracao`` são chamados VIA O PACOTE
(``views.render``, ``views._disponibilidade_extracao``): os testes fazem
``mock.patch('ia_ocr.views.render')`` e
``mock.patch('ia_ocr.views._disponibilidade_extracao')``
(``test_texto_views.py``), e o patch só vale se o call site resolver o
nome no objeto do pacote, a cada chamada. Todo outro helper de outro
módulo do pacote vem por import direto do dono e é chamada direta. Ver o
docstring do ``__init__.py``.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET

from dominial.views.documento_digital_views import _get_contexto_documento

from .. import estados, services, views
from ..diff import segmentos_diff
from ..models import (
    ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA, OcrJob, OcrJobTransicao,
)
from .resposta import _pagina_pedida, _url_tela


def _sem_atos_elegivel(extracao) -> bool:
    """Flag ligada e a única coisa que falta são os atos (issue #262)."""
    return services.pode_finalizar_sem_atos(extracao)


def _contexto_job(request, tis_id, imovel_id, documento_id, job_id):
    """TI, imóvel, documento e job, validando a hierarquia completa."""
    tis, imovel, documento = _get_contexto_documento(
        request, tis_id, imovel_id, documento_id
    )
    job = get_object_or_404(
        OcrJob.objects.select_related('documento_digital'),
        job_id=job_id, documento_digital__documento=documento,
    )
    return tis, imovel, documento, job


def _kwargs_job(tis, imovel, documento, job):
    return {
        'tis_id': tis.pk,
        'imovel_id': imovel.pk,
        'documento_id': documento.pk,
        'job_id': job.job_id,
    }


@login_required
@require_GET
def texto_job_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Split-view: PDF original à esquerda, texto da página à direita."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)

    if job.status not in estados.STATUS_COM_TEXTO:
        messages.info(request, 'O texto deste processamento ainda não está disponível.')
        return redirect(
            'upload_documento_digital',
            tis_id=tis.pk, imovel_id=imovel.pk, documento_id=documento.pk,
        )

    paginas = list(job.paginas.select_related('confirmado_por').defer('blocos'))
    if not paginas:
        raise Http404('Processamento sem páginas.')
    atual = _pagina_pedida(request, paginas)
    indice = paginas.index(atual)

    abas = [
        {
            'numero': pagina.numero_pagina,
            'pagina': pagina,
            'url': _url_tela(kwargs_job, pagina.numero_pagina),
            'atual': pagina.pk == atual.pk,
        }
        for pagina in paginas
    ]
    url_pdf = reverse('servir_documento_digital', kwargs={
        'tis_id': tis.pk,
        'imovel_id': imovel.pk,
        'documento_id': documento.pk,
        'arquivo_id': job.documento_digital_id,
    })
    acao = {'numero': atual.numero_pagina}
    editavel = job.status in estados.STATUS_REVISAVEIS
    nao_confirmadas = [p for p in paginas if p.estado == ESTADO_NAO_CONFIRMADA]
    editadas = [p for p in paginas if p.estado == ESTADO_EDITADA]
    confirmadas = len(paginas) - len(nao_confirmadas) - len(editadas)
    pode_extrair, motivo_sem_extracao = views._disponibilidade_extracao(job, paginas)
    # #314: um clique do upload ao formulário — a tela submete sozinha o
    # "Extrair campos" quando ainda não há extração (o POST segue o fluxo normal).
    auto_extrair = bool(
        pode_extrair and editavel and job.extracao_vigente() is None
    )

    return views.render(request, 'ia_ocr/confirmacao_texto.html', {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'arquivo': job.documento_digital,
        'job': job,
        'pagina': atual,
        'texto_atual': atual.texto_exibido,
        'diff': (
            segmentos_diff(atual.texto_ocr, atual.texto_confirmado)
            if atual.tem_edicao else None
        ),
        'abas': abas,
        'anterior': abas[indice - 1] if indice > 0 else None,
        'proxima': abas[indice + 1] if indice + 1 < len(abas) else None,
        'total': len(paginas),
        'confirmadas': confirmadas,
        'faltam': len(nao_confirmadas) + len(editadas),
        'todas_confirmadas': confirmadas == len(paginas),
        'pode_extrair': pode_extrair,
        'auto_extrair': auto_extrair,
        'motivo_sem_extracao': motivo_sem_extracao,
        # Bulk só quando há o que confirmar e o usuário não editou nada.
        'tem_editadas': bool(editadas),
        'pode_confirmar_todas': editavel and bool(nao_confirmadas) and not editadas,
        'editavel': editavel,
        'confirmacao_texto': (
            None if editavel else
            OcrJobTransicao.objects
            .filter(ocr_job=job, para_status=estados.TEXTO_CONFIRMADO)
            .select_related('usuario').order_by('criado_em').first()
        ),
        'url_pdf': url_pdf,
        'url_pdf_pagina': f'{url_pdf}#page={atual.numero_pagina}',
        'url_confirmar': reverse(
            'confirmar_pagina_ocr', kwargs={**kwargs_job, **acao}
        ),
        'url_editar': reverse('editar_pagina_ocr', kwargs={**kwargs_job, **acao}),
        'url_confirmar_todas': reverse('confirmar_paginas_ocr', kwargs=kwargs_job),
        'url_reprocessar': reverse('reprocessar_job_ocr', kwargs=kwargs_job),
        'url_extrair_campos': reverse('extrair_campos_ocr', kwargs=kwargs_job),
        'url_campos': reverse('campos_job_ocr', kwargs=kwargs_job),
    })
