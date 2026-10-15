"""Fixtures sintéticas para os testes de ia_ocr.

Nada de PDF/documento real: o `arquivo` fica vazio (o backend de OCR é fake
nesta issue) e nenhum byte é escrito no storage.
"""

import uuid
from datetime import date

from django.contrib.auth.models import User

from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Pessoas, TIs,
)


def criar_usuario():
    return User.objects.create_user(username=f'ocr-{uuid.uuid4().hex[:10]}')


def criar_documento_digital(upload_por=None, nome='matricula-sintetica.pdf'):
    """Cria um DocumentoDigital mínimo para pendurar um OcrJob."""
    upload_por = upload_por or criar_usuario()
    sufixo = uuid.uuid4().hex[:8]
    ti = TIs.objects.create(nome=f'TI Teste {sufixo}', codigo=f'TI-{sufixo}', etnia='Teste')
    cartorio = Cartorios.objects.create(
        nome=f'CRI Teste {sufixo}', cns=f'CNS-{sufixo}', estado='SP'
    )
    proprietario = Pessoas.objects.create(nome=f'Proprietário {uuid.uuid4().hex[:8]}')
    tipo = DocumentoTipo.objects.create(tipo=f'transcricao-{uuid.uuid4().hex[:8]}')
    imovel = Imovel.objects.create(
        nome=f'Imóvel Teste {uuid.uuid4().hex[:8]}',
        matricula=uuid.uuid4().hex[:10],
        terra_indigena_id=ti,
        proprietario=proprietario,
        cartorio=cartorio,
    )
    documento = Documento.objects.create(
        imovel=imovel, tipo=tipo, numero=f'R-{uuid.uuid4().hex[:6]}',
        data=date(2024, 1, 1), cartorio=cartorio, livro='1', folha='1',
    )
    return DocumentoDigital.objects.create(
        documento=documento,
        nome_original=nome,
        tipo_mime='application/pdf',
        tamanho_bytes=20,
        upload_por=upload_por,
    )
