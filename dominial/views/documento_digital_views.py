import hashlib
import json
import logging
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import DatabaseError, transaction
from django.db.models import ProtectedError
from django.http import HttpResponse, Http404, JsonResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils.http import content_disposition_header

from ..models import DocumentoDigital, Documento, Imovel, TIs
from ia_ocr.estados import (
    EM_EXECUCAO,
    FALHOU,
    PENDENTE,
    STATUS_ATIVOS,
    STATUS_COM_TEXTO,
    STATUS_REVISAVEIS,
)
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
        registro = DocumentoDigital.objects.create(
            documento=documento,
            arquivo=arquivo,
            nome_original=arquivo.name,
            tipo_mime=tipo_mime,
            tamanho_bytes=arquivo.size,
            upload_por=request.user,
        )

        messages.success(request, f'Arquivo "{arquivo.name}" anexado com sucesso.')
        if registro.is_pdf:
            # Fluxo tela 1 do protótipo (#260): PDF volta para o próprio
            # upload, onde fica o card "Extrair texto com IA". Imagens seguem
            # para o detalhado, que não tem o card.
            return redirect('upload_documento_digital', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)
        return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)

    # GET: renderiza formulário simples
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        # Card de OCR (I-3): só PDFs oferecem extração de texto.
        'arquivos_pdf': documento.arquivos_digitais.filter(tipo_mime='application/pdf'),
        # Fonte única dos estados do card (review #260-F): o template consulta
        # as listas e as expõe ao JS via data-* em JSON no container do card.
        'status_ativos': STATUS_ATIVOS,
        'status_com_texto': STATUS_COM_TEXTO,
        'status_revisaveis': STATUS_REVISAVEIS,
        'status_ativos_json': json.dumps(STATUS_ATIVOS),
        'status_com_texto_json': json.dumps(STATUS_COM_TEXTO),
        'status_revisaveis_json': json.dumps(STATUS_REVISAVEIS),
    }
    return render(request, 'dominial/upload_documento_digital.html', context)


@login_required
# A tela de confirmação do texto OCR (I-4, #261) exibe o PDF num iframe da
# própria origem; o padrão do Django (DENY) o bloquearia. SAMEORIGIN só libera
# páginas do mesmo site — outras origens continuam sem poder embutir o arquivo.
@xframe_options_sameorigin
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


def _hash_json(valor):
    """Hash estável de um JSONField (ordem das chaves não importa)."""
    return hashlib.sha256(
        json.dumps(valor, sort_keys=True, default=str).encode('utf-8')
    ).hexdigest()


def _estado_paginas(paginas):
    """Estado exato de cada página, não só a contagem.

    `versao`, `confirmado_em` e o texto vigente mudam quando outra pessoa
    edita e reconfirma uma página já confirmada — sem alterar o job.
    """
    return [
        (
            pagina.numero_pagina,
            pagina.versao,
            pagina.confirmado_em.isoformat() if pagina.confirmado_em else None,
            hashlib.sha256(
                (
                    pagina.texto_confirmado
                    or pagina.texto_corrigido
                    or pagina.texto_ocr
                    or ''
                ).encode('utf-8')
            ).hexdigest(),
        )
        for pagina in paginas
    ]


def _estado_extracoes(extracoes):
    """Conteúdo das extrações, não só a contagem.

    `ExtracaoSugerida` não tem `atualizado_em`: o id + hash dos campos
    sugeridos detecta uma extração alterada no lugar.
    """
    return [
        (
            extracao.id,
            _hash_json(
                {
                    'schema_version': extracao.schema_version,
                    'payload': extracao.payload,
                    'payload_servico': extracao.payload_servico,
                    'provider': extracao.provider,
                    'finalizada_em': (
                        extracao.finalizada_em.isoformat()
                        if extracao.finalizada_em
                        else None
                    ),
                    'finalizada_por_id': extracao.finalizada_por_id,
                }
            ),
        )
        for extracao in extracoes
    ]


