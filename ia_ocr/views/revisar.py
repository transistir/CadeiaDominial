"""Revisão do I-14 (#341): o formulário de lançamento, um ato por vez.

Extraída do monólito de views (etapa 3, limite de 400 linhas). O módulo
NÃO se chama ``revisao``: os testes fazem
``mock.patch('ia_ocr.views.revisao.pendencias')``, que resolve ``revisao``
como o pacote irmão ``ia_ocr.revisao`` — um submódulo de mesmo nome
sombrearia esse nome e o patch agiria no módulo errado.

Nomes alvo de patch resolvidos VIA O PACOTE, a cada chamada (ver o
docstring do ``__init__.py``):

- ``render`` — chamado como ``views.render``
  (``mock.patch('ia_ocr.views.render')``);
- ``_extracao_trocada_no_post`` — chamado como
  ``views._extracao_trocada_no_post``
  (``mock.patch('ia_ocr.views._extracao_trocada_no_post')``; mesmo sendo
  definido AQUI, o call site passa pelo pacote, senão o patch não age);
- ``guardar_rascunho`` segue como ATRIBUTO DE MÓDULO
  (``revisao_ato.guardar_rascunho``): o teste usa ``patch.object`` no
  módulo ``ia_ocr.revisao_ato``.

Todo outro helper de outro módulo do pacote vem por import direto do dono
e é chamada direta.

Logs: ``logger`` é ``getLogger(__name__)`` (``ia_ocr.views.revisar``) e
chega ao ``assertLogs('ia_ocr.views', level='ERROR')`` dos testes por
propagação ao logger pai.
"""
import logging
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from dominial.models import Cartorios, Pessoas
from dominial.services.lancamento_service import LancamentoService
from dominial.views.lancamento_views import _build_novo_lancamento_context

from .. import estados, formulario, revisao_ato, services, views
from ..models import OcrJob
from .jobs import _contexto_job, _kwargs_job
from .resposta import _url_tela

logger = logging.getLogger(__name__)

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
        trocada = views._extracao_trocada_no_post(request, job, extracao, kwargs_job)
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
    return views.render(request, 'dominial/lancamento_form.html', context)
