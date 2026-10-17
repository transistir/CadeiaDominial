"""Telas da app ia_ocr: confirmação do texto OCR (issue #261 / I-4).

Mesma política de acesso do upload digital: ``login_required`` + hierarquia
TI→Imóvel→Documento (``_get_contexto_documento``); fora do escopo → 404, o
padrão do projeto. As mutações são POST com redirect de volta à tela (PRG) e
delegam a ``ia_ocr.services``: a view nunca grava página nem transiciona o job
diretamente. Nenhum log daqui carrega texto de documento ou nome de arquivo
(PII).
"""

import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

# Hierarquia TI→Imóvel→Documento: a mesma do upload digital (reuso, não cópia).
from dominial.views.documento_digital_views import _get_contexto_documento

from . import estados, services
from .diff import segmentos_diff
from .estados import TransicaoConcorrente, TransicaoInvalida
from .models import (
    ESTADO_CONFIRMADA, ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA, OcrJob,
    OcrJobTransicao, PaginaOcr,
)


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


def _url_tela(kwargs_job, numero=None):
    url = reverse('texto_job_ocr', kwargs=kwargs_job)
    return f'{url}?pagina={numero}' if numero else url


def _numero_pagina(bruto):
    """Número de página vindo da requisição, ou None se não for um.

    Limita a 6 dígitos: int() de string gigante levanta ValueError no Python
    3.11+ (e nenhum documento tem tantas páginas — acima disso é 404 de todo jeito).
    """
    if bruto is not None and re.fullmatch(r'[0-9]{1,6}', bruto):
        return int(bruto)
    return None


def _destino(request, kwargs_job):
    """Tela de volta das ações gerais, na página em que o usuário estava."""
    return _url_tela(kwargs_job, _numero_pagina(request.POST.get('pagina')))


