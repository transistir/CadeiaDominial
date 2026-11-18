"""Telas da app ia_ocr: texto OCR e revisão da extração estruturada.

Mesma política de acesso do upload digital: ``login_required`` + hierarquia
TI→Imóvel→Documento (``_get_contexto_documento``); fora do escopo → 404, o
padrão do projeto. As mutações são POST com redirect de volta à tela (PRG) e
delegam a ``ia_ocr.services``: a view nunca grava página nem transiciona o job
diretamente. Nenhum log daqui carrega texto de documento ou nome de arquivo
(PII).
"""

import json
import logging
import re
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import decorator_from_middleware
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import (
    require_GET, require_http_methods, require_POST,
)

# Hierarquia TI→Imóvel→Documento: a mesma do upload digital (reuso, não cópia).
from dominial.managers import documentos_for_user
from dominial.models import Cartorios, LancamentoTipo, Pessoas
from dominial.services.lancamento_service import LancamentoService
from dominial.views.documento_digital_views import _get_contexto_documento
from dominial.views.lancamento_views import _build_novo_lancamento_context

from . import estados, formulario, revisao, revisao_ato, rotulos, services, valores
from . import importacao
from .diff import segmentos_diff
from .estados import TransicaoConcorrente, TransicaoInvalida
from .extracao_backends import ExtracaoBackendError
from .extracao_schema import PayloadExtracaoInvalido
from .models import (
    ESTADO_CONFIRMADA, ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA, OcrJob,
    OcrJobTransicao, PaginaOcr,
)

logger = logging.getLogger(__name__)

MENSAGEM_PAGINA_DESATUALIZADA = (
    'A página {numero} foi alterada por outra pessoa (ou em outra aba) depois '
    'que você a abriu. Nada foi gravado, para não sobrescrever essa alteração: '
    'o texto atual foi recarregado. Revise-o e repita a ação se ainda for '
    'necessário.'
)


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


def _avisos_descritos(request, extracao) -> list[dict]:
    """Avisos da revisão com o texto de negócio de cada um (#324).

    A MESMA fonte para a abertura da tela (``campos_job_ocr``) e para a
    resposta do save (``salvar_bloco_ocr``): o aviso (e o selo "não consta no
    documento") nasce do estado salvo da extração, então depois de um save a
    tela precisa do cálculo novo — nada de reimplementar a regra no cliente.
    O escopo do USUÁRIO alimenta o aviso de homônimo (#267): documento de
    outra TI nunca participa dele.
    """
    return [
        revisao.descrever_aviso(item)
        for item in revisao.avisos(
            extracao, documentos_queryset=documentos_for_user(request.user),
        )
    ]


def _aviso_nao_consta(item) -> bool:
    """O aviso é de "não consta no documento" (livro/folha da origem, #324).

    É ele que dá o selo ao card; a abertura da tela e a resposta do save usam
    este mesmo predicado, então o cliente não repete a lista de motivos.
    """
    return item['motivo'] in revisao.MOTIVOS_NAO_CONSTA


def _avisos_da_resposta(request, extracao) -> list[dict]:
    """Os avisos recalculados no formato da resposta do save (#324).

    Só o que a tela desenha: chave (alvo do selo), motivo (detalhe técnico),
    ``local``/``rotulo`` (texto de negócio) e ``nao_consta`` (o selo).
    """
    return [
        {
            'chave': item['chave'],
            'motivo': item['motivo'],
            'local': item['local'],
            'rotulo': item['rotulo'],
            'nao_consta': _aviso_nao_consta(item),
        }
        for item in _avisos_descritos(request, extracao)
    ]


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


def _versao_do_formulario(request):
    """Versão da página que o formulário exibiu, ou None se ausente/inválida.

    Limite de dígitos pelo mesmo motivo de ``_numero_pagina``; o valor só é
    comparado em Python com a versão da página, nunca vai para o banco.
    """
    bruto = request.POST.get('versao')
    if bruto is not None and re.fullmatch(r'[0-9]{1,10}', bruto):
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


def _disponibilidade_extracao(job, paginas):
    """(pode_extrair, motivo): após a #290 só depende do OCR, não da confirmação.

    ``texto_confirmado`` continua aceito pelo serviço (#12): a tela desse
    estado precisa oferecer o mesmo botão que a de ``concluido``.

    Mesma regra de ``services.extrair_campos``: sem páginas ou com
    ``texto_ocr`` nulo, recusa; verso em branco (``''``) é legítimo.
    """
    if job.status not in (estados.CONCLUIDO, estados.TEXTO_CONFIRMADO):
        return False, 'Aguardando o OCR terminar.'
    if not paginas or any(pagina.texto_ocr is None for pagina in paginas):
        return False, 'O OCR não devolveu texto para todas as páginas.'
    return True, ''


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
    pode_extrair, motivo_sem_extracao = _disponibilidade_extracao(job, paginas)
    # #314: um clique do upload ao formulário — a tela submete sozinha o
    # "Extrair campos" quando ainda não há extração (o POST segue o fluxo normal).
    auto_extrair = bool(
        pode_extrair and editavel and job.extracao_vigente() is None
    )

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
            return redirect('campos_job_ocr', **kwargs_job)
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
        messages.success(request, 'Extração concluída. Revise os campos.')
        return redirect('campos_job_ocr', **kwargs_job)
    return redirect(_destino(request, kwargs_job))


def _mascarar_cpf(cpf):
    digitos = re.sub(r'\D', '', cpf or '')
    return f'CPF ***.***.***-{digitos[-2:]}' if len(digitos) >= 2 else 'CPF ***'


