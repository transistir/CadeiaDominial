"""Conclusão da revisão sem atos (#262) pela revisão por formulário (#341).

Extraído do ``revisar_extras`` e estendido no MUST-FIX do review Codex da
#341: com ``acts: []`` e um campo do cabeçalho (``/document/cartorio``,
``/document/cri_atual``) SEM correspondência escolhida, a pendência
``escolha_pendente`` recusa ``pode_finalizar_sem_atos`` — e a tela de
cards, aposentada na fase 4, era o único controle que resolvia essa
escolha; o job ficava preso em ``extraido`` para sempre. O GET desta tela
passa a oferecer também o FORMULÁRIO dessas pendências — e só delas:
``obrigatorio_ausente``/``revisao_pendente``/``valor_invalido``/
``unidade_area`` não têm controle aqui e seguem no ramo antigo (mensagem +
redirect ao texto).

A regra do dono fica intocada (``services.pode_finalizar_sem_atos`` /
``services.finalizar_revisao``): só conclui sem atos quando a única
pendência é ``nenhum_ato``. Este módulo é a TELA que permite CHEGAR lá.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from dominial.models import Cartorios, Pessoas

from .. import estados, revisao, revisao_ato, services, valores, views
from ..estados import TransicaoConcorrente, TransicaoInvalida
from .jobs import _contexto_job, _kwargs_job
from .resposta import _url_tela
from .revisar_extras import _url_documento

logger = logging.getLogger(__name__)

MENSAGEM_SEM_ATOS_CONCLUIDA = (
    '✅ Revisão concluída: a extração foi finalizada sem atos.'
)
MENSAGEM_CRIAR_NOVO_SEM_NOME = (
    '⚠️ "Criar novo" exige o nome do novo cadastro preenchido. '
    'Nada foi gravado.'
)

# Pendências que ESTA tela resolve — todas de escolha de cadastro.
_MOTIVOS_DE_ESCOLHA = frozenset({
    'escolha_pendente', 'decisao_perdida', revisao.MOTIVO_CRIAR_NOVO_SEM_NOME,
})
# Valor do ``<option>`` sentinela: "o OCR leu, mas não há cadastro" —
# o nome para criá-lo vem do campo ``nome:<chave>`` do mesmo POST.
SENTINELA_CRIAR_NOVO = 'criar_novo'


def pendencias_de_escolha(extracao):
    """Pendências que ESTA tela resolve; ``[]`` se houver qualquer outra.

    Só escolha de cadastro tem controle aqui: os demais motivos pedem a
    revisão por ato/texto, e a página não pode fingir que os resolve —
    fingindo, o POST gravaria escolha e depois falharia na finalização
    (a transação única desfaz tudo).
    """
    por_chave = {campo.chave: campo for campo in extracao.campos.all()}
    escolhidas = []
    for pendencia in revisao.pendencias_sem_atos(extracao):
        if pendencia['motivo'] not in _MOTIVOS_DE_ESCOLHA:
            return []
        campo = por_chave.get(pendencia['chave'])
        if campo is None or campo.tipo_valor not in ('cartorio', 'parte'):
            return []
        escolhidas.append((pendencia['chave'], campo))
    return escolhidas


def destino_sem_atos(request, tis, imovel, documento, job, extracao,
                     kwargs_job):
    """Resposta do ramo sem atos da entrada; ``None`` volta ao ramo antigo.

    O chamador já garantiu ``job.status`` em ``extraido/revisado`` e que
    ``atos_da_revisao`` é vazio; aqui distingue a confirmação simples (flag
    destrava), o formulário das escolhas de cabeçalho e o ramo antigo.
    """
    if job.status != estados.EXTRAIDO:
        return None
    if services.pode_finalizar_sem_atos(extracao):
        return renderizar_sem_atos(
            request, tis, imovel, documento, job, extracao, kwargs_job,
        )
    escolhas = pendencias_de_escolha(extracao)
    if escolhas:
        return renderizar_sem_atos(
            request, tis, imovel, documento, job, extracao, kwargs_job,
            escolhas=escolhas,
        )
    return None


def _rotulo_cartorio(cartorio):
    local = '/'.join(
        parte for parte in (cartorio.cidade, cartorio.estado) if parte
    )
    return f'{cartorio.nome} — {local}' if local else cartorio.nome


def _opcoes_de_cadastro(escolhas):
    """Cada pendência com as opções nomeadas — uma query por tipo.

    Mesma técnica do ``_anexar_opcoes_cadastro`` da tela de cards aposentada:
    nunca consulta o banco no template e nunca expõe documento de pessoa.
    """
    ids_pessoas = {
        pk
        for _chave, campo in escolhas if campo.tipo_valor == 'parte'
        for pk in (campo.match_candidatos or [])
    }
    ids_cartorios = {
        pk
        for _chave, campo in escolhas if campo.tipo_valor == 'cartorio'
        for pk in (campo.match_candidatos or [])
    }
    rotulos_pessoas = {
        p.pk: p.nome
        for p in Pessoas.objects.filter(pk__in=ids_pessoas).only('nome')
    }
    cartorios = {
        c.pk: c
        for c in Cartorios.objects.filter(pk__in=ids_cartorios).only(
            'nome', 'cidade', 'estado', 'cns',
        )
    }
    itens = []
    for chave, campo in escolhas:
        if campo.tipo_valor == 'parte':
            rotulos = rotulos_pessoas
            escolhido = campo.pessoa_escolhida_id
            nome_digitado = ''
        else:
            rotulos = {
                pk: _rotulo_cartorio(c) for pk, c in cartorios.items()
            }
            escolhido = campo.cartorio_escolhido_id
            valor_atual = (
                campo.valor_final
                if campo.valor_final is not None else campo.normalized
            )
            nome_digitado = valor_atual or ''
        itens.append({
            'chave': chave,
            'rotulo': revisao.rotulo_de_campo(chave),
            'opcoes': [
                {'id': pk, 'rotulo': rotulos.get(pk, 'Cadastro indisponível')}
                for pk in (campo.match_candidatos or [])
            ],
            'escolhido': escolhido,
            'criar_novo': campo.criar_novo,
            'nome_digitado': nome_digitado,
        })
    return itens


def renderizar_sem_atos(request, tis, imovel, documento, job, extracao,
                        kwargs_job, escolhas=None):
    """GET da confirmação "concluir sem atos" (#262) pela revisão (#341).

    Sem ``escolhas``, só o botão de concluir. Com elas (pendências de
    escolha de cadastro do cabeçalho), a mesma página ganha o formulário
    que as resolve. O POST desta página é ``revisar_sem_atos_ocr``, que
    revalida o ``versao`` sob trava.
    """
    return views.render(request, 'ia_ocr/revisao_sem_atos.html', {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'job': job,
        'extracao': extracao,
        'versao': services.versao_bloco(extracao),
        'escolhas': _opcoes_de_cadastro(escolhas or []),
        'url_sem_atos': reverse('revisar_sem_atos_ocr', kwargs=kwargs_job),
        'url_texto': _url_tela(kwargs_job),
        'url_documento': _url_documento(tis, imovel, documento),
    })


def _decisao_da_escolha(campo, bruto, nome, marcar):
    """Decisão do contrato de ``salvar_bloco`` para UM campo; ``None`` sem
    decisão, ``(True, ...)`` marcado quando "criar novo" ficou sem nome."""
    escolha = {'criar_novo': False}
    if marcar or bruto == SENTINELA_CRIAR_NOVO:
        escolha['criar_novo'] = True
        decisao = {'incluir': True, 'escolha': escolha}
        if campo.tipo_valor == 'cartorio':
            # O nome do novo cartório vai no próprio campo; sem ele nada
            # nasce (a pendência ``criar_novo_sem_nome`` continuaria). Para
            # parte o nome mora na folha ``nome`` — que não existe sem atos.
            if not nome:
                return True, True
            decisao['valor'] = nome
        decisao['versao'] = services.versao_linha(campo)
        return decisao, False
    if bruto.isdigit():
        id_escolhido = int(bruto)
        if campo.tipo_valor == 'parte':
            escolha['pessoa_escolhida_id'] = id_escolhido
        else:
            escolha['cartorio_escolhido_id'] = id_escolhido
        return {
            'incluir': True, 'escolha': escolha,
            'versao': services.versao_linha(campo),
        }, False
    return None, False


def _decisoes_de_escolha(extracao, post):
    """POST do formulário → decisões; ``(decisoes, incompletos)``.

    ``incompletos`` são as chaves com "criar novo" SEM nome: o chamador
    recusa o POST inteiro antes de tocar no banco.
    """
    por_chave = {campo.chave: campo for campo in extracao.campos.all()}
    decisoes = {}
    incompletos = []
    vistas = set()
    for pendencia in revisao.pendencias_sem_atos(extracao):
        if pendencia['motivo'] not in _MOTIVOS_DE_ESCOLHA:
            continue
        chave = pendencia['chave']
        if chave in vistas:
            continue
        vistas.add(chave)
        campo = por_chave.get(chave)
        if campo is None:
            continue
        decisao, incompleto = _decisao_da_escolha(
            campo,
            (post.get(f'escolha:{chave}') or '').strip(),
            (post.get(f'nome:{chave}') or '').strip(),
            f'criar_novo:{chave}' in post,
        )
        if incompleto:
            incompletos.append(chave)
        elif decisao is not None:
            decisoes[chave] = decisao
    return decisoes, incompletos


@login_required
@require_POST
def revisar_sem_atos_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Conclui a revisão sem atos (#262), resolvendo antes as escolhas (#341).

    O ``versao`` exibido no GET valida o estado sob trava; as decisões do
    formulário (quando houver) e a finalização compartilham UMA transação —
    em qualquer falha nada é gravado, nem escolha parcial.
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
    decisoes, incompletos = _decisoes_de_escolha(extracao, request.POST)
    if incompletos:
        messages.warning(request, MENSAGEM_CRIAR_NOVO_SEM_NOME)
        return redirect(entrada)
    try:
        with transaction.atomic():
            if decisoes:
                travada, versao_salva, _partes, _novos = services.salvar_bloco(
                    extracao, decisoes, request.user, versao,
                )
                services.finalizar_revisao(
                    travada, request.user, versao_cliente=versao_salva,
                    confirmar_sem_atos=True,
                )
            else:
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
    except revisao.EscolhaIncompativel:
        # Inclui EscolhaInvalida: id fora dos candidatos da página atual
        # (página aberta antes de a identidade da parte mudar, p. ex.).
        messages.warning(request, (
            '⚠️ A escolha enviada não vale mais para esta revisão; '
            'recarregue a página. Nada foi gravado.'
        ))
        return redirect(entrada)
    except valores.ValorInvalido:
        messages.warning(request, (
            '⚠️ Há valor acima do limite do destino; corrija e reenvie. '
            'Nada foi gravado.'
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
