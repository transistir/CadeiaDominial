"""Download em lote dos PDFs da cadeia dominial (#334).

Gera um ZIP com todos os PDFs anexados aos documentos da cadeia, na ordem
da tela. View nova em módulo próprio porque o legado
``documento_digital_views.py`` está congelado no baseline de 400 linhas.
"""

import logging
import os
import shutil
import tempfile
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, prefetch_related_objects
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.utils.text import slugify

from ..models import DocumentoDigital, Imovel
from ..services.cadeia_completa_service import CadeiaCompletaService
from ..utils.segregacao_utils import require_imovel_atribuido

logger = logging.getLogger(__name__)

TIPO_MIME_PDF = 'application/pdf'
MENSAGEM_SEM_PDF = 'Nenhum PDF anexado aos documentos desta cadeia.'
MAX_SPOOL = 10 * 1024 * 1024  # 10 MB em memória antes de virar arquivo temporário


def _documentos_da_cadeia(cadeia_completa):
    """Documentos dos troncos, na ordem da tela, deduplicados por id.

    O mesmo documento pode reaparecer em mais de um tronco; só a primeira
    aparição vale. Documentos importados já vêm no tronco com o `Documento`
    do imóvel de origem — que é onde o PDF dele vive (#297).
    """
    vistos = set()
    documentos = []
    for tronco in cadeia_completa:
        for item in tronco['documentos']:
            documento = item['documento']
            if documento.id in vistos:
                continue
            vistos.add(documento.id)
            documentos.append(documento)
    return documentos


def _com_pdfs(documentos):
    """Pares (documento, PDFs do documento) com prefetch filtrado — sem N+1.

    Devolve TODOS os documentos da cadeia (mesmo sem PDF) para o NN do nome
    interno ser a posição na cadeia, e não a ordem dos itens com arquivo. O
    `Prefetch` já vem filtrado por `tipo_mime='application/pdf'`, então
    imagens nem chegam ao ZIP e cada documento vira uma única consulta de
    arquivos, executada em lote pelo prefetch.
    """
    if not documentos:
        return []
    prefetch_related_objects(
        documentos,
        Prefetch(
            'arquivos_digitais',
            queryset=DocumentoDigital.objects.filter(tipo_mime=TIPO_MIME_PDF),
            to_attr='_pdfs_certidoes',
        ),
    )
    return [
        (documento, documento._pdfs_certidoes)
        for documento in documentos
    ]


def _nome_interno(posicao, documento, arquivo, usados):
    """`NN_<tipo>_<numero>_<nome_original>`; colisão ganha sufixo _2, _3.

    NN é a posição do documento na cadeia (não a ordem dos arquivos
    coletados), com zero à esquerda. Separadores de caminho no nome
    original viram `_` para não criar subpastas dentro do ZIP.
    """
    tipo = slugify(documento.tipo.get_tipo_display()).title() or 'Documento'
    nome_original = (
        (arquivo.nome_original or '').replace('/', '_').replace('\\', '_')
    )
    base = f'{posicao:02d}_{tipo}_{documento.numero}_{nome_original}'
    raiz, extensao = os.path.splitext(base)
    nome = base
    contador = 2
    while nome in usados:
        nome = f'{raiz}_{contador}{extensao}'
        contador += 1
    usados.add(nome)
    return nome


@login_required
@require_imovel_atribuido
def baixar_certidoes_cadeia(request, tis_id, imovel_id):
    """ZIP com todos os PDFs anexados aos documentos da cadeia (#334).

    Mesma fonte e escopo do Excel (`CadeiaCompletaService` + #132): tronco
    principal na ordem da tela, com os importados. Sem nenhum PDF, não gera
    ZIP vazio — volta para a cadeia com mensagem. Arquivo ausente no
    storage é pulado com log; o download dos demais não cai.
    """
    imovel = get_object_or_404(
        Imovel.objects.for_user(request.user),
        id=imovel_id,
        terra_indigena_id_id=tis_id,
    )

    contexto = CadeiaCompletaService(user=request.user).get_cadeia_completa(
        tis_id, imovel_id
    )
    pares = _com_pdfs(_documentos_da_cadeia(contexto['cadeia_completa']))

    if not any(arquivos for _, arquivos in pares):
        messages.warning(request, MENSAGEM_SEM_PDF)
        return redirect('tronco_principal', tis_id=tis_id, imovel_id=imovel_id)

    # PDFs já são comprimidos: ZIP_STORED evita gastar CPU sem ganho. O
    # spool gruda em disco acima de 10 MB e o FileResponse fecha o arquivo
    # ao terminar de streamar. Não pode entrar num `with`: a resposta ainda
    # precisa dele aberto depois daqui.
    spool = tempfile.SpooledTemporaryFile(max_size=MAX_SPOOL)  # noqa: SIM115
    usados = set()
    with zipfile.ZipFile(spool, 'w', zipfile.ZIP_STORED) as zipf:
        for posicao, (documento, arquivos) in enumerate(pares, start=1):
            if not arquivos:
                continue
            for arquivo in arquivos:
                nome = _nome_interno(posicao, documento, arquivo, usados)
                try:
                    with (
                        arquivo.arquivo.open('rb') as fisico,
                        zipf.open(nome, 'w') as destino,
                    ):
                        shutil.copyfileobj(fisico, destino)
                except OSError:
                    logger.warning(
                        'Arquivo ausente no storage; pulado do ZIP; '
                        'arquivo_id=%s documento_id=%s',
                        arquivo.id,
                        documento.id,
                    )
    spool.seek(0)

    nome_zip = (
        f"certidoes_{slugify(imovel.matricula) or imovel.id}_"
        f"{timezone.localdate().strftime('%Y%m%d')}.zip"
    )
    response = FileResponse(spool, content_type='application/zip')
    response['Content-Disposition'] = content_disposition_header(
        as_attachment=True, filename=nome_zip
    )
    return response
