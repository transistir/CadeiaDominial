"""Download em lote dos PDFs da cadeia dominial (#334).

Gera um ZIP com os PDFs anexados aos documentos da cadeia, na ordem da
tela. A fonte é a mesma da tela (`CadeiaDominialTabelaService` + as
escolhas de origem da sessão, com o ``?escolhas`` da URL valendo mais que
a sessão — igual à tela): o ZIP segue o galho escolhido. View nova em
módulo próprio porque o legado ``documento_digital_views.py`` está
congelado no baseline de 400 linhas.
"""

import logging
import os
import re
import shutil
import tempfile
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, prefetch_related_objects
from django.http import FileResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.utils.text import slugify

from ..models import DocumentoDigital
from ..services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
from ..utils.escolhas_origem_utils import escolhas_da_url
from ..utils.segregacao_utils import require_imovel_atribuido

logger = logging.getLogger(__name__)

TIPO_MIME_PDF = 'application/pdf'
MENSAGEM_SEM_PDF = 'Nenhum PDF anexado aos documentos desta cadeia.'
MENSAGEM_ERRO_GERACAO = 'Erro ao gerar o ZIP das certidões. Tente novamente.'
MAX_SPOOL = 10 * 1024 * 1024  # 10 MB em memória antes de virar arquivo temporário
_PONTOS_SEGUIDOS = re.compile(r'\.{2,}')


def _sanitizar_para_zip(texto):
    """Texto seguro como parte de nome de arquivo dentro do ZIP.

    Separadores de caminho (``/``, ``\\``) e caracteres de controle viram
    `_`, corridas de pontos (`..`) viram `_` e pontas não sobrecarregam `.`
    nem espaço. Assim o número `M123/45` não cria subpasta e `../evil` não
    sobe de nível dentro do ZIP.
    """
    texto = (texto or '').replace('/', '_').replace('\\', '_')
    texto = ''.join(
        '_' if ord(caractere) < 32 or ord(caractere) == 127 else caractere
        for caractere in texto
    )
    texto = _PONTOS_SEGUIDOS.sub('_', texto)
    return texto.strip(' .')


def _documentos_da_cadeia(cadeia):
    """Documentos das linhas da tabela, na ordem da tela, deduplicados por id.

    `cadeia` é a lista devolvida por ``CadeiaDominialTabelaService.
    get_cadeia_dominial_tabela`` — a mesma lista, na mesma ordem, que a
    tela renderiza, já seguindo as escolhas de origem da sessão. O mesmo
    documento não deve reaparecer; se reaparecer, só a primeira aparição
    vale. Documentos importados vêm na linha com o `Documento` do imóvel de
    origem — que é onde o PDF dele vive (#297).
    """
    vistos = set()
    documentos = []
    for item in cadeia:
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
    coletados), com zero à esquerda. Número e nome originais passam por
    `_sanitizar_para_zip` antes da resolução de colisão, para não criarem
    subpastas dentro do ZIP.
    """
    tipo = slugify(documento.tipo.get_tipo_display()).title() or 'Documento'
    numero = _sanitizar_para_zip(documento.numero) or 'Documento'
    nome_original = _sanitizar_para_zip(arquivo.nome_original)
    base = f'{posicao:02d}_{tipo}_{numero}_{nome_original}'
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
    """ZIP com os PDFs da cadeia, espelho da tela (#334).

    Mesma fonte da tela (`CadeiaDominialTabelaService` + a sessão de
    escolhas de origem): o ZIP segue o galho escolhido nos botões de origem,
    na ordem das linhas. O ``?escolhas`` da URL vale mais que a sessão,
    com a mesma semântica e precedência da tela (`escolhas_da_url` — param
    > sessão, inclusive vazio). Sem nenhum PDF incluído, não gera ZIP vazio
    — volta para a cadeia com mensagem. Arquivo ausente no storage é pulado
    com log e o download dos demais não cai; falha na cópia ou na resposta
    fecha o spool e devolve erro — nunca um ZIP parcial com 200.
    """
    resultado = CadeiaDominialTabelaService(
        user=request.user
    ).get_cadeia_dominial_tabela(
        tis_id,
        imovel_id,
        request.session,
        escolhas_da_url(request.GET.get('escolhas')),
    )
    imovel = resultado['imovel']
    pares = _com_pdfs(_documentos_da_cadeia(resultado['cadeia']))

    if not any(arquivos for _, arquivos in pares):
        messages.warning(request, MENSAGEM_SEM_PDF)
        return redirect('tronco_principal', tis_id=tis_id, imovel_id=imovel_id)

    # PDFs já são comprimidos: ZIP_STORED evita gastar CPU sem ganho. O
    # spool gruda em disco acima de 10 MB e o FileResponse fecha o arquivo
    # ao terminar de streamar. Não pode entrar num `with`: a resposta ainda
    # precisa dele aberto depois daqui — e em qualquer caminho de exceção
    # abaixo ele é fechado à mão, para não vazar.
    spool = tempfile.SpooledTemporaryFile(max_size=MAX_SPOOL)  # noqa: SIM115
    try:
        usados = set()
        incluidos = 0
        with zipfile.ZipFile(spool, 'w', zipfile.ZIP_STORED) as zipf:
            for posicao, (documento, arquivos) in enumerate(pares, start=1):
                if not arquivos:
                    continue
                for arquivo in arquivos:
                    nome = _nome_interno(posicao, documento, arquivo, usados)
                    # OSError só aqui: ausente no storage pula com warning.
                    try:
                        fisico = arquivo.arquivo.open('rb')
                    except OSError:
                        logger.warning(
                            'Arquivo ausente no storage; pulado do ZIP; '
                            'arquivo_id=%s documento_id=%s',
                            arquivo.id,
                            documento.id,
                        )
                        continue
                    try:
                        with zipf.open(nome, 'w') as destino:
                            shutil.copyfileobj(fisico, destino)
                    finally:
                        fisico.close()
                    incluidos += 1
        if not incluidos:
            spool.close()
            messages.warning(request, MENSAGEM_SEM_PDF)
            return redirect(
                'tronco_principal', tis_id=tis_id, imovel_id=imovel_id
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
    except Exception:
        # Falha na cópia (leitura/escrita) ou na construção da resposta não
        # pode ser apresentada como sucesso: fecha o spool, loga e devolve
        # erro — sem JSON/ZIP parcial.
        spool.close()
        logger.exception(
            'Falha ao gerar o ZIP das certidões; imovel_id=%s', imovel_id
        )
        messages.error(request, MENSAGEM_ERRO_GERACAO)
        return redirect('tronco_principal', tis_id=tis_id, imovel_id=imovel_id)