_CPF = re.compile(r'\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}\b')
_RG = re.compile(r'\b\d{1,2}\.\d{3}\.\d{3}-?[\dXx]\b')
_RG_ROTULO = re.compile(
    r'(?i)(\bR\.?G\.?(?:\s*n\.?\s*[º°o]?\.?)?\s*[:\-]?\s*)'
    r'\d(?:[.\-/\s]?\d){4,11}(?:[-\s]?[\dXx])?'
)


def _mascarar_evidencia(trecho):
    """Esconde CPF/RG no trecho exibido; datas, valores e CNS ficam intactos."""
    if not trecho:
        return trecho
    mascarado = _CPF.sub('***', trecho)
    mascarado = _RG.sub('***', mascarado)
    return _RG_ROTULO.sub(r'\1***', mascarado)


def _mascarar_rg(rg):
    digitos = re.sub(r'\D', '', rg or '')
    return f'RG ***{digitos[-2:]}' if len(digitos) >= 2 else 'RG ***'


def _rotulo_pessoa(pessoa):
    if pessoa is None:
        return 'Cadastro indisponível'
    if pessoa.cpf:
        documento = _mascarar_cpf(pessoa.cpf)
    elif pessoa.rg:
        documento = _mascarar_rg(pessoa.rg)
    else:
        documento = ''
    return f'{pessoa.nome} — {documento}' if documento else pessoa.nome


def _rotulo_cartorio(cartorio):
    if cartorio is None:
        return 'Cadastro indisponível'
    rotulo = cartorio.nome
    local = '/'.join(
        parte for parte in (cartorio.cidade, cartorio.estado) if parte
    )
    if local:
        rotulo = f'{rotulo} — {local}'
    if cartorio.cns:
        rotulo = f'{rotulo} — CNS {cartorio.cns}'
    return rotulo


def _anexar_opcoes_cadastro(campos):
    """Rótulos dos candidatos, em uma query por tipo (pessoa/cartório).

    Nunca consulta o banco no template e nunca expõe documento completo:
    CPF/RG saem mascarados com os dois últimos dígitos.
    """
    ids_pessoas = set()
    ids_cartorios = set()
    for campo in campos:
        if campo.tipo_valor == 'parte':
            ids_pessoas.update(campo.match_candidatos or [])
            if campo.pessoa_escolhida_id:
                ids_pessoas.add(campo.pessoa_escolhida_id)
        elif campo.tipo_valor == 'cartorio':
            ids_cartorios.update(campo.match_candidatos or [])
            if campo.cartorio_escolhido_id:
                ids_cartorios.add(campo.cartorio_escolhido_id)
    pessoas = {
        p.pk: p for p in Pessoas.objects.filter(
            pk__in=ids_pessoas,
        ).only('nome', 'cpf', 'rg')
    }
    cartorios = {
        c.pk: c for c in Cartorios.objects.filter(
            pk__in=ids_cartorios,
        ).only('nome', 'cidade', 'estado', 'cns')
    }

    def opcoes(ids, escolhido, rotulos):
        lista = list(ids or [])
        if escolhido and escolhido not in lista:
            lista.append(escolhido)
        return [
            {'id': pk, 'rotulo': rotulos.get(pk, 'Cadastro indisponível')}
            for pk in lista
        ]

    rotulos_pessoas = {
        pk: _rotulo_pessoa(pessoa) for pk, pessoa in pessoas.items()
    }
    rotulos_cartorios = {
        pk: _rotulo_cartorio(cartorio) for pk, cartorio in cartorios.items()
    }
    for campo in campos:
        if campo.tipo_valor == 'parte':
            campo.opcoes_cadastro = opcoes(
                campo.match_candidatos, campo.pessoa_escolhida_id,
                rotulos_pessoas,
            )
        elif campo.tipo_valor == 'cartorio':
            campo.opcoes_cadastro = opcoes(
                campo.match_candidatos, campo.cartorio_escolhido_id,
                rotulos_cartorios,
            )
        else:
            campo.opcoes_cadastro = []


def _preencher_fallback_cartorio(extracao, campos):
    """Seletor de cartório nunca vazio: candidatos da comarca, só em memória.

    Roda antes de ``_anexar_opcoes_cadastro`` para os rótulos saírem na mesma
    query. Nada é salvo nem pré-selecionado: a escolha é do revisor.
    """
    sem_candidatos = [
        campo for campo in campos
        if campo.tipo_valor == 'cartorio' and not campo.match_candidatos
    ]
    if not sem_candidatos:
        return
    indice = revisao.IndiceCartorios()
    comarca = revisao.comarca_do_documento(extracao)
    for campo in sem_candidatos:
        campo.match_candidatos = revisao.fallback_cartorio(
            campo, indice, comarca,
        )


def _opcoes_tipo_sugerido():
    """Opções do <select> do tipo, na MESMA fonte do enum aceito no save.

    Revisão Opus (MUST-FIX #322): as opções DESENHADAS saem de
    ``rotulos.TIPOS_SUGERIDOS`` — o mesmo vocabulário que
    ``destinos._do_campo`` aceita no POST. Tipo no cadastro fora do
    contrato não vira opção que dá 422; código no contrato sem linha no
    cadastro continua sendo ofertado. O rótulo de exibição vem do cadastro
    (``get_tipo_display``) quando a linha existe e de
    ``LancamentoTipo.TIPO_CHOICES`` quando não vem.
    """
    configuracoes = {
        tipo.tipo: tipo for tipo in LancamentoTipo.objects.order_by('pk')
    }
    displays = dict(LancamentoTipo.TIPO_CHOICES)
    return [
        {
            'codigo': codigo,
            'display': (
                configuracoes[codigo].get_tipo_display()
                if codigo in configuracoes
                else displays.get(codigo, codigo)
            ),
        }
        for codigo in rotulos.TIPOS_SUGERIDOS
    ]


