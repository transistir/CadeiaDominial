"""Ciclo de vida do job na fila: criação idempotente, reprocessamento,
claim (CAS + lease) e reap de leases expirados.
"""

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from dominial.models import DocumentoDigital

from .. import estados
from ..estados import TransicaoConcorrente
from ..models import OcrJob, OcrJobTransicao
from .erros import JobEmExecucao, JobIdConflitante, _mensagem_erro_segura

logger = logging.getLogger(__name__)


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


def reprocessar(job, usuario=None, forcar_ocr=True):
    """Cria um novo job de OCR para o documento do job recebido.

    O job anterior permanece INTOCADO: páginas (inclusive confirmadas) e
    auditoria não são reescritas — reprocessar nunca altera histórico. Se o
    próprio job ainda está pendente/em_execucao, recusa com ``JobEmExecucao``
    em vez de criar um sucessor reivindicável. Se já existe OUTRO job do
    documento em pendente/em_execucao, nada é criado e o job vigente é
    devolvido com ``False`` (mesmo estilo de ``criar_job``).
    A checagem e a criação são serializadas por ``select_for_update`` no
    DocumentoDigital: sem constraint parcial, que quebraria a fila da I-1
    (vários pendentes legítimos para o mesmo documento).
    """
    documento_id = job.documento_digital_id
    with transaction.atomic():
        DocumentoDigital.objects.select_for_update().get(pk=documento_id)
        origem_ativa = OcrJob.objects.filter(
            pk=job.pk,
            status__in=[estados.PENDENTE, estados.EM_EXECUCAO],
        ).exists()
        if origem_ativa:
            raise JobEmExecucao(
                'O job de origem ainda está pendente ou em execução.'
            )
        vigente = (
            OcrJob.objects
            .filter(
                documento_digital_id=documento_id,
                status__in=[estados.PENDENTE, estados.EM_EXECUCAO],
            )
            .first()
        )
        if vigente is not None:
            return vigente, False
        novo = OcrJob.objects.create(
            documento_digital_id=documento_id,
            criado_por=usuario,
            origem='ocr',
            forcar_ocr=forcar_ocr,
            status=estados.PENDENTE,
        )
        return novo, True


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
