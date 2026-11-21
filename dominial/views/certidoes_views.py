"""Download em lote dos PDFs da cadeia dominial (#334).

O ZIP baixa a cadeia INTEIRA — a MESMA lista que o XLSX renderiza, na
mesma ordem. A fonte é ``CadeiaCompletaService.get_cadeia_completa``, a
mesma de ``exportar_cadeia_dominial_excel``: a escolha de origem da tela
não filtra o ZIP (decisão do dono, 21/11/2026). Todo documento da cadeia
aparece na posição dele — com os PDFs disponíveis, com um marcador
``_INDISPONIVEL.txt`` quando o registro existe mas o arquivo sumiu do
storage, ou com um marcador ``_SEM_PDF.txt`` quando não há registro de
PDF nenhum. Os arquivos se chamam ``<numero>_<cartório>.<ext>`` — sem NN
e sem o tipo do documento (dono, 21/11/2026); marcadores usam a mesma
raiz. View nova em módulo próprio porque o legado
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

from ..models import Cartorios, DocumentoDigital
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

    Devolve TODOS os documentos da cadeia, mesmo os sem PDF: cada um ganha
    entrada no ZIP — arquivo ou marcador. O `Prefetch` já vem filtrado por
    `tipo_mime='application/pdf'`, então imagens nem chegam ao ZIP e cada
    documento vira uma única consulta de arquivos, executada em lote pelo
    prefetch.
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


_ORDINAL_NO_NOME = re.compile(r'^\s*(\d+)\s*[º°ªoaOA]?\b')


class _SiglasCartorio:
    """Parte do cartório no nome do arquivo: `CRI-Cuiaba-MT` (dono 21/11).

    Um só cartório do tipo na cidade/UF → `CRI`; dois ou mais → ordinal do
    `nome` (`1º` → `CRI1`); nome sem ordinal → cns no fim
    (`CRI-Cuiaba-MT-334334`). Cidade/UF nulos são omitidos — nunca `--`.
    O cache por `(tipo, cidade, estado)` faz a pergunta "há concorrente?"
    custar uma consulta por combinação, não uma por documento.
    """

    def __init__(self):
        self._concorrentes = {}

    def _tem_concorrente(self, cartorio):
        chave = (cartorio.tipo, cartorio.cidade, cartorio.estado)
        if chave not in self._concorrentes:
            self._concorrentes[chave] = (
                Cartorios.objects.filter(
                    tipo=cartorio.tipo,
                    cidade=cartorio.cidade,
                    estado=cartorio.estado,
                ).count() > 1
            )
        return self._concorrentes[chave]

    def parte_de(self, documento):
        """Sigla sanitizada: `CRI-Cuiaba-MT`, `CRI2-Cuiaba-MT` ou
        `SEM_CARTORIO` (documento sem cartório ou sem segmento utilizável).
        """
        cartorio = documento.cartorio
        if cartorio is None:
            return 'SEM_CARTORIO'
        segmentos = [
            texto for texto in (
                _sanitizar_para_zip(cartorio.tipo),
                _sanitizar_para_zip(cartorio.cidade),
                _sanitizar_para_zip(cartorio.estado),
            )
            if texto
        ]
        if not segmentos:
            return 'SEM_CARTORIO'
        if self._tem_concorrente(cartorio):
            ordinal = _ORDINAL_NO_NOME.match(cartorio.nome or '')
            if ordinal:
                segmentos[0] = f'{segmentos[0]}{ordinal.group(1)}'
            else:
                cns = _sanitizar_para_zip(cartorio.cns)
                if cns:
                    segmentos.append(cns)
        return '-'.join(segmentos)


def _raiz_de_nome(documento, siglas):
    """`<numero>_<CRI-Cidade-UF>`, tudo sanitizado (dono 21/11/2026).

    Sem NN e sem o tipo do documento: número + cartório abreviado
    (`_SiglasCartorio`) identificam o arquivo. O número passa por
    `_sanitizar_para_zip` antes de virar nome, para não criar subpastas
    dentro do ZIP.
    """
    numero = _sanitizar_para_zip(documento.numero) or 'Documento'
    return f'{numero}_{siglas.parte_de(documento)}'


def _extensao_do_original(nome_original):
    """Extensão do arquivo original, sanitizada e com ponto ('' se não há)."""
    bruta = os.path.splitext(nome_original or '')[1]
    texto = _sanitizar_para_zip(bruta[1:])
    return f'.{texto}' if texto else ''


def _nome_interno(documento, arquivo, siglas, usados):
    """`<numero>_<cartório>.<ext original>`; colisão ganha sufixo _2, _3."""
    raiz = _raiz_de_nome(documento, siglas)
    extensao = _extensao_do_original(arquivo.nome_original)
    nome = f'{raiz}{extensao}'
    contador = 2
    while nome in usados:
        nome = f'{raiz}_{contador}{extensao}'
        contador += 1
    usados.add(nome)
    return nome


def _nome_marcador(documento, estado, siglas, usados):
    """`<numero>_<cartório>_<estado>.txt`; colisão vira _2, _3.

    `estado` é ``INDISPONIVEL`` (o registro existe, o arquivo sumiu do
    storage) ou ``SEM_PDF`` (documento sem registro de PDF nenhum).
    Compartilha o `usados` dos nomes reais: marcador nunca sobrescreve um
    PDF de mesmo nome, nem vice-versa.
    """
    raiz = f'{_raiz_de_nome(documento, siglas)}_{estado}'
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
        siglas = _SiglasCartorio()
        with zipfile.ZipFile(spool, 'w', zipfile.ZIP_STORED) as zipf:
            for documento, arquivos in pares:
                if not arquivos:
                    zipf.writestr(
                        _nome_marcador(
                            documento, 'SEM_PDF', siglas, usados
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
                                documento, 'INDISPONIVEL', siglas, usados
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
                            documento, arquivo, siglas, usados
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