@login_required
@require_GET
def campos_job_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Revisão da extração vigente; após finalizar, a tela é somente leitura."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)
    if job.status not in (estados.EXTRAIDO, estados.REVISADO):
        messages.info(request, 'Extraia os campos antes de revisá-los.')
        return redirect(_url_tela(kwargs_job))
    extracao = job.extracao_vigente()
    if extracao is None:
        raise Http404('Extração indisponível.')
    todas_as_linhas = list(extracao.campos.order_by('chave'))
    # Token do estado salvo: os candidatos abaixo são só de exibição. O
    # token cobre TODAS as linhas salvas — inclusive as ignoradas na tela
    # (Tarefa C #322), que o salvar_bloco ainda considera no seu próprio —
    # senão o primeiro save da extração antiga daria conflito de versão.
    versao = services.versao_bloco(extracao, campos=todas_as_linhas)
    # Linhas em revisao.LINHAS_IGNORADAS (extrações antigas já salvaram
    # valor_transacao) não podem virar card.
    campos = [
        campo for campo in todas_as_linhas
        if not revisao.linha_ignorada(campo.chave)
    ]
    _preencher_fallback_cartorio(extracao, campos)
    _anexar_opcoes_cadastro(campos)
    # P2-2 (#322/PR #327, rodada 10): o card tem que mostrar o tipo que
    # pendências, prévia e importação vão usar — o resolvedor único da
    # revisão, AGORA COM A ORIGEM. Nada de recalcular a precedência aqui:
    # a cópia anterior divergia em dois estados alcançáveis (linha de tipo
    # descartada e valor explícito fora de TIPOS_SUGERIDOS criado pelo
    # backfill da 0009). Rodada 12: a resolução cobre também o ato
    # DESCARTADO (mesmo resolvedor, contexto que ignora só o descarte
    # dele) — o fallback de valor_final/normalized da rodada 11 saiu.
    resolucoes = revisao.resolucoes_de_tipo(extracao)
    for campo in campos:
        campo.evidencia_trecho = _mascarar_evidencia(campo.evidencia_trecho)
        campo.obrigatorio = revisao.campo_obrigatorio(campo.chave)
        # Exclusivo do card de tipo do ATO (/acts/N/tipo_sugerido): nenhuma
        # outra chave do mapa de destinos termina em tipo_sugerido.
        campo.eh_tipo_sugerido = re.fullmatch(
            r'/acts/\d+/tipo_sugerido', campo.chave,
        ) is not None
        if campo.eh_tipo_sugerido:
            # O que o <select> traz selecionado é o que a importação vai
            # usar — inclusive quando a linha de tipo está descartada (o
            # resolvedor já pula a linha e cai no rótulo) e quando o ATO
            # está descartado. Única exceção: origem 'limpo' = select
            # APAGADO (P2-1), decisão de "sem tipo" — nenhuma opção
            # marcada. Sem linha estrutural do ato não há resolução
            # (estado inalcançável: o desnormalizar sempre cria a linha do
            # ato antes da de tipo) e o select fica em branco.
            tipo, origem = resolucoes.get(
                campo.chave.rsplit('/', 1)[0], (None, 'nenhum'),
            )
            campo.tipo_exibido = '' if origem == 'limpo' else tipo
    # I-11a (#321): a tela agrupa como o FORMULÁRIO de lançamento — seção
    # Documento, um bloco por ato em ordem reversa, não reconhecidos e
    # "Outros dados lidos" —, não mais por destino técnico
    # (``dominial.Lancamento.tipo``/``SEM_DESTINO``). As opções do <select>
    # são calculadas UMA vez: o display do subtítulo do ato sai da mesma
    # fonte que desenha as opções.
    opcoes_tipo = _opcoes_tipo_sugerido()
    somente_leitura = job.status == estados.REVISADO
    pendencias = services._com_bloqueios_de_campo(
        revisao.pendencias(extracao), extracao,
    )
    # Issue #262: a confirmação sem atos só aparece quando a ÚNICA pendência é
    # a ausência de atos. A comparação é por conteúdo: a lista de pendências
    # continua sendo exibida e a flag nunca a remove.
    permitir_sem_atos = (
        services.pode_finalizar_sem_atos(extracao) and not somente_leitura
    )
    avisos_descritos = _avisos_descritos(request, extracao)
    # Detalhe técnico do card abre sozinho no campo com pendência, e o
    # cabeçalho do ato conta as pendências que o bloqueiam. O selo "não
    # consta no documento" (#324) marca o campo de livro/folha da origem que
    # o documento não trouxe; o campo segue vazio e editável.
    chaves_pendentes = {item['chave'] for item in pendencias}
    chaves_nao_consta = {
        item['chave'] for item in avisos_descritos if _aviso_nao_consta(item)
    }
    for campo in campos:
        campo.pendente = campo.chave in chaves_pendentes
        campo.nao_consta = campo.chave in chaves_nao_consta
    secoes = revisao.secoes_da_tela(
        campos,
        payload=extracao.payload_servico or extracao.payload,
        tipos_display={
            opcao['codigo']: opcao['display'] for opcao in opcoes_tipo
        },
    )
    for secao in secoes:
        if secao['tipo'] != 'ato':
            continue
        prefixo = secao['chave_ato']
        secao['pendencias_do_ato'] = sum(
            1 for item in pendencias
            if item['chave'] == prefixo
            or (
                isinstance(item['chave'], str)
                and item['chave'].startswith(prefixo + '/')
            )
        )
    # Âncora da pendência só quando o alvo existe na tela: linha sem card
    # (estado antigo) não vira link morto (#321 §5).
    ids_da_tela = {'campo-' + slugify(campo.chave) for campo in campos}
    if permitir_sem_atos:
        ids_da_tela.add('campo-sem-atos')
    pendencias_descritas = [
        revisao.descrever_pendencia(item, permitir_sem_atos)
        for item in pendencias
    ]
    for item in pendencias_descritas:
        if item['alvo'] is not None and item['alvo'] not in ids_da_tela:
            item['alvo'] = None
    return render(request, 'ia_ocr/revisao_campos.html', {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'arquivo': job.documento_digital,
        'job': job,
        'extracao': extracao,
        'campos': campos,
        'secoes': secoes,
        # Tarefa B #322: o tipo é <select> como no formulário de lançamento;
        # as opções e o enum aceito no save vêm da MESMA fonte (contrato A3).
        'opcoes_tipo_sugerido': opcoes_tipo,
        'codigos_tipo_sugerido': list(rotulos.TIPOS_SUGERIDOS),
        'pendencias': pendencias_descritas,
        'pendencias_total': len(pendencias),
        'permitir_sem_atos': permitir_sem_atos,
        'avisos': avisos_descritos,
        'versao': versao,
        'somente_leitura': somente_leitura,
        'dpi': job.dpi or 200,
        'url_salvar': reverse('salvar_bloco_ocr', kwargs=kwargs_job),
        'url_finalizar': reverse('finalizar_revisao_ocr', kwargs=kwargs_job),
        'url_texto': _url_tela(kwargs_job),
        'url_arquivo': reverse('servir_documento_digital', kwargs={
            'tis_id': tis.pk,
            'imovel_id': imovel.pk,
            'documento_id': documento.pk,
            'arquivo_id': job.documento_digital_id,
        }),
        'url_documento': reverse('documento_detalhado', kwargs={
            'tis_id': tis.pk, 'imovel_id': imovel.pk, 'documento_id': documento.pk,
        }),
    })


