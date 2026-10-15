"""Serviços da fila de OCR: criação idempotente, claim, reap e finalização.

Nenhum log aqui carrega texto de documento ou dados do PDF (PII): apenas
job_id, status, tentativa e códigos de erro estáveis. O que vem de fora
(backend) é sanitizado antes de virar log ou coluna.
"""

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import estados
from .backends import OcrBackendError, ResultadoOcr
from .estados import TransicaoConcorrente
from .models import (
    ORIGEM_CHOICES, OcrJob, OcrJobTransicao, PaginaOcr,
    PendenciaLimpezaArquivo,
)

logger = logging.getLogger(__name__)

LIMITE_TIMINGS_CHAVES = 20
# GET /v1/ocr/jobs/{jobId} e .../result em
# ocr-service/contracts/ocr-api.openapi.yaml. Chaves novas exigem atualização
# conjunta do contrato e desta allowlist.
CHAVES_TIMING_PERMITIDAS = frozenset({
    'download_and_validation',
    'inference',
    'total',
})

CODIGOS_ERRO_PERMITIDOS = frozenset({
    # Contrato OCR v1.0.1 (ocr-service/contracts/ocr-api.openapi.yaml).
    'INVALID_INPUT',
    'INVALID_FILE_URL',
    'SOURCE_HOST_NOT_ALLOWED',
    'DOWNLOAD_TIMEOUT',
    'DOWNLOAD_FAILED',
    'TOO_MANY_REDIRECTS',
    'FILE_TOO_LARGE',
    'EMPTY_FILE',
    'INVALID_PDF',
    'ENCRYPTED_PDF',
    'TOO_MANY_PAGES',
    'PDF_PAGE_TOO_LARGE',
    'INVALID_OCR_RESULT',
    'EMPTY_OCR_RESULT',
    'OUTPUT_TOO_LARGE',
    'JOB_NOT_FOUND',
    'JOB_ID_CONFLICT',
    'JOB_TIMEOUT',
    'UNSUPPORTED_MEDIA_TYPE',
    'UNAUTHORIZED',
    'INFERENCE_FAILED',
    # Códigos internos/estáveis usados pela fila e pelo gateway.
    'QUEUE_FULL',
    'SERVICE_UNAVAILABLE',
    'WORKER_TIMEOUT',
    'BACKEND_NAO_IMPLEMENTADO',
    'ERRO_INTERNO',
})

MENSAGENS_ERRO_SEGURAS = {
    'INVALID_INPUT': 'entrada inválida para processamento OCR',
    'INVALID_FILE_URL': 'URL de arquivo inválida',
    'SOURCE_HOST_NOT_ALLOWED': 'origem do arquivo não permitida',
    'DOWNLOAD_TIMEOUT': 'tempo limite excedido ao baixar arquivo',
    'DOWNLOAD_FAILED': 'falha ao baixar arquivo para OCR',
    'TOO_MANY_REDIRECTS': 'redirecionamentos excessivos ao baixar arquivo',
    'FILE_TOO_LARGE': 'arquivo excede o limite de tamanho do serviço',
    'EMPTY_FILE': 'arquivo vazio',
    'INVALID_PDF': 'PDF inválido',
    'ENCRYPTED_PDF': 'PDF criptografado não suportado',
    'TOO_MANY_PAGES': 'documento excede o limite de páginas do serviço',
    'PDF_PAGE_TOO_LARGE': 'página do PDF excede o limite do serviço',
    'INVALID_OCR_RESULT': 'resultado OCR inválido',
    'EMPTY_OCR_RESULT': 'resultado OCR vazio',
    'OUTPUT_TOO_LARGE': 'resultado OCR excede o limite do serviço',
    'JOB_NOT_FOUND': 'job OCR não encontrado',
    'JOB_ID_CONFLICT': 'identificador do job já vinculado a outro arquivo',
    'JOB_TIMEOUT': 'serviço OCR excedeu o tempo limite do job',
    'UNSUPPORTED_MEDIA_TYPE': 'tipo de arquivo não suportado pelo serviço OCR',
    'UNAUTHORIZED': 'acesso ao serviço OCR não autorizado',
    'INFERENCE_FAILED': 'falha na inferência OCR',
    'QUEUE_FULL': 'fila do serviço OCR cheia',
    'SERVICE_UNAVAILABLE': 'serviço OCR indisponível',
    'WORKER_TIMEOUT': 'worker OCR excedeu o tempo limite',
    'BACKEND_NAO_IMPLEMENTADO': 'backend OCR não implementado',
    'ERRO_INTERNO': 'falha interna no processamento do job',
}

_ORIGENS_VALIDAS = frozenset(valor for valor, _rotulo in ORIGEM_CHOICES)


def _sanitizar_timings(timings_ms):
    """Mantém apenas métricas contratuais numéricas, no máximo 20."""
    if not isinstance(timings_ms, dict):
        return None
    sanitizado = {}
    for chave, valor in timings_ms.items():
        if len(sanitizado) >= LIMITE_TIMINGS_CHAVES:
            break
        if (
            chave in CHAVES_TIMING_PERMITIDAS
            and isinstance(valor, (int, float))
            and not isinstance(valor, bool)
        ):
            sanitizado[chave] = valor
    return sanitizado


