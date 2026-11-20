"""Fachada dos testes de leitor de PDF (Etapa 16, limite de 400 linhas)."""

import io
import tempfile
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ia_ocr.backends import OcrBackendError
from ia_ocr.leitor_pdf import inspecionar_pdf

from .test_leitor_pdf_parte1 import LeitorPdfTestsParte1
from .test_leitor_pdf_parte2 import LeitorPdfTestsParte2


class LeitorPdfBase(SimpleTestCase):
    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.addCleanup(self.diretorio.cleanup)

    def _gravar(self, conteudo, nome='documento.pdf'):
        caminho = Path(self.diretorio.name) / nome
        caminho.write_bytes(conteudo)
        return caminho

    @staticmethod
    def _pdf(*, paginas=1, width=612, height=792, textos=None, configurar=None):
        writer = PdfWriter()
        for indice in range(paginas):
            pagina = writer.add_blank_page(width=width, height=height)
            if configurar is not None:
                configurar(pagina, indice)
            if textos is not None:
                texto = textos[indice]
                fonte = DictionaryObject(
                    {
                        NameObject('/Type'): NameObject('/Font'),
                        NameObject('/Subtype'): NameObject('/Type1'),
                        NameObject('/BaseFont'): NameObject('/Helvetica'),
                    }
                )
                pagina[NameObject('/Resources')] = DictionaryObject(
                    {
                        NameObject('/Font'): DictionaryObject(
                            {NameObject('/F1'): fonte}
                        )
                    }
                )
                conteudo = DecodedStreamObject()
                conteudo.set_data(
                    f'BT /F1 12 Tf 72 720 Td ({texto}) Tj ET'.encode('ascii')
                )
                pagina[NameObject('/Contents')] = conteudo
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    @staticmethod
    def _pdf_criptografado(*, senha_usuario, senha_dono=None, paginas=1):
        writer = PdfWriter()
        for _ in range(paginas):
            writer.add_blank_page(width=612, height=792)
        writer.encrypt(
            user_password=senha_usuario,
            owner_password=senha_dono,
            algorithm='RC4-128',
        )
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    @staticmethod
    def _pdf_objstm_jbig2_corrompido():
        """PDF 1.5 SEM /Encrypt cujo catálogo vive num /ObjStm com
        /Filter /JBIG2Decode (dados inválidos). Abrir o arquivo funciona;
        resolver o catálogo exige decodificar o JBIG2."""
        cabecalho = b'%PDF-1.5\n'
        lixo = b'dados-jbig2-corrompidos'
        objstm = (
            b'1 0 obj\n'
            + (
                '<< /Type /ObjStm /N 1 /First 4 /Filter /JBIG2Decode '
                f'/Length {len(lixo)} >>\n'
            ).encode()
            + b'stream\n'
            + lixo
            + b'\nendstream\nendobj\n'
        )
        offset_objstm = len(cabecalho)
        offset_xref = offset_objstm + len(objstm)
        # /W [1 2 1]: tipo, offset (ou nº do ObjStm), geração (ou índice).
        entradas = [
            (0, 0, 255),  # objeto 0: livre
            (1, offset_objstm, 0),  # objeto 1: o /ObjStm
            (1, offset_xref, 0),  # objeto 2: o próprio xref stream
            (2, 1, 0),  # objeto 3 (catálogo): índice 0 do ObjStm 1
        ]
        tabela = b''.join(
            bytes([tipo]) + campo.to_bytes(2, 'big') + bytes([extra])
            for tipo, campo, extra in entradas
        )
        xref = (
            b'2 0 obj\n'
            + (
                '<< /Type /XRef /Size 4 /W [1 2 1] /Root 3 0 R '
                f'/Length {len(tabela)} >>\n'
            ).encode()
            + b'stream\n'
            + tabela
            + b'\nendstream\nendobj\n'
        )
        return (
            cabecalho
            + objstm
            + xref
            + f'startxref\n{offset_xref}\n%%EOF\n'.encode()
        )

    def _inspecionar(self, caminho, **kwargs):
        parametros = {'max_bytes': 50 * 1024 * 1024, 'max_paginas': 25}
        parametros.update(kwargs)
        return inspecionar_pdf(caminho, **parametros)

    def _assert_codigo(self, codigo, caminho, **kwargs):
        with self.assertRaises(OcrBackendError) as contexto:
            self._inspecionar(caminho, **kwargs)
        self.assertEqual(contexto.exception.codigo, codigo)



class LeitorPdfTests(
    LeitorPdfTestsParte1, LeitorPdfTestsParte2, LeitorPdfBase
):
    """Fachada com o ID histórico; corpos nas duas partes."""