class _CsrfJsonMiddleware(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return JsonResponse({'erro': 'csrf_invalido'}, status=403)


def _respostas_json_ocr(view):
    """Mantém 404, 405 e rejeições CSRF em JSON, sem mudar o login_required."""
    protegida = decorator_from_middleware(_CsrfJsonMiddleware)(view)

    # A checagem CSRF é feita pela middleware local acima, com a mesma
    # proteção do Django. Evita apenas a resposta HTML da middleware global.
    @csrf_exempt
    @wraps(view)
    def resposta_json(request, *args, **kwargs):
        try:
            resposta = protegida(request, *args, **kwargs)
        except Http404:
            return JsonResponse({'erro': 'nao_encontrado'}, status=404)
        if resposta.status_code == 405:
            erro = JsonResponse({'erro': 'metodo_nao_permitido'}, status=405)
            erro['Allow'] = resposta['Allow']
            return erro
        return resposta

    return resposta_json


def _recusar_decisao(code, chave=None):
    erro = services.ExtracaoRecusada(code)
    erro.chave = chave
    raise erro


_ESCOLHA_DA_TELA = {
    'pessoa_id': 'pessoa_escolhida_id',
    'cartorio_id': 'cartorio_escolhido_id',
}


def _decisoes_bloco(dados):
    """Valida o contrato JSON e indexa a lista pelo JSON Pointer de cada linha."""
    if not isinstance(dados, dict):
        _recusar_decisao('corpo_invalido')
    if not isinstance(dados.get('versao'), str):
        _recusar_decisao('versao_invalida')
    if not isinstance(dados.get('decisoes'), list):
        _recusar_decisao('decisoes_invalidas')
    decisoes = {}
    for decisao in dados['decisoes']:
        if not isinstance(decisao, dict):
            _recusar_decisao('decisao_invalida')
        chave = decisao.get('chave')
        if not isinstance(chave, str) or not chave:
            _recusar_decisao('chave_invalida')
        if chave in decisoes:
            _recusar_decisao('chave_duplicada', chave)
        if not isinstance(decisao.get('incluir'), bool):
            _recusar_decisao('decisao_invalida', chave)
        for nome in ('conferido', 'confirmo_conversao'):
            if nome in decisao and not isinstance(decisao[nome], bool):
                _recusar_decisao('decisao_invalida', chave)
        for nome in ('valor', 'ha_convertido'):
            if decisao.get(nome) is not None and not isinstance(decisao[nome], str):
                _recusar_decisao('valor_invalido', chave)
        if 'versao' in decisao and not isinstance(decisao['versao'], str):
            _recusar_decisao('versao_invalida', chave)
        escolha = decisao.get('escolha')
        if escolha is not None:
            if not isinstance(escolha, dict):
                _recusar_decisao('escolha_invalida', chave)
            # A tela manda pessoa_id/cartorio_id; o motor usa os nomes do modelo.
            for curto, nome in _ESCOLHA_DA_TELA.items():
                if curto in escolha:
                    if nome in escolha:
                        _recusar_decisao('escolha_invalida', chave)
                    escolha[nome] = escolha.pop(curto)
            for nome, valor in escolha.items():
                if nome == 'criar_novo' and isinstance(valor, bool):
                    continue
                if nome in ('pessoa_escolhida_id', 'cartorio_escolhido_id'):
                    if valor is None or (type(valor) is int and valor > 0):
                        continue
                _recusar_decisao('escolha_invalida', chave)
        decisoes[chave] = {nome: valor for nome, valor in decisao.items() if nome != 'chave'}
    return decisoes


def _chave_valor_invalido(extracao, decisoes):
    """Localiza a linha após rollback, reaplicando o motor só em memória.

    ValorInvalido ainda não carrega a chave; não expomos seu texto ao cliente.
    """
    campos = {campo.chave: campo for campo in extracao.campos.all()}
    for chave, decisao in decisoes.items():
        argumentos = {
            nome: decisao[nome] for nome in (
                'incluir', 'valor', 'conferido', 'escolha',
                'ha_convertido', 'confirmo_conversao',
            ) if nome in decisao
        }
        try:
            revisao.aplicar_linha(campos[chave], **argumentos)
        except valores.ValorInvalido:
            return chave
        except revisao.EscolhaIncompativel:
            return chave
    return None


@_respostas_json_ocr
@login_required
@require_POST
def salvar_bloco_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Salva decisões de revisão com controle otimista da versão do bloco."""
    _tis, _imovel, _documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id,
    )
    try:
        dados = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'erro': 'json_invalido'}, status=400)
    try:
        decisoes = _decisoes_bloco(dados)
        # ``valor: null`` explícito pede o OCR; só a chave ausente preserva.
        com_valor = {item['chave'] for item in dados['decisoes'] if 'valor' in item}
        extracao = job.extracao_vigente()
        if extracao is None:
            raise services.ExtracaoRecusada('sem_extracao')
        obrigatorias = {
            chave for chave in decisoes if revisao.campo_obrigatorio(chave)
        }
        corrigidos = dict(extracao.campos.filter(
            chave__in=obrigatorias, valor_final__isnull=False,
        ).values_list('chave', 'valor_final'))
        for chave in obrigatorias:
            decisao = decisoes[chave]
            decisao['incluir'] = True
            # Sem a chave ``valor`` o motor volta ao OCR: preserva a correção salva.
            if chave not in com_valor and chave in corrigidos:
                decisao['valor'] = corrigidos[chave]
        _salva, versao, partes_invalidadas, campos_novos = services.salvar_bloco(
            extracao, decisoes, request.user, dados['versao'],
        )
    except revisao.EscolhaIncompativel as exc:
        return JsonResponse({
            'erro': exc.code, 'chave': exc.chave,
        }, status=422)
    except services.ConflitoVersao as exc:
        return JsonResponse({
            'erro': 'conflito_versao', 'chaves': exc.chaves_afetadas,
        }, status=409)
    except services.ExtracaoRecusada as exc:
        return JsonResponse({
            'erro': exc.code, 'chave': getattr(exc, 'chave', None),
        }, status=422)
    except valores.ValorInvalido as exc:
        return JsonResponse({
            'erro': 'valor_invalido',
            'chave': getattr(exc, 'chave', None)
            or _chave_valor_invalido(extracao, decisoes),
        }, status=422)
    except TransicaoInvalida as exc:
        return JsonResponse({'erro': exc.code or 'estado_invalido'}, status=409)
    except TransicaoConcorrente:
        return JsonResponse({'erro': 'transicao_concorrente'}, status=409)
    return JsonResponse({
        'ok': True,
        'versao': versao,
        # A escolha de cadastro foi zerada nessas partes: a tela relê os
        # candidatos recomputados pelo servidor quando puder recarregar.
        'partes_invalidadas': partes_invalidadas,
        # Linhas obrigatórias criadas pelo novo tipo: sem card na tela atual,
        # o cliente recarrega quando puder para exibi-las.
        'campos_novos': campos_novos,
        # Só chave/motivo: a tela reabilita o finalizar sem expor dados da revisão.
        # Com sem atos, ``pendencias()`` só traz ``nenhum_ato``; o helper
        # acrescenta os bloqueios de campo sem duplicar.
        'pendencias': [
            {'chave': item['chave'], 'motivo': item['motivo']}
            for item in services._com_bloqueios_de_campo(
                revisao.pendencias(_salva), _salva,
            )
        ],
        # Issue #262: um bloqueio de campo criado no save não aparece em
        # ``pendencias`` (sem atos ela é sempre nenhum_ato); a tela precisa
        # saber que a confirmação sem atos deixou de ser suficiente.
        'sem_atos_elegivel': _sem_atos_elegivel(_salva),
        # #324 (PR #343, P2): os avisos e os selos "não consta no documento"
        # só eram calculados na abertura da página — preencher livro/folha
        # deixava o aviso na tela, e mudar o número da origem podia esconder
        # ou criar um. A lista inteira vem da MESMA fonte da abertura
        # (``_avisos_descritos``) sobre o estado recém-salvo; a tela troca a
        # lista, a contagem e os selos por ela. Só chave, motivo, o texto de
        # negócio e se o aviso é de "não consta" (o selo do card) — nada do
        # valor revisado.
        'avisos': _avisos_da_resposta(request, _salva),
    })


@_respostas_json_ocr
@login_required
@require_POST
def importar_job_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Grava os atos marcados da revisão finalizada (I-6)."""
    _tis, _imovel, _documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id,
    )
    try:
        dados = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'erro': 'json_invalido'}, status=400)
    if not isinstance(dados, dict):
        return JsonResponse({'erro': 'corpo_invalido', 'chave': None}, status=422)
    try:
        extracao = job.extracao_vigente()
        if extracao is None:
            raise services.ExtracaoRecusada('sem_extracao')
        resultado = importacao.importar(
            extracao, request.user, dados.get('versao'), dados.get('atos'),
        )
    except importacao.ImportacaoInvalida as exc:
        return JsonResponse(
            {'erro': exc.code, 'linhas': exc.linhas}, status=422,
        )
    except revisao.RevisaoInvalidada as exc:
        # Mensagens fixas do motor (sem valor digitado): a tela recarrega.
        # As pendências estruturadas dizem ONDE — a parte cuja escolha de
        # pessoa virou nada chega como ``decisao_perdida`` (#263 rodada 2).
        return JsonResponse(
            {
                'erro': 'revisao_invalidada',
                'mensagem': str(exc),
                'pendencias': importacao.pendencias_para_resposta(extracao),
            },
            status=422,
        )
    except services.ConflitoVersao as exc:
        return JsonResponse({
            'erro': 'conflito_versao', 'chaves': exc.chaves_afetadas,
        }, status=409)
    except services.ExtracaoRecusada as exc:
        return JsonResponse({
            'erro': exc.code, 'chave': getattr(exc, 'chave', None),
        }, status=422)
    except TransicaoInvalida as exc:
        return JsonResponse({'erro': exc.code or 'estado_invalido'}, status=409)
    except TransicaoConcorrente:
        return JsonResponse({'erro': 'transicao_concorrente'}, status=409)
    return JsonResponse(resultado)


