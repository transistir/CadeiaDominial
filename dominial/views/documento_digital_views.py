import logging
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import DatabaseError, transaction
from django.db.models import ProtectedError
from django.http import HttpResponse, Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils.http import content_disposition_header

from ..models import DocumentoDigital, Documento, Imovel, TIs
from ia_ocr.estados import EM_EXECUCAO, FALHOU, PENDENTE
from ia_ocr.models import OcrJob
from ia_ocr.services import criar_job, registrar_pendencia_limpeza


logger = logging.getLogger(__name__)


TIPOS_PERMITIDOS = {
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/webp',
}

TAMANHO_MAXIMO = 20 * 1024 * 1024  # 20MB


def _validar_magic_bytes(arquivo):
    """Valida o conteúdo real do arquivo por assinatura binária."""
    header = arquivo.read(12)
    arquivo.seek(0)
    # PDF: %PDF-
    if header[:5] == b'%PDF-':
        return True
    # PNG: \x89PNG\r\n\x1a\n
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    # JPEG: \xFF\xD8\xFF
    if header[:3] == b'\xFF\xD8\xFF':
        return True
    # WebP: RIFF....WEBP
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return True
    return False


def _get_contexto_documento(request, tis_id, imovel_id, documento_id):
    """Helper: resolve TI, Imóvel e Documento com validação de hierarquia."""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel.objects.for_user(request.user), id=imovel_id, terra_indigena_id=tis)
    documento = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    return tis, imovel, documento


@login_required
@require_http_methods(["GET", "POST"])
def upload_documento_digital(request, tis_id, imovel_id, documento_id):
    """Upload de arquivo digital vinculado a um documento."""
    tis, imovel, documento = _get_contexto_documento(request, tis_id, imovel_id, documento_id)

    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')

        if not arquivo:
            messages.error(request, 'Nenhum arquivo selecionado.')
            return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)

        # Validar tipo MIME
        tipo_mime = mimetypes.guess_type(arquivo.name)[0] or 'application/octet-stream'
        if tipo_mime not in TIPOS_PERMITIDOS:
            messages.error(request, f'Tipo de arquivo não permitido: {tipo_mime}. Aceitos: PDF, PNG, JPEG, WebP.')
            return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)

        # Validar magic bytes (conteúdo real)
        if not _validar_magic_bytes(arquivo):
            messages.error(request, f'Conteúdo do arquivo não corresponde ao tipo declarado ({tipo_mime}). Arquivo rejeitado.')
            return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)

        # Validar tamanho
        if arquivo.size > TAMANHO_MAXIMO:
            messages.error(request, f'Arquivo muito grande ({arquivo.size / (1024*1024):.1f} MB). Limite: 20 MB.')
            return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)

        # Criar o registro
        DocumentoDigital.objects.create(
            documento=documento,
            arquivo=arquivo,
            nome_original=arquivo.name,
            tipo_mime=tipo_mime,
            tamanho_bytes=arquivo.size,
            upload_por=request.user,
        )

        messages.success(request, f'Arquivo "{arquivo.name}" anexado com sucesso.')
        return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)

    # GET: renderiza formulário simples
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        # Card de OCR (I-3): só PDFs oferecem extração de texto.
        'arquivos_pdf': documento.arquivos_digitais.filter(tipo_mime='application/pdf'),
    }
    return render(request, 'dominial/upload_documento_digital.html', context)


