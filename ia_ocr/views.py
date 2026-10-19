"""Telas da app ia_ocr: texto OCR e revisão da extração estruturada.

Mesma política de acesso do upload digital: ``login_required`` + hierarquia
TI→Imóvel→Documento (``_get_contexto_documento``); fora do escopo → 404, o
padrão do projeto. As mutações são POST com redirect de volta à tela (PRG) e
delegam a ``ia_ocr.services``: a view nunca grava página nem transiciona o job
diretamente. Nenhum log daqui carrega texto de documento ou nome de arquivo
(PII).
"""

import json
import re
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import decorator_from_middleware
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

# Hierarquia TI→Imóvel→Documento: a mesma do upload digital (reuso, não cópia).
from dominial.models import Cartorios, Pessoas
from dominial.views.documento_digital_views import _get_contexto_documento

from . import destinos, estados, revisao, services, valores
from .diff import segmentos_diff
from .estados import TransicaoConcorrente, TransicaoInvalida
from .extracao_backends import ExtracaoBackendError
from .models import (
    ESTADO_CONFIRMADA, ESTADO_EDITADA, ESTADO_NAO_CONFIRMADA, OcrJob,
    OcrJobTransicao, PaginaOcr,
)

MENSAGEM_PAGINA_DESATUALIZADA = (
    'A página {numero} foi alterada por outra pessoa (ou em outra aba) depois '
    'que você a abriu. Nada foi gravado, para não sobrescrever essa alteração: '
    'o texto atual foi recarregado. Revise-o e repita a ação se ainda for '
    'necessário.'
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
    try:
        services.solicitar_extracao(job, request.user)
    except services.ExtracaoRecusada as exc:
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
_RG = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]\b')
_RG_ROTULO = re.compile(
    r'(?i)(\bR\.?G\.?(?:\s*n\.?[º°o]?\.?)?\s*[:\-]?\s*)[\d.\-/]{5,13}[\dXx]'
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
    campos = list(extracao.campos.order_by('chave'))
    _anexar_opcoes_cadastro(campos)
    for campo in campos:
        campo.evidencia_trecho = _mascarar_evidencia(campo.evidencia_trecho)
    efetivos = {
        campo.chave: campo.valor_final if campo.valor_final is not None else campo.normalized
        for campo in campos
    }
    por_destino = {}
    for campo in campos:
        contexto = [efetivos[campo.chave]]
        if campo.chave.endswith('/documento_identificacao/valor'):
            contexto.insert(0, efetivos.get(campo.chave.rsplit('/', 1)[0] + '/tipo'))
        try:
            destino = destinos.destino_de(campo.chave, *contexto)
        except destinos.ChaveDesconhecida:
            destino = destinos.SEM_DESTINO
        por_destino.setdefault(destino.campo_modelo or 'SEM_DESTINO', []).append(campo)
    return render(request, 'ia_ocr/revisao_campos.html', {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'arquivo': job.documento_digital,
        'job': job,
        'extracao': extracao,
        'campos': campos,
        'por_destino': por_destino,
        'pendencias': revisao.pendencias(extracao),
        'avisos': revisao.avisos(extracao),
        'versao': services.versao_bloco(extracao, campos=campos),
        'somente_leitura': job.status == estados.REVISADO,
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
        extracao = job.extracao_vigente()
        if extracao is None:
            raise services.ExtracaoRecusada('sem_extracao')
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
        'pendencias': [
            {'chave': item['chave'], 'motivo': item['motivo']}
            for item in revisao.pendencias(_salva)
        ],
    })


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
    # Sem o token que a tela exibiu, não há como saber se a revisão mudou.
    if not isinstance(dados.get('versao'), str):
        return JsonResponse({'erro': 'versao_ausente', 'chave': None}, status=422)
    try:
        extracao = job.extracao_vigente()
        if extracao is None:
            raise services.ExtracaoRecusada('sem_extracao')
        services.finalizar_revisao(
            extracao, request.user, versao_cliente=dados['versao'],
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