@_respostas_json_ocr
@login_required
@require_POST
def finalizar_revisao_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Finaliza apenas uma revisão sem pendências e informa o destino da tela."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id,
    )
    try:
        dados = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'erro': 'json_invalido'}, status=400)
    if not isinstance(dados, dict):
        return JsonResponse({'erro': 'corpo_invalido', 'chave': None}, status=422)
    # Issue #262: a confirmação é explícita e estritamente booleana; a string
    # "true" (ou 1) não pode destravar a finalização por acidente.
    if 'sem_atos' in dados and not isinstance(dados['sem_atos'], bool):
        return JsonResponse({'erro': 'corpo_invalido', 'chave': None}, status=422)
    # Sem o token que a tela exibiu, não há como saber se a revisão mudou.
    if not isinstance(dados.get('versao'), str):
        return JsonResponse({'erro': 'versao_ausente', 'chave': None}, status=422)
    try:
        extracao = job.extracao_vigente()
        if extracao is None:
            raise services.ExtracaoRecusada('sem_extracao')
        services.finalizar_revisao(
            extracao, request.user, versao_cliente=dados['versao'],
            confirmar_sem_atos=(dados.get('sem_atos') is True),
        )
    except services.ConflitoVersao as exc:
        return JsonResponse({
            'erro': 'conflito_versao', 'chaves': exc.chaves_afetadas,
        }, status=409)
    except services.RevisaoIncompleta as exc:
        return JsonResponse({
            'erro': 'revisao_incompleta', 'pendencias': exc.pendencias,
        }, status=422)
    except services.ExtracaoRecusada as exc:
        return JsonResponse({
            'erro': exc.code, 'chave': getattr(exc, 'chave', None),
        }, status=422)
    except TransicaoInvalida as exc:
        return JsonResponse({'erro': exc.code or 'estado_invalido'}, status=409)
    except TransicaoConcorrente:
        return JsonResponse({'erro': 'transicao_concorrente'}, status=409)
    return JsonResponse({
        'ok': True,
        'redirect': reverse('documento_detalhado', kwargs={
            'tis_id': tis.pk, 'imovel_id': imovel.pk, 'documento_id': documento.pk,
        }),
    })