def _pagina_pedida(request, paginas):
    """Página do ``?pagina=N``; sem parâmetro, retoma na primeira pendente."""
    bruto = request.GET.get('pagina')
    if bruto is None:
        return next(
            (p for p in paginas if p.estado != ESTADO_CONFIRMADA), paginas[0]
        )
    numero = _numero_pagina(bruto)
    if numero is None:
        raise Http404('Página inválida.')
    for pagina in paginas:
        if pagina.numero_pagina == numero:
            return pagina
    raise Http404('Página inexistente.')


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

    return render(request, 'ia_ocr/confirmacao_texto.html', {
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


@login_required
@require_POST
def confirmar_pagina_ocr(request, tis_id, imovel_id, documento_id, job_id, numero):
    """Confirma a página: grava texto_confirmado + quem/quando (auditoria)."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    destino = _url_tela(_kwargs_job(tis, imovel, documento, job), numero)
    try:
        _pagina, alterada = services.confirmar_pagina(
            job, numero, request.user, texto=request.POST.get('texto'),
        )
    except PaginaOcr.DoesNotExist:
        raise Http404('Página inexistente.')
    except services.TextoNaoEditavel:
        messages.error(
            request, 'Este processamento não aceita mais alterações no texto.'
        )
        return redirect(destino)

    if alterada:
        messages.success(request, f'Página {numero} confirmada.')
    else:
        messages.info(request, f'A página {numero} já estava confirmada com este texto.')
    return redirect(destino)


@login_required
@require_POST
def editar_pagina_ocr(request, tis_id, imovel_id, documento_id, job_id, numero):
    """Salva a edição sem confirmar: a página fica "editada" até reconfirmar."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    # Sem o campo, "editar" esvaziaria a página: é requisição malformada.
    if 'texto' not in request.POST:
        return HttpResponseBadRequest('Campo "texto" ausente.')
    destino = _url_tela(_kwargs_job(tis, imovel, documento, job), numero)
    try:
        _pagina, alterada = services.editar_pagina(
            job, numero, request.POST['texto'],
        )
    except PaginaOcr.DoesNotExist:
        raise Http404('Página inexistente.')
    except services.TextoNaoEditavel:
        messages.error(
            request, 'Este processamento não aceita mais alterações no texto.'
        )
        return redirect(destino)

    if alterada:
        messages.success(
            request,
            f'Edição da página {numero} salva. Confirme a página para validá-la.',
        )
    else:
        messages.info(request, f'Nenhuma alteração para salvar na página {numero}.')
    return redirect(destino)


@login_required
@require_POST
def confirmar_paginas_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Bulk: confirma as páginas pendentes quando nada foi editado."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    destino = _destino(request, _kwargs_job(tis, imovel, documento, job))
    try:
        total = services.confirmar_todas_paginas(job, request.user)
    except services.TextoNaoEditavel:
        messages.error(
            request, 'Este processamento não aceita mais alterações no texto.'
        )
    except services.EdicaoPendente:
        messages.error(
            request,
            'Há página editada aguardando confirmação: confirme-a individualmente '
            'antes de usar "Confirmar todas as páginas".',
        )
    else:
        if total:
            confirmadas = '1 página confirmada' if total == 1 else f'{total} páginas confirmadas'
            messages.success(request, f'{confirmadas} sem alteração.')
        else:
            messages.info(request, 'Não havia páginas pendentes de confirmação.')
    return redirect(destino)


@login_required
@require_POST
def reprocessar_job_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Novo ciclo de OCR (I-2). O job atual e seu texto confirmado ficam intactos."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)
    if job.status not in estados.STATUS_REVISAVEIS:
        messages.error(
            request,
            'Só é possível reprocessar um OCR concluído e ainda não confirmado.',
        )
        return redirect(_url_tela(kwargs_job))

    try:
        _novo, criado = services.reprocessar(job, usuario=request.user)
    except services.JobEmExecucao:
        messages.error(request, 'O processamento de origem ainda está em andamento.')
    else:
        if criado:
            messages.success(
                request,
                'Novo processamento de OCR iniciado. O texto confirmado do '
                'processamento anterior segue preservado e só será substituído '
                'depois do novo ciclo.',
            )
        else:
            messages.info(
                request, 'Já existe um processamento de OCR em andamento para este arquivo.'
            )
    return redirect(
        'upload_documento_digital',
        tis_id=tis.pk, imovel_id=imovel.pk, documento_id=documento.pk,
    )


@login_required
@require_POST
def extrair_campos_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Botão "Extrair campos →": concluido → texto_confirmado, só com tudo confirmado.

    Nesta issue só a transição e o link para a revisão de campos; a extração
    estruturada e a tela de campos são da I-5 (#262).
    """
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    destino = _destino(request, _kwargs_job(tis, imovel, documento, job))
    try:
        services.confirmar_texto(job, request.user)
    except TransicaoInvalida as exc:
        if exc.code in ('paginas_nao_confirmadas', 'sem_paginas'):
            messages.error(
                request, 'Confirme todas as páginas antes de extrair os campos.'
            )
        else:
            messages.error(
                request, 'Este processamento não está mais aguardando a confirmação do texto.'
            )
    except TransicaoConcorrente:
        messages.error(
            request, 'O processamento mudou de estado enquanto você revisava. Recarregue a tela.'
        )
    else:
        messages.success(
            request, 'Texto confirmado. O próximo passo é a revisão de campos.'
        )
    return redirect(destino)


@login_required
@require_GET
def campos_job_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Ponto de entrada da revisão de campos (I-5 / #262), ainda sem a tela.

    Existe para o link de "Extrair campos →" apontar para um destino estável
    e com a mesma checagem de hierarquia; a I-5 troca o corpo desta view.
    """
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)
    if job.status in estados.STATUS_REVISAVEIS or job.status not in estados.STATUS_COM_TEXTO:
        messages.info(request, 'Confirme o texto antes de revisar os campos.')
        return redirect(_url_tela(kwargs_job))
    return render(request, 'ia_ocr/campos_pendente.html', {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'job': job,
        'url_texto': _url_tela(kwargs_job),
    })