def _resumo_jobs(jobs):
    """Contagens exibidas na confirmação e estado usado na assinatura.

    Aceita lista ou queryset: a confirmação usa queryset e a exclusão usa a
    lista já travada por `select_for_update`.
    """
    resumo = []
    for job in sorted(jobs, key=lambda job: job.id):
        paginas = list(job.paginas.order_by('numero_pagina'))
        extracoes = list(job.extracoes.order_by('id'))
        resumo.append({
            'job': job,
            'paginas': len(paginas),
            'confirmadas': sum(
                1 for pagina in paginas if pagina.confirmado_em is not None
            ),
            'extracoes': len(extracoes),
            'estado_paginas': _estado_paginas(paginas),
            'estado_extracoes': _estado_extracoes(extracoes),
        })
    return resumo


def _assinatura_jobs(resumo):
    """Impressão digital do estado do OCR no momento do render.

    Cobre o que a exclusão destrói (jobs, páginas, confirmações e extrações) e
    o `atualizado_em` do job (transições/reprocessamento). Ordenada por id para
    não depender da ordem do queryset. Páginas e extrações entram pelo estado
    exato, não só pela contagem: edição/reconfirmação de página ou alteração de
    extração invalida a assinatura mesmo sem mudar as contagens.
    """
    partes = [
        (
            item['job'].id,
            item['paginas'],
            item['confirmadas'],
            item['extracoes'],
            item['job'].atualizado_em.isoformat(),
            item['estado_paginas'],
            item['estado_extracoes'],
        )
        for item in resumo
    ]
    return hashlib.sha256(repr(partes).encode('utf-8')).hexdigest()


def _contexto_confirmacao(tis, imovel, documento, arquivo, resumo):
    return {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'arquivo': arquivo,
        'jobs': resumo,
        'assinatura': _assinatura_jobs(resumo),
        'total_confirmadas': sum(item['confirmadas'] for item in resumo),
    }


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
            # Mesma trava do reprocessar: confirmação e mutação do OCR não
            # podem se entrecortar. A assinatura é recalculada sob a trava.
            arquivo = get_object_or_404(
                DocumentoDigital.objects.select_for_update(),
                id=arquivo_id, documento=documento,
            )
            caminho = arquivo.arquivo.name if arquivo.arquivo else None

            # A decisão de pedir confirmação também acontece sob a trava:
            # um job criado entre a checagem e a exclusão não pode escapar.
            jobs_atuais = OcrJob.objects.filter(documento_digital=arquivo)
            if (
                jobs_atuais.exists()
                and request.POST.get('confirmar_ocr') != '1'
            ):
                return render(
                    request,
                    'dominial/confirmar_exclusao_ocr.html',
                    _contexto_confirmacao(
                        tis, imovel, documento, arquivo,
                        _resumo_jobs(jobs_atuais),
                    ),
                )

            # Jobs travados na mesma ordem do DocumentoDigital: páginas e
            # confirmações não podem mudar entre a assinatura e o delete.
            jobs = list(
                OcrJob.objects.select_for_update()
                .filter(documento_digital=arquivo)
                .order_by('id')
            )

            if request.POST.get('confirmar_ocr') == '1':
                resumo = _resumo_jobs(jobs)
                if request.POST.get('assinatura') != _assinatura_jobs(resumo):
                    # Cliente antigo (sem assinatura) também cai aqui: sem
                    # prova de que viu o estado atual, nada é apagado.
                    return render(
                        request,
                        'dominial/confirmar_exclusao_ocr.html',
                        _contexto_confirmacao(
                            tis, imovel, documento, arquivo, resumo,
                        ) | {'aviso_divergencia': True},
                        status=409,
                    )

            logger.info(
                'Excluindo arquivo digital; arquivo_id=%s user_id=%s jobs=%s',
                arquivo_id,
                request.user.id,
                len(jobs),
            )
            OcrJob.objects.filter(id__in=[job.id for job in jobs]).delete()
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
            'O processamento de OCR mudou enquanto você confirmava. '
            'Tente novamente.'
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

    # A guarda e a criação são serializadas pelo mesmo lock de
    # services.reprocessar: duas requisições concorrentes não criam dois jobs.
    # A leitura com lock acontece dentro do atomic: se o arquivo for excluído
    # no meio do caminho, a ausência vira 404 (e não DoesNotExist → 500).
    with transaction.atomic():
        arquivo = get_object_or_404(
            DocumentoDigital.objects.select_for_update(),
            id=arquivo_id, documento=documento,
        )

        if not arquivo.is_pdf:
            return JsonResponse(
                {'error': 'OCR disponível apenas para arquivos PDF.'},
                status=400,
            )

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
