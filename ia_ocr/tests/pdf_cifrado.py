"""PDFs AES sintéticos e a simulação de "sem provider AES" (issue #280).

Sem `cryptography` utilizável o pypdf cai no provider `_fallback`: RC4 em
Python puro, mas qualquer operação AES levanta `DependencyError`.
`sem_provider_aes()` reproduz esse ambiente dentro do processo de teste usando
o próprio `_fallback` do pypdf, então o erro nasce no mesmo ponto de uma
instalação sem a dependência. Gere o PDF FORA do bloco: o writer também
precisa do provider real.
"""

import io
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf._crypt_providers import _fallback
from pypdf.generic import NameObject, TextStringObject

# Nomes que `pypdf._encryption` importa do provider ativo e usa para AES.
_NOMES_AES = (
    'CryptAES',
    'aes_cbc_decrypt',
    'aes_cbc_encrypt',
    'aes_ecb_decrypt',
    'aes_ecb_encrypt',
)


def gerar_pdf_aes(
    *,
    algoritmo='AES-256',
    senha_usuario='',
    senha_dono='senha-do-dono',
    paginas=2,
    string_na_pagina=False,
):
    """Gera um PDF de páginas em branco cifrado com AES.

    `string_na_pagina` grava uma string no dicionário de cada página. No
    AES-128 isso obriga a decifrar ao percorrer as páginas (a falha sem
    provider só aparece aí); no AES-256 ela já ocorre ao abrir o arquivo.
    """
    writer = PdfWriter()
    for _ in range(paginas):
        pagina = writer.add_blank_page(width=612, height=792)
        if string_na_pagina:
            pagina[NameObject('/TesteIa')] = TextStringObject('valor cifrado')
    writer.encrypt(
        user_password=senha_usuario,
        owner_password=senha_dono,
        algorithm=algoritmo,
    )
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def sem_provider_aes():
    """Context manager: o AES do pypdf passa a ser o do `_fallback`."""
    return patch.multiple(
        'pypdf._encryption',
        **{nome: getattr(_fallback, nome) for nome in _NOMES_AES},
    )
