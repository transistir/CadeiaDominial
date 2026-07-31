import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404
from django.views.decorators.http import require_POST, require_http_methods

from ..models import DocumentoDigital, Documento, Imovel, TIs


TIPOS_PERMITIDOS = {
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/webp',
}

TAMANHO_MAXIMO = 20 * 1024 * 1024  # 20MB


def _get_contexto_documento(tis_id, imovel_id, documento_id):
    """Helper: resolve TI, Imóvel e Documento com validação de hierarquia."""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documento = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    return tis, imovel, documento


@login_required
@require_http_methods(["GET", "POST"])
def upload_documento_digital(request, tis_id, imovel_id, documento_id):
    """Upload de arquivo digital vinculado a um documento."""
    tis, imovel, documento = _get_contexto_documento(tis_id, imovel_id, documento_id)

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
    }
    return render(request, 'dominial/upload_documento_digital.html', context)


@login_required
def servir_documento_digital(request, tis_id, imovel_id, documento_id, arquivo_id):
    """Serve o arquivo para download/visualização (NUNCA expõe URL pública)."""
    tis, imovel, documento = _get_contexto_documento(tis_id, imovel_id, documento_id)
    arquivo = get_object_or_404(DocumentoDigital, id=arquivo_id, documento=documento)

    try:
        response = FileResponse(
            arquivo.arquivo.open('rb'),
            content_type=arquivo.tipo_mime,
        )
        response['Content-Disposition'] = f'inline; filename="{arquivo.nome_original}"'
        return response
    except FileNotFoundError:
        raise Http404("Arquivo não encontrado no storage.")


@login_required
@require_POST
def excluir_documento_digital(request, tis_id, imovel_id, documento_id, arquivo_id):
    """Exclui um arquivo digital (POST apenas)."""
    tis, imovel, documento = _get_contexto_documento(tis_id, imovel_id, documento_id)
    arquivo = get_object_or_404(DocumentoDigital, id=arquivo_id, documento=documento)

    nome = arquivo.nome_original
    # Deletar o arquivo do storage antes de deletar o registro
    if arquivo.arquivo:
        arquivo.arquivo.delete(save=False)
    arquivo.delete()

    messages.success(request, f'Arquivo "{nome}" excluído com sucesso.')
    return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)