@login_required
def servir_documento_digital(request, tis_id, imovel_id, documento_id, arquivo_id):
    """Serve o arquivo via X-Accel-Redirect (nginx internal) — nunca expõe URL pública."""
    tis, imovel, documento = _get_contexto_documento(request, tis_id, imovel_id, documento_id)
    arquivo = get_object_or_404(DocumentoDigital, id=arquivo_id, documento=documento)

    if not arquivo.arquivo:
        raise Http404("Arquivo não encontrado no storage.")

    response = HttpResponse()
    response['X-Accel-Redirect'] = arquivo.arquivo.url
    response['Content-Type'] = arquivo.tipo_mime
    # `nome_original` vem do upload: interpolar direto deixa aspas e quebras de
    # linha injetarem headers. O helper do Django faz o escaping/RFC 5987.
    response['Content-Disposition'] = content_disposition_header(
        as_attachment=False, filename=arquivo.nome_original
    )
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@require_POST
def excluir_documento_digital(request, tis_id, imovel_id, documento_id, arquivo_id):
    """Exclui um arquivo digital (POST apenas)."""
    tis, imovel, documento = _get_contexto_documento(request, tis_id, imovel_id, documento_id)
    arquivo = get_object_or_404(DocumentoDigital, id=arquivo_id, documento=documento)

    nome = arquivo.nome_original
    # Registro e intenção de limpeza formam uma unidade: se a pendência não
    # puder ser persistida, o DocumentoDigital continua disponível.
    caminho = arquivo.arquivo.name if arquivo.arquivo else None
    try:
        with transaction.atomic():
            arquivo.delete()
            pendencia = (
                registrar_pendencia_limpeza(
                    documento_digital_id=arquivo_id,
                    documento_id=documento_id,
                    caminho_storage=caminho,
                )
                if caminho
                else None
            )
    except ProtectedError:
        messages.error(
            request,
            f'Arquivo "{nome}" possui processamento de OCR vinculado e não pode ser '
            'excluído. Remova o processamento de OCR antes de excluir o arquivo.'
        )
        return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)
    except DatabaseError:
        logger.warning(
            'Falha ao excluir o arquivo digital; arquivo_id=%s', arquivo_id
        )
        messages.error(
            request, 'Não foi possível excluir o arquivo digital. Tente novamente.'
        )
        return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)

    # A intenção já está durável; falhas físicas deixam a pendência para retry.
    falha_limpeza_fisica = False
    if caminho:
        try:
            arquivo.arquivo.delete(save=False)
        except Exception:
            logger.warning(
                'Falha na limpeza física do storage; arquivo_id=%s', arquivo_id
            )
            falha_limpeza_fisica = True
        else:
            try:
                pendencia.delete()
            except Exception:
                # A pendência órfã é segura e pode ser removida posteriormente.
                logger.warning(
                    'Falha ao remover pendência de limpeza; arquivo_id=%s',
                    arquivo_id,
                )

    messages.success(request, f'Arquivo "{nome}" excluído com sucesso.')
    if falha_limpeza_fisica:
        messages.warning(
            request,
            'O arquivo físico não pôde ser removido do armazenamento. '
            'Avise o suporte para concluir a limpeza.'
        )
    return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)


@login_required
@require_POST
def criar_job_ocr(request, tis_id, imovel_id, documento_id, arquivo_id):
    """Cria e enfileira um job de OCR para o arquivo digital (JSON).

    Mesma política do upload: login + hierarquia TI→Imóvel→Documento. Só PDF;
    job ativo (pendente/em_execucao) existente → 409 em vez de um segundo job.
    """
    tis, imovel, documento = _get_contexto_documento(request, tis_id, imovel_id, documento_id)
    arquivo = get_object_or_404(DocumentoDigital, id=arquivo_id, documento=documento)

    if not arquivo.is_pdf:
        return JsonResponse(
            {'error': 'OCR disponível apenas para arquivos PDF.'},
            status=400,
        )

    # A guarda e a criação são serializadas pelo mesmo lock de
    # services.reprocessar: duas requisições concorrentes não criam dois jobs.
    with transaction.atomic():
        DocumentoDigital.objects.select_for_update().get(pk=arquivo.pk)
        job_ativo = (
            OcrJob.objects
            .filter(documento_digital=arquivo, status__in=[PENDENTE, EM_EXECUCAO])
            .first()
        )
        if job_ativo is not None:
            return JsonResponse(
                {
                    'error': 'Já existe um job de OCR ativo para este arquivo.',
                    'job_id': str(job_ativo.job_id),
                    'status': job_ativo.status,
                },
                status=409,
            )
        job, _criado = criar_job(arquivo, criado_por=request.user)

    return JsonResponse(
        {
            'job_id': str(job.job_id),
            'status': job.status,
            'tentativa': job.tentativa,
        },
        status=201,
    )


@login_required
@require_GET
def status_job_ocr(request, tis_id, imovel_id, documento_id, arquivo_id, job_id):
    """Estado atual do job de OCR (JSON): progresso e motivo de falha."""
    tis, imovel, documento = _get_contexto_documento(request, tis_id, imovel_id, documento_id)
    arquivo = get_object_or_404(DocumentoDigital, id=arquivo_id, documento=documento)
    job = get_object_or_404(OcrJob, job_id=job_id, documento_digital=arquivo)

    payload = {
        'job_id': str(job.job_id),
        'status': job.status,
        'status_display': job.get_status_display(),
        'tentativa': job.tentativa,
        'criado_em': job.criado_em.isoformat(),
        'atualizado_em': job.atualizado_em.isoformat(),
        'progresso': None,
        'erro': None,
    }
    if job.page_count is not None:
        processadas = job.paginas.count()
        payload['progresso'] = {
            'pagina': processadas,
            'total': job.page_count,
            'texto': f'página {processadas} de {job.page_count}',
        }
    if job.status == FALHOU:
        payload['erro'] = {
            'codigo': job.erro_codigo,
            'mensagem': job.erro_mensagem,
        }
    return JsonResponse(payload)
