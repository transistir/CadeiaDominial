"""Finalização do job pelo worker: sucesso ou falha condicionada ao lease.

Resultado válido (uma página por número, 1..N) grava páginas + transição
auditada; violação de contrato e exceções viram o erro sanitizado. Se o
lease mudou no meio do processamento, o resultado é DESCARTADO (só log).
"""

import logging

from django.db import transaction
from django.utils import timezone

from .. import estados
from ..backends import OcrBackendError, ResultadoOcr
from ..models import ORIGEM_CHOICES, OcrJob, OcrJobTransicao, PaginaOcr
from .erros import _mensagem_erro_segura, _sanitizar_erro_codigo, _sanitizar_timings

logger = logging.getLogger(__name__)

_ORIGENS_VALIDAS = frozenset(valor for valor, _rotulo in ORIGEM_CHOICES)


def finalizar(job, resultado_ou_erro, tentativa):
    """Finaliza um job claimado, condicionada ao lease (status + tentativa).

    Se o lease mudou (reap/retry no meio do processamento), o resultado do
    worker antigo é DESCARTADO: nada é gravado, só log com job_id/tentativa.
    Um resultado válido contém exatamente uma entrada para cada página,
    numerada de 1 a ``page_count``, sem duplicatas. ``paginas`` é materializado
    uma única vez para que iteráveis consumíveis, como geradores, sejam seguros.
    Retorna True se a finalização foi aplicada.
    """
    agora = timezone.now()
    if isinstance(resultado_ou_erro, ResultadoOcr):
        resultado = resultado_ou_erro
        try:
            paginas = list(resultado.paginas)
            numeros_paginas = [pagina['numero_pagina'] for pagina in paginas]
        except (KeyError, TypeError):
            paginas = []
            numeros_paginas = []
        page_count_valido = (
            isinstance(resultado.page_count, int)
            and not isinstance(resultado.page_count, bool)
            and resultado.page_count >= 1
        )
        paginas_validas = (
            page_count_valido
            and len(numeros_paginas) == resultado.page_count
            and all(
                isinstance(numero, int)
                and not isinstance(numero, bool)
                and 1 <= numero <= resultado.page_count
                for numero in numeros_paginas
            )
            and len(set(numeros_paginas)) == len(numeros_paginas)
        )
        if not paginas_validas:
            # O contrato exige uma entrada por página, numerada em 1..N.
            # Converte a violação no caminho de erro contratual já sanitizado.
            resultado_ou_erro = OcrBackendError(
                'INVALID_OCR_RESULT', 'páginas do resultado OCR inválidas'
            )

    with transaction.atomic():
        if (
            isinstance(resultado_ou_erro, ResultadoOcr)
            and (
                resultado_ou_erro.origem is None
                or resultado_ou_erro.origem in _ORIGENS_VALIDAS
            )
        ):
            resultado = resultado_ou_erro
            campos = {
                'status': estados.CONCLUIDO,
                'atualizado_em': agora,
                'sha256_pdf': resultado.sha256_pdf,
                'page_count': resultado.page_count,
                'timings_ms': _sanitizar_timings(resultado.timings_ms),
            }
            if resultado.origem is not None:
                # Sem origem no resultado: a origem definida no criar_job
                # (ex.: texto_embutido da I-2) permanece.
                campos['origem'] = resultado.origem
            if type(resultado.dpi) is int and resultado.dpi > 0:
                # DPI efetivo do OCR (o remoto, ou o solicitado como fallback):
                # extração e conversão de bbox dependem dele. None (ex.:
                # texto_embutido) não persiste — não houve raster.
                campos['dpi'] = resultado.dpi
            rowcount = OcrJob.objects.filter(
                pk=job.pk, status=estados.EM_EXECUCAO, tentativa=tentativa,
            ).update(**campos)
            if rowcount == 0:
                _logar_finalizacao_descartada(job, tentativa)
                return False
            PaginaOcr.objects.bulk_create(
                PaginaOcr(
                    ocr_job_id=job.pk,
                    numero_pagina=pagina['numero_pagina'],
                    texto_ocr=pagina.get('texto', ''),
                    blocos=pagina.get('blocos'),
                )
                for pagina in paginas
            )
            OcrJobTransicao.objects.create(
                ocr_job_id=job.pk,
                de_status=estados.EM_EXECUCAO,
                para_status=estados.CONCLUIDO,
                motivo='processado com sucesso',
            )
            timings = campos['timings_ms'] or {}
            if 'total' in timings:
                logger.info(
                    'job_id=%s status=concluido page_count=%s total_ms=%s',
                    job.job_id, resultado.page_count, timings['total'],
                )
            else:
                logger.info(
                    'job_id=%s status=concluido page_count=%s',
                    job.job_id, resultado.page_count,
                )
            return True

        excecao = resultado_ou_erro
        if isinstance(excecao, OcrBackendError):
            codigo = _sanitizar_erro_codigo(excecao.codigo)
        else:
            # Resultado com origem inválida e exceções inesperadas usam o
            # mesmo erro local. Nem o valor inválido nem str(exc) são usados.
            codigo = 'ERRO_INTERNO'
        mensagem = _mensagem_erro_segura(codigo)
        rowcount = OcrJob.objects.filter(
            pk=job.pk, status=estados.EM_EXECUCAO, tentativa=tentativa,
        ).update(
            status=estados.FALHOU,
            atualizado_em=agora,
            erro_codigo=codigo,
            erro_mensagem=mensagem,
        )
        if rowcount == 0:
            _logar_finalizacao_descartada(job, tentativa)
            return False
        OcrJobTransicao.objects.create(
            ocr_job_id=job.pk,
            de_status=estados.EM_EXECUCAO,
            para_status=estados.FALHOU,
            motivo=codigo,
        )
        logger.warning('job_id=%s status=falhou erro_codigo=%s', job.job_id, codigo)
        return True


def marcar_falha_interna(job, tentativa):
    """Último recurso quando a própria finalização falhou (ex.: DatabaseError
    ao persistir páginas): marca o job falhou/ERRO_INTERNO numa NOVA transação
    (a anterior já sofreu rollback), condicionada ao mesmo lease.

    Levanta se não conseguir — quem chama decide (log + reap como rede de
    segurança). Retorna True se marcou, False se o lease já não é nosso.
    """
    agora = timezone.now()
    with transaction.atomic():
        rowcount = OcrJob.objects.filter(
            pk=job.pk, status=estados.EM_EXECUCAO, tentativa=tentativa,
        ).update(
            status=estados.FALHOU,
            atualizado_em=agora,
            erro_codigo='ERRO_INTERNO',
            erro_mensagem=_mensagem_erro_segura('ERRO_INTERNO'),
        )
        if rowcount == 0:
            _logar_finalizacao_descartada(job, tentativa)
            return False
        OcrJobTransicao.objects.create(
            ocr_job_id=job.pk,
            de_status=estados.EM_EXECUCAO,
            para_status=estados.FALHOU,
            motivo='ERRO_INTERNO',
        )
        logger.warning(
            'job_id=%s status=falhou erro_codigo=ERRO_INTERNO '
            '(finalizacao original falhou ao persistir)',
            job.job_id,
        )
        return True


def _logar_finalizacao_descartada(job, tentativa):
    logger.warning(
        'job_id=%s finalizacao descartada: lease mudou (tentativa=%s)',
        job.job_id, tentativa,
    )
