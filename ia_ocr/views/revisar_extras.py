"""Complementos da revisão por ato: importação da cadeia duplicada (#341).

A conclusão sem atos saiu deste módulo no MUST-FIX do review Codex da
#341: está em ``revisar_sem_atos`` (limite de 400 linhas), que importa
daqui só ``_url_documento``.
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from dominial.models import Documento, DocumentoDigital
from dominial.services.lancamento_duplicata_service import LancamentoDuplicataService

from .. import estados, revisao_ato, services, views
from .jobs import _contexto_job, _kwargs_job

logger = logging.getLogger(__name__)


class _DuplicataRecusada(Exception):
    """Interrompe a transação externa sem gravar importação parcial."""

    def __init__(self, mensagem=''):
        super().__init__(mensagem)
        self.mensagem = mensagem


def mostrar_duplicata(request, tis, imovel, documento, extracao, kwargs_job,
                       indice, duplicata_info):
    """Renderiza a confirmação e conserva o POST como rascunho do ato."""
    revisao_ato.guardar_rascunho(request, extracao, indice)
    dados = _dados_do_formulario(request.POST)
    return views.render(
        request, 'dominial/duplicata_importacao.html', {
            'tis': tis,
            'imovel': imovel,
            'documento': documento,
            'duplicata_info': LancamentoDuplicataService.obter_dados_duplicata_para_template(
                duplicata_info,
            ),
            'form_data': dados,
            'campos_preservados': _campos_preservados(request.POST),
            'extracao_id': extracao.pk,
            'url_importar_duplicata': reverse(
                'revisar_ato_duplicata_ocr', kwargs={**kwargs_job, 'indice': indice},
            ),
            'url_cancelar_duplicata': reverse(
                'revisar_ato_ocr', kwargs={**kwargs_job, 'indice': indice},
            ),
        },
    )


@login_required
@require_POST
def revisar_ato_duplicata_ocr(request, tis_id, imovel_id, documento_id, job_id,
                               indice):
    """Importa a cadeia duplicada e salva o ato como uma única operação."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id,
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)
    try:
        with transaction.atomic():
            DocumentoDigital.objects.select_for_update().get(pk=job.documento_digital_id)
            extracao = services._travar_extracao_revisao(job.extracao_vigente())
            if (request.POST.get('extracao_id') or '').strip() != str(extracao.pk):
                raise services.ExtracaoRecusada('extracao_nao_vigente')
            if extracao.ocr_job.status not in (estados.EXTRAIDO, estados.REVISADO):
                raise _DuplicataRecusada()
            ato = next(
                (item for item in revisao_ato.atos_da_revisao(extracao)
                 if item['indice'] == indice),
                None,
            )
            if ato and ato['estado'] == revisao_ato.ESTADO_IMPORTADO:
                raise _DuplicataRecusada('Este ato já foi salvo.')
            Documento.objects.select_for_update().get(pk=documento.pk)
            importacao = LancamentoDuplicataService.processar_importacao_duplicata(
                request, documento, request.user,
            )
            erros = importacao.get('erros') or ()
            if erros:
                raise _DuplicataRecusada('; '.join(erros))
            if not importacao.get('sucesso'):
                raise _DuplicataRecusada(
                    importacao.get('mensagem') or importacao.get('erro') or '',
                )
            resultado = revisao_ato.salvar_ato(
                request, tis, imovel, documento, job, extracao, indice,
                apos_importacao=True,
            )
            if resultado.situacao == 'ja_salvo':
                raise _DuplicataRecusada(resultado.mensagem or 'Este ato já foi salvo.')
            if resultado.situacao != 'salvo':
                raise _DuplicataRecusada(resultado.mensagem)
    except services.ExtracaoRecusada:
        messages.warning(request, '⚠️ A extração deste documento mudou; recarregue a revisão.')
        return redirect(reverse('revisar_job_ocr', kwargs=kwargs_job))
    except _DuplicataRecusada as erro:
        motivo = f' {erro.mensagem}' if erro.mensagem else ''
        messages.error(
            request,
            f'❌ Não foi possível importar a duplicata.{motivo} Nada foi gravado.',
        )
        return redirect(reverse('revisar_ato_ocr', kwargs={**kwargs_job, 'indice': indice}))
    except Exception:
        logger.exception('Erro ao importar duplicata da revisão (job=%s, ato=%s)', job.pk, indice)
        messages.error(request, '❌ Erro interno ao importar a duplicata. Nada foi gravado.')
        return redirect(reverse('revisar_ato_ocr', kwargs={**kwargs_job, 'indice': indice}))

    revisao_ato.limpar_rascunho(request, extracao, indice)
    messages.success(request, '✅ Cadeia duplicada importada e ato salvo como lançamento.')
    return redirect(reverse('revisar_job_ocr', kwargs=kwargs_job))


def _url_documento(tis, imovel, documento):
    """URL da tela do documento — mesma forma do módulo ``revisar``."""
    return reverse('documento_detalhado', kwargs={
        'tis_id': tis.pk, 'imovel_id': imovel.pk, 'documento_id': documento.pk,
    })


def _dados_do_formulario(post):
    """Formato histórico da tela de duplicata, preenchido pelo POST original."""
    simples = (
        'tipo_lancamento', 'numero_lancamento', 'numero_lancamento_simples',
        'data', 'observacoes', 'livro_documento', 'folha_documento', 'cartorio',
        'cartorio_nome', 'area', 'descricao', 'forma_transacao', 'titulo_transacao',
        'cartorio_transmissao', 'cartorio_transmissao_nome', 'livro_transacao',
        'folha_transacao', 'data_transacao',
    )
    listas = (
        'origem_completa', 'cartorio_origem', 'cartorio_origem_nome',
        'livro_origem', 'folha_origem', 'transmitente', 'transmitente_nome',
        'adquirente', 'adquirente_nome', 'fim_cadeia', 'tipo_fim_cadeia',
        'classificacao_fim_cadeia', 'sigla_patrimonio_publico',
        'info_adicional_fim_cadeia', 'especificacao_fim_cadeia',
    )
    dados = {nome: post.get(nome) for nome in simples}
    dados.update({nome: post.getlist(f'{nome}[]') for nome in listas})
    return dados


def _campos_preservados(post):
    """Pares nome/valor do POST para a confirmação, sem seus próprios campos."""
    excluidos = {
        'csrfmiddlewaretoken', 'extracao_id', 'documento_origem_id',
        'documentos_importaveis[]',
    }
    return [
        (nome, valor)
        for nome, valores in post.lists() if nome not in excluidos
        for valor in valores
    ]
