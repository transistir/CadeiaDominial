"""Importação da revisão finalizada em lançamentos (``importar_job_ocr``,
I-6) e a finalização da revisão sem pendências (``finalizar_revisao_ocr``,
issue #262).

Extraídos do monólito de views (etapa 3, limite de 400 linhas). O módulo
NÃO se chama ``importacao``: o call site usa o MÓDULO/pacote irmão
``ia_ocr.importacao`` como atributo (``importacao.importar(...)``,
``importacao.ImportacaoInvalida``), e um submódulo de mesmo nome
sombrearia esse nome dentro do pacote. Nenhum nome daqui é alvo de patch
pelo pacote: helpers de outros módulos vêm por import direto do dono e
são chamada direta; o decorator ``_respostas_json_ocr`` é aplicado em
tempo de IMPORTAÇÃO, então também vem por import direto do módulo dono.
Ver o docstring do ``__init__.py``.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from .. import importacao, revisao, services
from ..estados import TransicaoConcorrente, TransicaoInvalida
from .jobs import _contexto_job
from .resposta import _respostas_json_ocr


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
