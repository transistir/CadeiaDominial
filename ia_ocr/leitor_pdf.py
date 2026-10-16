"""Diagnóstico local de PDFs antes do envio ao serviço de OCR."""

from __future__ import annotations

import logging
import math
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import DependencyError

from ia_ocr.backends import OcrBackendError, OrcamentoEsgotado


MAX_PAGE_EDGE_POINTS = 3600
MAX_PAGE_AREA_POINTS = 10_000_000
MIN_CHARS_TEXTO_EMBUTIDO = 200

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
_JPEG_MAGIC = b'\xff\xd8\xff'
_RIFF_MAGIC = b'RIFF'


@dataclass(frozen=True)
class InspecaoPdf:
    page_count: int | None
    tamanho_bytes: int
    criptografado: bool
    texto_por_pagina: tuple[str | None, ...] | None


@contextmanager
def _silenciar_logger_pypdf():
    """Impede que mensagens do parser, que podem conter bytes, propaguem."""
    logger = logging.getLogger('pypdf')
    handler = logging.NullHandler(level=logging.WARNING)
    propagate_original = logger.propagate
    logger.addHandler(handler)
    logger.propagate = False
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.propagate = propagate_original


def _erro(codigo, mensagem):
    return OcrBackendError(codigo, mensagem)


def _inspecao_inconclusiva(tamanho_bytes):
    """PDF cifrado que o provider local não consegue abrir: o serviço decide."""
    return InspecaoPdf(
        page_count=None,
        tamanho_bytes=tamanho_bytes,
        criptografado=True,
        texto_por_pagina=None,
    )


def _conferir_prazo(prazo):
    if prazo is not None and time.monotonic() >= prazo:
        raise OrcamentoEsgotado('Prazo esgotado durante a inspeção do PDF.')


def _tipo_magic_bytes(cabecalho):
    if cabecalho.startswith(b'%PDF-'):
        return 'pdf'
    if cabecalho.startswith(_PNG_MAGIC):
        return 'png'
    if cabecalho.startswith(_JPEG_MAGIC):
        return 'jpeg'
    if cabecalho.startswith(_RIFF_MAGIC) and cabecalho[8:12] == b'WEBP':
        return 'webp'
    return 'unknown'


def inspecionar_pdf(
    caminho,
    *,
    prazo=None,
    max_bytes,
    max_paginas,
    ler_texto=False,
    min_chars_pagina=MIN_CHARS_TEXTO_EMBUTIDO,
):
    """Valida um PDF local e, opcionalmente, tenta ler sua camada de texto."""
    try:
        tamanho_bytes = os.path.getsize(caminho)
        if tamanho_bytes == 0:
            raise _erro('EMPTY_FILE', 'O arquivo enviado está vazio.')
        if tamanho_bytes > max_bytes:
            raise _erro(
                'FILE_TOO_LARGE',
                'O arquivo enviado excede o limite de tamanho configurado.',
            )

        with open(caminho, 'rb') as arquivo:
            cabecalho = arquivo.read(16)
        tipo = _tipo_magic_bytes(cabecalho)
        if tipo in {'png', 'jpeg', 'webp'}:
            raise _erro(
                'UNSUPPORTED_MEDIA_TYPE',
                'O tipo de arquivo enviado não é suportado.',
            )
        if tipo != 'pdf':
            raise _erro('INVALID_PDF', 'O arquivo enviado não é um PDF válido.')

        with _silenciar_logger_pypdf():
            reader = PdfReader(str(caminho), strict=False)
            criptografado = reader.is_encrypted
            if criptografado:
                try:
                    desbloqueado = bool(reader.decrypt(''))
                except Exception:
                    # Sem o backend criptográfico local não é possível decidir.
                    # O serviço pode conseguir abrir o documento; não o barre.
                    return _inspecao_inconclusiva(tamanho_bytes)
                if not desbloqueado:
                    raise _erro(
                        'ENCRYPTED_PDF',
                        'O PDF exige senha de usuário para ser aberto.',
                    )

            page_count = len(reader.pages)
            if page_count < 1:
                raise _erro('INVALID_PDF', 'O PDF não contém páginas.')
            if page_count > max_paginas:
                raise _erro(
                    'TOO_MANY_PAGES',
                    f'O PDF excede o limite de {max_paginas} páginas deste job.',
                )

            for indice, pagina in enumerate(reader.pages):
                if indice:
                    _conferir_prazo(prazo)
                numero_pagina = indice + 1
                try:
                    user_unit = float(getattr(pagina, 'user_unit', 1.0))
                    width = abs(float(pagina.mediabox.width)) * user_unit
                    height = abs(float(pagina.mediabox.height)) * user_unit
                except (TypeError, ValueError, OverflowError) as exc:
                    raise _erro(
                        'INVALID_PDF',
                        f'A página {numero_pagina} do PDF tem dimensões inválidas.',
                    ) from exc
                if (
                    not math.isfinite(user_unit)
                    or user_unit <= 0
                    or not math.isfinite(width)
                    or not math.isfinite(height)
                    or width <= 0
                    or height <= 0
                ):
                    raise _erro(
                        'INVALID_PDF',
                        f'A página {numero_pagina} do PDF tem dimensões inválidas.',
                    )
                if (
                    max(abs(width), abs(height)) > MAX_PAGE_EDGE_POINTS
                    or abs(width) * abs(height) > MAX_PAGE_AREA_POINTS
                ):
                    raise _erro(
                        'PDF_PAGE_TOO_LARGE',
                        f'A página {numero_pagina} excede o limite de dimensões.',
                    )

            textos = None
            if ler_texto:
                extraidos = []
                for indice, pagina in enumerate(reader.pages):
                    if indice:
                        _conferir_prazo(prazo)
                    try:
                        texto = pagina.extract_text()
                    except Exception:
                        extraidos.append(None)
                        break
                    texto = texto.strip() if isinstance(texto, str) else ''
                    extraidos.append(texto)
                    if len(texto) < min_chars_pagina:
                        break
                textos = tuple(extraidos)

        return InspecaoPdf(
            page_count=page_count,
            tamanho_bytes=tamanho_bytes,
            criptografado=criptografado,
            texto_por_pagina=textos,
        )
    except (OcrBackendError, OrcamentoEsgotado):
        raise
    except DependencyError:
        # Neste fluxo, DependencyError = provider AES local indisponível
        # (cryptography ausente ou incompatível). O pypdf o levanta ao abrir
        # o arquivo (ele já tenta a senha vazia no construtor), no decrypt ou
        # só ao decifrar as páginas; por isso o tratamento é aqui, não apenas
        # em volta de `decrypt`. O PDF é cifrado e o serviço pode abri-lo.
        return _inspecao_inconclusiva(tamanho_bytes)
    except Exception as exc:
        raise _erro(
            'INVALID_PDF', 'O PDF não pôde ser interpretado.'
        ) from exc


def paginas_texto_embutido(texto_por_pagina, *, min_chars_pagina=200):
    """Monta páginas locais somente quando todas atingem o mínimo de texto."""
    if not texto_por_pagina:
        return None
    if any(
        not isinstance(texto, str) or len(texto) < min_chars_pagina
        for texto in texto_por_pagina
    ):
        return None
    return [
        {
            'numero_pagina': numero,
            'texto': texto,
            'blocos': {
                'dpi': None,
                'width_px': None,
                'height_px': None,
                'blocos': [],
            },
        }
        for numero, texto in enumerate(texto_por_pagina, start=1)
    ]