# ---------------------------------------------------------------------------
# I-14 (#341): a revisão é o formulário de lançamento, um ato por vez
# ---------------------------------------------------------------------------

MENSAGEM_ERRO_INTERNO_DO_ATO = '❌ Erro interno ao salvar o ato. Tente novamente.'
MENSAGEM_ATO_JA_SALVO = (
    'Este ato já foi salvo como lançamento. Nada foi gravado de novo.'
)
MENSAGEM_DUPLICATA_NA_REVISAO = (
    'A origem deste ato já existe em outra cadeia. Altere a origem ou o '
    'cartório, ou salve este ato pelo lançamento manual para importar a '
    'cadeia existente. Nada foi gravado.'
)
MENSAGEM_REVISAO_CONCLUIDA = (
    '✅ Revisão concluída: todos os atos desta extração foram resolvidos.'
)
MENSAGEM_EXTRACAO_TROCOU = (
    '⚠️ A extração deste documento mudou; recarregue a revisão. Nada foi gravado.'
)


def _url_ato(kwargs_job, indice):
    return reverse('revisar_ato_ocr', kwargs={**kwargs_job, 'indice': indice})


def _url_entrada(kwargs_job):
    return reverse('revisar_job_ocr', kwargs=kwargs_job)


def _url_documento(tis, imovel, documento):
    return reverse('documento_detalhado', kwargs={
        'tis_id': tis.pk, 'imovel_id': imovel.pk, 'documento_id': documento.pk,
    })


def _fora_da_revisao(request, tis, imovel, documento, job, kwargs_job):
    """Redirect de quem chega em job que não está em revisão; ``None`` se está."""
    if job.status in (estados.EXTRAIDO, estados.REVISADO):
        return None
    if job.status == estados.IMPORTADO:
        messages.info(request, 'A revisão desta extração já foi concluída.')
        return redirect(_url_documento(tis, imovel, documento))
    messages.info(request, 'Extraia os campos antes de revisá-los.')
    return redirect(_url_tela(kwargs_job))


def _destino_da_navegacao(bruto, atos):
    """Índice pedido em ``_ir_para`` se for de um ato da revisão; senão ``None``."""
    if bruto is None or not re.fullmatch(r'[0-9]{1,6}', bruto):
        return None
    pedido = int(bruto)
    return pedido if any(ato['indice'] == pedido for ato in atos) else None