def _sanitizar_erro_codigo(codigo):
    """Aceita somente códigos estáveis explicitamente allowlisted."""
    if isinstance(codigo, str) and codigo in CODIGOS_ERRO_PERMITIDOS:
        return codigo
    return 'ERRO_INTERNO'


def _mensagem_erro_segura(codigo):
    """Retorna texto local fixo; nunca usa mensagem fornecida pelo backend."""
    return MENSAGENS_ERRO_SEGURAS.get(
        codigo, MENSAGENS_ERRO_SEGURAS['ERRO_INTERNO']
    )


class JobIdConflitante(Exception):
    """job_id já existe vinculado a outro documento digital."""


def registrar_pendencia_limpeza(
    documento_digital_id, caminho_storage, documento_id=None
):
    """Registra a intenção de limpeza antes da remoção física do arquivo.

    A intenção é gravada na mesma transação que exclui o DocumentoDigital.
    Ela é removida quando a limpeza física conclui e permanece, para retomada
    pelo suporte, somente quando essa limpeza falha. Só o caminho fica no banco,
    nunca em log, para não expor o nome do arquivo fora do sistema.
    """
    return PendenciaLimpezaArquivo.objects.create(
        documento_digital_id=documento_digital_id,
        documento_id=documento_id,
        caminho_storage=caminho_storage,
    )


def criar_job(documento_digital, job_id=None, criado_por=None, origem='ocr'):
    """Cria (ou recupera) um job de OCR de forma idempotente por job_id.

    O lookup é somente por job_id; os metadados vão em `defaults` — filtro
    divergente no get_or_create causaria IntegrityError na segunda chamada.
    """
    if job_id is None:
        job_id = uuid.uuid4()
    job, criado = OcrJob.objects.get_or_create(
        job_id=job_id,
        defaults={
            'documento_digital': documento_digital,
            'criado_por': criado_por,
            'origem': origem,
            'status': estados.PENDENTE,
        },
    )
    if not criado and job.documento_digital_id != documento_digital.pk:
        raise JobIdConflitante(
            f'job_id {job_id} já existe para outro documento digital.'
        )
    return job, criado


def claim_proximo_job(timeout_s=None):
    """Reivindica (CAS) o job mais antigo e persiste seu prazo de lease.

    O ``lease_expira_em`` é gravado no mesmo CAS que muda o status; portanto,
    todo claim novo possui prazo explícito mesmo quando o timeout default é
    usado. O lock apenas reduz disputa: a correção continua vindo do CAS.
    """
    agora = timezone.now()
    if timeout_s is None:
        timeout_s = settings.OCR_JOB_TIMEOUT_SECONDS
    lease_expira_em = agora + timedelta(seconds=timeout_s)
    with transaction.atomic():
        tentados = set()
        while True:
            candidato = (
                OcrJob.objects.select_for_update(skip_locked=True)
                .filter(status=estados.PENDENTE)
                .exclude(pk__in=tentados)
                .order_by('criado_em', 'pk')
                .first()
            )
            if candidato is None or candidato.pk in tentados:
                return None
            tentados.add(candidato.pk)
            rowcount = (
                OcrJob.objects
                .filter(pk=candidato.pk, status=estados.PENDENTE)
                .update(
                    status=estados.EM_EXECUCAO,
                    atualizado_em=agora,
                    lease_expira_em=lease_expira_em,
                )
            )
            if rowcount == 1:
                OcrJobTransicao.objects.create(
                    ocr_job_id=candidato.pk,
                    de_status=estados.PENDENTE,
                    para_status=estados.EM_EXECUCAO,
                    motivo='claim do worker',
                )
                return OcrJob.objects.get(pk=candidato.pk)


def reap_jobs_expirados(timeout_s=None):
    """Reapa leases explícitos vencidos e jobs legados pelo timestamp.

    O fallback ``atualizado_em + timeout_s`` vale somente para linhas criadas
    antes da migração, cujo ``lease_expira_em`` ainda é NULL. Cada candidato
    mantém a transição CAS individual da I-1.
    """
    agora = timezone.now()
    if timeout_s is None:
        timeout_s = settings.OCR_JOB_TIMEOUT_SECONDS
    limite_legado = agora - timedelta(seconds=timeout_s)
    reapados = 0
    expirados = OcrJob.objects.filter(status=estados.EM_EXECUCAO).filter(
        Q(lease_expira_em__lt=agora)
        | Q(lease_expira_em__isnull=True, atualizado_em__lt=limite_legado)
    )
    for job in expirados:
        try:
            job.transicionar(
                estados.FALHOU,
                motivo='WORKER_TIMEOUT',
                tentativa=job.tentativa,
                erro_codigo='WORKER_TIMEOUT',
                erro_mensagem=_mensagem_erro_segura('WORKER_TIMEOUT'),
            )
        except TransicaoConcorrente:
            continue
        reapados += 1
    return reapados


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
