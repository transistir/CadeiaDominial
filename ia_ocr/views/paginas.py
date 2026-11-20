"""Ações de página da tela de texto: confirmar, editar, bulk, reprocessar
(I-2) e o POST que solicita a extração (#314). PRG: mutação é POST com
redirect de volta à tela; gravação só via ``ia_ocr.services``.

Extraídas do monólito de views (etapa 3, limite de 400 linhas). Nenhum
nome deste módulo é alvo de patch pelo pacote: helpers de outros módulos
vêm por import direto do dono e são chamada direta. Os POSTs passam por
``services.solicitar_extracao``/``services.confirmar_pagina`` etc. como
ATRIBUTO DE MÓDULO — os testes fazem
``mock.patch('ia_ocr.views.services.<op>')``, que resolve no módulo
``ia_ocr.services``, reexportado pelo pacote de views. Ver o docstring do
``__init__.py``.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .. import estados, services
from ..estados import TransicaoInvalida
from ..extracao_backends import ExtracaoBackendError
from ..extracao_schema import PayloadExtracaoInvalido
from ..models import PaginaOcr
from .jobs import _contexto_job, _kwargs_job
from .resposta import _destino, _url_tela, _versao_do_formulario

MENSAGEM_PAGINA_DESATUALIZADA = (
    'A página {numero} foi alterada por outra pessoa (ou em outra aba) depois '
    'que você a abriu. Nada foi gravado, para não sobrescrever essa alteração: '
    'o texto atual foi recarregado. Revise-o e repita a ação se ainda for '
    'necessário.'
)


@login_required
@require_POST
def confirmar_pagina_ocr(request, tis_id, imovel_id, documento_id, job_id, numero):
    """Confirma a página: grava texto_confirmado + quem/quando (auditoria)."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    # Sem a versão não há como saber se o formulário é obsoleto.
    versao = _versao_do_formulario(request)
    if versao is None:
        return HttpResponseBadRequest('Campo "versao" ausente ou inválido.')
    destino = _url_tela(_kwargs_job(tis, imovel, documento, job), numero)
    try:
        _pagina, alterada = services.confirmar_pagina(
            job, numero, request.user, texto=request.POST.get('texto'),
            versao_esperada=versao,
        )
    except PaginaOcr.DoesNotExist:
        raise Http404('Página inexistente.')
    except services.TextoNaoEditavel:
        messages.error(
            request, 'Este processamento não aceita mais alterações no texto.'
        )
        return redirect(destino)
    except services.PaginaDesatualizada:
        messages.error(request, MENSAGEM_PAGINA_DESATUALIZADA.format(numero=numero))
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
    versao = _versao_do_formulario(request)
    if versao is None:
        return HttpResponseBadRequest('Campo "versao" ausente ou inválido.')
    destino = _url_tela(_kwargs_job(tis, imovel, documento, job), numero)
    try:
        _pagina, alterada = services.editar_pagina(
            job, numero, request.POST['texto'], versao_esperada=versao,
        )
    except PaginaOcr.DoesNotExist:
        raise Http404('Página inexistente.')
    except services.TextoNaoEditavel:
        messages.error(
            request, 'Este processamento não aceita mais alterações no texto.'
        )
        return redirect(destino)
    except services.PaginaDesatualizada:
        messages.error(request, MENSAGEM_PAGINA_DESATUALIZADA.format(numero=numero))
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
    """Solicita a extração e encaminha para a revisão dos campos sugeridos."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)
    # #314/PR #319: só o POST da tela auto-submetida marca `extrair_auto`;
    # o clique manual segue sem o flag e continua podendo reextrair.
    auto = request.POST.get('extrair_auto') == '1'
    try:
        services.solicitar_extracao(job, request.user, somente_se_inexistente=auto)
    except services.ExtracaoRecusada as exc:
        if exc.code == 'extracao_existente':
            # O POST atrasado de uma segunda aba: já há revisão vigente com
            # as correções de quem chegou primeiro — não é falha.
            messages.info(request, 'Os campos já foram extraídos.')
            return redirect('revisar_job_ocr', **kwargs_job)
        mensagens = {
            'sem_texto_ocr': 'O OCR ainda não devolveu texto para todas as páginas.',
            'extracao_desatualizada': 'A extração mudou. Recarregue a tela.',
        }
        messages.error(request, mensagens.get(
            exc.code, 'Este processamento não permite extrair campos no estado atual.',
        ))
    except services.ExtracaoConcorrente:
        messages.error(
            request, 'Já existe uma extração em andamento para este documento.',
        )
    except (services.ExtracaoPayloadInvalido, PayloadExtracaoInvalido):
        # O serviço respondeu, mas fora do contrato: repetir não resolve. Sem
        # código, caminho ou valor na tela (o serviço já os deixou no log).
        messages.error(
            request,
            'A extração veio em formato inesperado. Avise o suporte.',
        )
    except services.ExtracaoIncompativel:
        # O serviço respondeu 422: recusou o formato/versão da requisição.
        # Repetir não resolve — é para o suporte, não "tente de novo".
        messages.error(
            request,
            'O serviço de extração não aceitou o formato desta versão. '
            'Avise o suporte.',
        )
    except (services.ExtracaoIndisponivel, ExtracaoBackendError):
        messages.error(
            request,
            'O serviço de extração não respondeu. Tente novamente em instantes.',
        )
    except TransicaoInvalida:
        messages.error(
            request, 'Este processamento não permite extrair campos no estado atual.',
        )
    else:
        messages.success(request, 'Extração concluída. Revise cada ato no formulário.')
        return redirect('revisar_job_ocr', **kwargs_job)
    return redirect(_destino(request, kwargs_job))
