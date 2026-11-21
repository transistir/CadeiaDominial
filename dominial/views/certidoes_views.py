"""Download em lote dos PDFs da cadeia dominial (#334).

O ZIP baixa a cadeia INTEIRA — a MESMA lista que o XLSX renderiza, na
mesma ordem. A fonte é ``CadeiaCompletaService.get_cadeia_completa``, a
mesma de ``exportar_cadeia_dominial_excel``: a escolha de origem da tela
não filtra o ZIP (decisão do dono, 21/11/2026). Todo documento da cadeia
aparece na posição dele — com os PDFs disponíveis, com um marcador
``_INDISPONIVEL.txt`` quando o registro existe mas o arquivo sumiu do
storage, ou com um marcador ``_SEM_PDF.txt`` quando não há registro de
PDF nenhum. View nova em módulo próprio porque o legado
``documento_digital_views.py`` está congelado no baseline de 400 linhas.
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
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.utils.text import slugify

from ..models import DocumentoDigital
from ..services.cadeia_completa_service import CadeiaCompletaService
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


def _documentos_da_cadeia(context):
    """Documentos do `cadeia_completa`, na MESMA lista/ordem do XLSX.

    `context` é o retorno de ``CadeiaCompletaService.get_cadeia_completa``
    — o mesmo objeto que ``exportar_cadeia_dominial_excel`` renderiza. O
    mesmo documento não deve reaparecer entre troncos; se reaparecer, só a
    primeira aparição vale. Documentos importados vêm com o `Documento` do
    imóvel de origem — que é onde o PDF dele vive (#297).
    """
    vistos = set()
    documentos = []
    for tronco in context['cadeia_completa']:
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


def _coletar_pares(request, tis_id, imovel_id):
    """Contexto do `CadeiaCompletaService` + os pares (documento, PDFs).

    A mesma fonte do XLSX, para o ZIP e para a verificação do modal —
    mesma autenticação, mesmo escopo (#132), mesma ordem.
    """
    context = CadeiaCompletaService(
        user=request.user
    ).get_cadeia_completa(tis_id, imovel_id)
    return context, _com_pdfs(_documentos_da_cadeia(context))


def _arquivo_disponivel(arquivo):
    """O registro de PDF tem arquivo físico no storage? (`storage.exists`)"""
    return arquivo.arquivo.storage.exists(arquivo.arquivo.name)


def _raiz_de_nome(posicao, documento, cauda):
    """`NN_<tipo>_<numero>` + `_cauda`, tudo sanitizado (sem separadores).

    NN é a posição do documento na cadeia (não a ordem dos arquivos
    coletados), com zero à esquerda. Número e cauda passam por
    `_sanitizar_para_zip` antes de virar nome, para não criarem subpastas
    dentro do ZIP.
    """
    tipo = slugify(documento.tipo.get_tipo_display()).title() or 'Documento'
    numero = _sanitizar_para_zip(documento.numero) or 'Documento'
    base = f'{posicao:02d}_{tipo}_{numero}'
    cauda = _sanitizar_para_zip(cauda)
    if cauda:
        base = f'{base}_{cauda}'
    return base


def _nome_interno(posicao, documento, arquivo, usados):
    """`NN_<tipo>_<numero>_<nome_original>`; colisão ganha sufixo _2, _3."""
    base = _raiz_de_nome(posicao, documento, arquivo.nome_original)
    raiz, extensao = os.path.splitext(base)
    nome = base
    contador = 2
    while nome in usados:
        nome = f'{raiz}_{contador}{extensao}'
        contador += 1
    usados.add(nome)
    return nome


def _nome_marcador(posicao, documento, cauda, estado, usados):
    """`NN_<tipo>_<numero>_<cauda>_<estado>.txt`; colisão vira _2, _3.

    `estado` é ``INDISPONIVEL`` (o registro existe, o arquivo sumiu do
    storage) ou ``SEM_PDF`` (documento sem registro de PDF nenhum).
    Compartilha o `usados` dos nomes reais: marcador nunca sobrescreve um
    PDF de mesmo nome, nem vice-versa.
    """
    raiz = f'{_raiz_de_nome(posicao, documento, cauda)}_{estado}'
    nome = f'{raiz}.txt'
    contador = 2
    while nome in usados:
        nome = f'{raiz}_{contador}.txt'
        contador += 1
    usados.add(nome)
    return nome


def _texto_marcador(documento, arquivo=None):
    """Explica o caso: documento, tipo, número, data e arquivo esperado."""
    data = documento.data_exibicao
    linhas = [
        'Este arquivo é um marcador de posição — não é o documento em si.',
        '',
        f'Documento: {documento.tipo.get_tipo_display()} {documento.numero}',
        f'Data: {data.strftime("%d/%m/%Y") if data else "não informada"}',
    ]
    if arquivo is not None:
        linhas += [
            f'Arquivo esperado: {arquivo.nome_original}',
            (
                'Motivo: o registro do PDF existe, mas o arquivo não foi '
                'encontrado no armazenamento.'
            ),
        ]
    else:
        linhas.append('Motivo: nenhum PDF foi anexado a este documento.')
    return '\n'.join(linhas) + '\n'


@login_required
@require_imovel_atribuido
def baixar_certidoes_cadeia(request, tis_id, imovel_id):
    """ZIP com a cadeia inteira, idêntica à lista do XLSX (#334).

    Baixa a cadeia inteira, idêntica à lista do XLSX; a escolha de origem
    da tela não filtra (decisão do dono, 21/11/2026). Todo documento entra
    na posição dele: os PDFs disponíveis, `_INDISPONIVEL.txt` quando o
    registro existe mas o arquivo sumiu do storage e `_SEM_PDF.txt` quando
    não há registro de PDF. Só cadeia sem documento nenhum volta com
    MENSAGEM_SEM_PDF — com marcadores, sempre há o que entregar. Falha na
    cópia ou na resposta fecha o spool e devolve erro — nunca um ZIP
    parcial com 200.
    """
    context, pares = _coletar_pares(request, tis_id, imovel_id)
    if not pares:
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
        with zipfile.ZipFile(spool, 'w', zipfile.ZIP_STORED) as zipf:
            for posicao, (documento, arquivos) in enumerate(pares, start=1):
                if not arquivos:
                    zipf.writestr(
                        _nome_marcador(
                            posicao, documento, '', 'SEM_PDF', usados
                        ),
                        _texto_marcador(documento),
                    )
                    continue
                for arquivo in arquivos:
                    if not _arquivo_disponivel(arquivo):
                        logger.warning(
                            'Arquivo ausente no storage; vira marcador; '
                            'arquivo_id=%s documento_id=%s',
                            arquivo.id,
                            documento.id,
                        )
                        zipf.writestr(
                            _nome_marcador(
                                posicao,
                                documento,
                                arquivo.nome_original,
                                'INDISPONIVEL',
                                usados,
                            ),
                            _texto_marcador(documento, arquivo),
                        )
                        continue
                    # OSError só aqui: `exists` pode mentir num storage
                    # lento; abrir pode falhar. O registro é pulado com
                    # warning e o download dos demais não cai.
                    try:
                        fisico = arquivo.arquivo.open('rb')
                    except OSError:
                        logger.warning(
                            'Arquivo não pôde ser aberto; pulado do ZIP; '
                            'arquivo_id=%s documento_id=%s',
                            arquivo.id,
                            documento.id,
                        )
                        continue
                    try:
                        nome = _nome_interno(
                            posicao, documento, arquivo, usados
                        )
                        with zipf.open(nome, 'w') as destino:
                            shutil.copyfileobj(fisico, destino)
                    finally:
                        fisico.close()
        spool.seek(0)

        imovel = context['imovel']
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


@login_required
@require_imovel_atribuido
def baixar_certidoes_cadeia_verificar(request, tis_id, imovel_id):
    """Resumo do que o ZIP vai trazer — alimenta o modal de aviso (#334).

    Mesmo escopo e mesma fonte do ZIP: cadeia inteira, idêntica à lista do
    XLSX; a escolha de origem da tela não filtra (dono, 21/11/2026).
    Devolve `total` (documentos da cadeia), `com_pdf` (com ao menos um PDF
    disponível), `sem_pdf` (sem registro de PDF) e `indisponiveis` (os
    registros cujo arquivo sumiu do storage, com posição e detalhes).
    """
    _, pares = _coletar_pares(request, tis_id, imovel_id)
    com_pdf = 0
    sem_pdf = 0
    indisponiveis = []
    for ordem, (documento, arquivos) in enumerate(pares, start=1):
        if not arquivos:
            sem_pdf += 1
            continue
        tem_disponivel = False
        for arquivo in arquivos:
            if _arquivo_disponivel(arquivo):
                tem_disponivel = True
            else:
                indisponiveis.append({
                    'ordem': ordem,
                    'tipo': documento.tipo.get_tipo_display(),
                    'numero': documento.numero,
                    'nome_original': arquivo.nome_original,
                })
        if tem_disponivel:
            com_pdf += 1
    return JsonResponse({
        'total': len(pares),
        'com_pdf': com_pdf,
        'sem_pdf': sem_pdf,
        'indisponiveis': indisponiveis,
    })