def _extracao_trocada_no_post(request, job, extracao, kwargs_job):
    """Redirect quando o POST vem de página renderizada sobre outra extração.

    A reextração troca a vigente no meio da revisão e o navegador segue com
    o formulário da ANTIGA aberto: sem esta checagem, o POST gravava os
    dados dela e marcava como importado o ato da mesma posição na extração
    nova (#341, M2). A identidade da extração vai no hidden ``extracao_id``
    e é validada contra a vigente SOB TRAVA (``select_for_update`` no job,
    a mesma ordem da reextração). Esta checagem preliminar acontece antes de
    resolver o índice, para uma página antiga não virar 404; salvar e navegar
    repetem a validação dentro da transação que grava o ato ou guarda o
    rascunho, mantendo a trava até o fim da operação. Trocada (ou sem a
    identidade, que todo POST da revisão carrega): nada é gravado, nem
    rascunho guardado — a entrada da revisão recarrega a extração vigente.
    """
    posted = (request.POST.get('extracao_id') or '').strip()
    with transaction.atomic():
        vigente = OcrJob.objects.select_for_update().get(
            pk=job.pk,
        ).extracao_vigente()
    if (
        vigente is not None and vigente.pk == extracao.pk
        and posted == str(vigente.pk)
    ):
        return None
    messages.warning(request, MENSAGEM_EXTRACAO_TROCOU)
    return redirect(_url_entrada(kwargs_job))


@login_required
@require_GET
def revisar_job_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Entrada da revisão: leva ao primeiro ato pendente. Só redireciona."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)
    desvio = _fora_da_revisao(request, tis, imovel, documento, job, kwargs_job)
    if desvio is not None:
        return desvio
    extracao = job.extracao_vigente()
    if extracao is None:
        raise Http404('Extração indisponível.')
    atos = revisao_ato.atos_da_revisao(extracao)
    if not atos:
        messages.info(request, 'A extração não trouxe nenhum ato para revisar.')
        return redirect(_url_tela(kwargs_job))
    alvo = revisao_ato.proximo_pendente(atos)
    if alvo is None:
        messages.info(request, 'Todos os atos desta extração já foram salvos.')
        return redirect(_url_documento(tis, imovel, documento))
    return redirect(_url_ato(kwargs_job, alvo['indice']))


@login_required
@require_http_methods(['GET', 'POST'])
def revisar_ato_ocr(request, tis_id, imovel_id, documento_id, job_id, indice):
    """O formulário de lançamento pré-preenchido com o ato ``indice``.

    Mesma segurança de ``/campos/``: hierarquia TI→Imóvel→Documento→job e
    404 (não 403) fora do escopo. GET nunca grava; o POST é o único caminho
    de gravação e passa pelo ``LancamentoService`` do formulário manual.
    """
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)
    desvio = _fora_da_revisao(request, tis, imovel, documento, job, kwargs_job)
    if desvio is not None:
        return desvio
    extracao = job.extracao_vigente()
    if extracao is None:
        raise Http404('Extração indisponível.')

    # Antes de montar os atos: um POST de página antiga pode nem corresponder
    # a um ato da extração nova (o índice sumiu) — a recusa pela identidade
    # da extração vem primeiro, sem 404 (#341, M2).
    if request.method == 'POST':
        trocada = _extracao_trocada_no_post(request, job, extracao, kwargs_job)
        if trocada is not None:
            return trocada

    atos = revisao_ato.atos_da_revisao(extracao)
    ato = next((item for item in atos if item['indice'] == indice), None)
    if ato is None:
        raise Http404('Ato inexistente.')

    if request.method == 'POST':
        if '_ir_para' in request.POST:
            return _navegar_entre_atos(request, extracao, kwargs_job, indice)
        return _salvar_ato(
            request, tis, imovel, documento, job, extracao, kwargs_job, atos, ato,
        )

    if ato['estado'] == revisao_ato.ESTADO_IMPORTADO:
        messages.info(
            request,
            'Este ato já foi salvo. Para alterá-lo, use a edição do lançamento.',
        )
        return redirect(reverse('editar_lancamento', kwargs={
            'tis_id': tis.pk, 'imovel_id': imovel.pk,
            'lancamento_id': ato['lancamento_id'],
        }))
    rascunho = revisao_ato.rascunho_do_ato(request, extracao, indice)
    return _mostrar_ato(
        request, tis, imovel, documento, job, extracao, kwargs_job, atos, ato,
        rascunho=rascunho, restaurado=rascunho is not None,
    )


def _navegar_entre_atos(request, extracao, kwargs_job, indice):
    """Guarda o rascunho somente se a extração postada ainda for a vigente.

    A checagem e ``guardar_rascunho`` ficam sob a mesma trava do job. A
    reextração não pode entrar entre as duas e fazer uma página antiga
    navegar como se ainda pertencesse à revisão atual (#341, M2).
    """
    try:
        with transaction.atomic():
            extracao = services._travar_extracao_revisao(extracao)
            if (request.POST.get('extracao_id') or '').strip() != str(extracao.pk):
                raise services.ExtracaoRecusada('extracao_nao_vigente')
            atos = revisao_ato.atos_da_revisao(extracao)
            revisao_ato.guardar_rascunho(request, extracao, indice)
            destino = _destino_da_navegacao(request.POST.get('_ir_para'), atos)
    except services.ExtracaoRecusada:
        messages.warning(request, MENSAGEM_EXTRACAO_TROCOU)
        return redirect(_url_entrada(kwargs_job))
    return redirect(_url_ato(kwargs_job, indice if destino is None else destino))


def _salvar_ato(request, tis, imovel, documento, job, extracao, kwargs_job,
                atos, ato):
    indice = ato['indice']
    try:
        resultado = revisao_ato.salvar_ato(
            request, tis, imovel, documento, job, extracao, indice,
        )
    except services.ExtracaoRecusada:
        messages.warning(request, MENSAGEM_EXTRACAO_TROCOU)
        return redirect(_url_entrada(kwargs_job))
    except Exception:
        # Traceback só no log do servidor (mesma regra do novo_lancamento,
        # #162): nunca ``str(e)`` na tela, que vazaria documento/matrícula.
        logger.exception(
            'Erro inesperado ao salvar o ato %s da revisão (job=%s, documento=%s)',
            indice, job.pk, documento.pk,
        )
        messages.error(request, MENSAGEM_ERRO_INTERNO_DO_ATO)
        # O ``atomic`` do ``salvar_ato`` desfaz o banco, mas esta instância
        # segue em memória com o livro/folha que o service escreveu ANTES de
        # a falha acontecer: sem o refresh, o re-render travava (disabled)
        # um livro que o banco não tem (#341, M4 — mesmo fix do
        # ``ValidationError`` do service manual).
        documento.refresh_from_db(fields=['livro', 'folha'])
        return _mostrar_ato(
            request, tis, imovel, documento, job, extracao, kwargs_job, atos,
            ato, rascunho=request.POST,
        )

    if resultado.situacao == 'salvo':
        revisao_ato.limpar_rascunho(request, extracao, indice)
        messages.success(request, f'✅ Ato {ato["rotulo"]} salvo como lançamento.')
        if resultado.mensagem_origens:
            messages.info(request, resultado.mensagem_origens)
        return _depois_de_salvar(request, tis, imovel, documento, extracao,
                                 kwargs_job, indice)
    if resultado.situacao == 'ja_salvo':
        messages.info(request, MENSAGEM_ATO_JA_SALVO)
        return _depois_de_salvar(request, tis, imovel, documento, extracao,
                                 kwargs_job, indice)
    if resultado.situacao == 'recusado':
        messages.error(request, resultado.mensagem)
        return redirect(_url_tela(kwargs_job))

    # ``invalido``/``duplicata``: o service recusou e nada foi gravado — o
    # formulário volta com os erros e com tudo o que foi digitado.
    if resultado.situacao == 'duplicata':
        messages.warning(request, MENSAGEM_DUPLICATA_NA_REVISAO)
    else:
        messages.error(request, resultado.mensagem)
    return _mostrar_ato(
        request, tis, imovel, documento, job, extracao, kwargs_job, atos, ato,
        rascunho=request.POST,
        numero_lancamento_error=(
            'Já existe um lançamento com o número' in (resultado.mensagem or '')
        ),
    )


def _depois_de_salvar(request, tis, imovel, documento, extracao, kwargs_job,
                      indice):
    """Próximo ato pendente; sem nenhum, a tela do documento com o aviso final."""
    atos = revisao_ato.atos_da_revisao(extracao)
    proximo = revisao_ato.proximo_pendente(atos, depois_de=indice)
    if proximo is None:
        messages.success(request, MENSAGEM_REVISAO_CONCLUIDA)
        return redirect(_url_documento(tis, imovel, documento))
    return redirect(_url_ato(kwargs_job, proximo['indice']))


def _mostrar_ato(request, tis, imovel, documento, job, extracao, kwargs_job,
                 atos, ato, rascunho=None, numero_lancamento_error=False,
                 restaurado=False):
    """Renderiza o formulário de lançamento do ato.

    ``rascunho`` (POST guardado na sessão ou POST recusado) vence o
    pré-preenchimento: é o que o usuário digitou. ``restaurado`` avisa que
    ele veio da sessão (e não de um erro de validação). Só lê o banco.
    """
    indice = ato['indice']
    try:
        prefill = formulario.prefill_do_ato(extracao, indice, documento)
    except formulario.AtoInexistente:
        raise Http404('Ato inexistente.')
    if rascunho is not None:
        estado = revisao_ato.estado_do_formulario(rascunho)
    else:
        estado = {
            chave: prefill[chave] for chave in (
                'form_data', 'origens_separadas', 'transmitentes', 'adquirentes',
            )
        }

    # Mesmo contexto do GET/erro do formulário manual: tipos, cartórios,
    # herança de cartório, ``is_primeiro_lancamento`` etc.
    context = _build_novo_lancamento_context(
        request, tis, imovel, documento,
        Pessoas.objects.all().order_by('nome'),
        Cartorios.objects.all().order_by('nome'),
        LancamentoService.obter_tipos_lancamento_por_documento(documento),
        emitir_avisos=False,
    )
    context.update(estado)
    context.update({
        'numero_lancamento_error': numero_lancamento_error,
        'evidencias': prefill['evidencias'],
        'revisao_ia': {
            'indice': indice,
            'extracao_id': extracao.pk,
            'posicao': ato['posicao'],
            'total': len(atos),
            'rotulo': ato['rotulo'],
            'salvos': sum(
                1 for item in atos
                if item['estado'] == revisao_ato.ESTADO_IMPORTADO
            ),
            'atos': [
                dict(
                    item,
                    atual=item['indice'] == indice,
                    url=_url_ato(kwargs_job, item['indice']),
                    url_lancamento=(
                        reverse('editar_lancamento', kwargs={
                            'tis_id': tis.pk, 'imovel_id': imovel.pk,
                            'lancamento_id': item['lancamento_id'],
                        }) if item['lancamento_id'] else None
                    ),
                )
                for item in atos
            ],
            'avisos': prefill['pendencias'],
            'descartar_area': bool(
                rascunho is not None
                and rascunho.get('descartar_area') == '1'
            ),
            'restaurado': restaurado,
            'url_texto': _url_tela(kwargs_job),
            'url_documento': _url_documento(tis, imovel, documento),
        },
    })
    return render(request, 'dominial/lancamento_form.html', context)
