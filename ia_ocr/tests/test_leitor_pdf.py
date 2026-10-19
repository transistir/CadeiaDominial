import io
import logging
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase
from pypdf import PdfReader, PdfWriter
from pypdf._crypt_providers import crypt_provider
from pypdf.errors import DependencyError
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ia_ocr.backends import OcrBackendError
from ia_ocr.leitor_pdf import (
    InspecaoPdf,
    inspecionar_pdf,
    paginas_texto_embutido,
)
from ia_ocr.ocr_client import OrcamentoEsgotado
from ia_ocr.tests.pdf_cifrado import (
    erro_dependencia_aes,
    gerar_pdf_aes,
    sem_provider_aes,
)

ALGORITMOS_AES = ('AES-128', 'AES-256-R5', 'AES-256')


class LeitorPdfTests(SimpleTestCase):
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

    def test_arquivo_vazio_retorna_empty_file(self):
        self._assert_codigo('EMPTY_FILE', self._gravar(b''))

    def test_arquivo_maior_que_limite_retorna_file_too_large(self):
        caminho = self._gravar(b'%PDF-' + b'x' * 12)
        self._assert_codigo('FILE_TOO_LARGE', caminho, max_bytes=16)

    def test_magic_bytes_png_retorna_unsupported_media_type(self):
        caminho = self._gravar(b'\x89PNG\r\n\x1a\nconteudo')
        self._assert_codigo('UNSUPPORTED_MEDIA_TYPE', caminho)

    def test_magic_bytes_jpeg_retorna_unsupported_media_type(self):
        caminho = self._gravar(b'\xff\xd8\xffconteudo')
        self._assert_codigo('UNSUPPORTED_MEDIA_TYPE', caminho)

    def test_magic_bytes_webp_retorna_unsupported_media_type(self):
        caminho = self._gravar(b'RIFF\x04\x00\x00\x00WEBPconteudo')
        self._assert_codigo('UNSUPPORTED_MEDIA_TYPE', caminho)

    def test_lixo_nao_pdf_retorna_invalid_pdf(self):
        self._assert_codigo('INVALID_PDF', self._gravar(b'nao e um pdf'))

    def test_pdf_sem_paginas_retorna_invalid_pdf(self):
        self._assert_codigo('INVALID_PDF', self._gravar(self._pdf(paginas=0)))

    def test_pdf_so_com_senha_de_dono_e_aceito(self):
        caminho = self._gravar(
            self._pdf_criptografado(
                senha_usuario='', senha_dono='dono-do-teste', paginas=2
            )
        )

        resultado = self._inspecionar(caminho)

        self.assertEqual(resultado.page_count, 2)
        self.assertEqual(resultado.tamanho_bytes, caminho.stat().st_size)
        self.assertTrue(resultado.criptografado)
        self.assertIsNone(resultado.texto_por_pagina)

    def test_pdf_com_senha_de_usuario_retorna_encrypted_pdf(self):
        caminho = self._gravar(
            self._pdf_criptografado(senha_usuario='segredo-do-teste')
        )
        self._assert_codigo('ENCRYPTED_PDF', caminho)

    def test_dependency_error_no_decrypt_e_inconclusivo_e_segue(self):
        caminho = self._gravar(
            self._pdf_criptografado(
                senha_usuario='', senha_dono='dono-do-teste', paginas=2
            )
        )

        with patch(
            'ia_ocr.leitor_pdf.PdfReader.decrypt',
            side_effect=erro_dependencia_aes(),
        ):
            resultado = self._inspecionar(caminho)

        self.assertIsNone(resultado.page_count)
        self.assertTrue(resultado.criptografado)

    def test_pypdf_usa_o_cryptography_como_provider_de_aes(self):
        """O piso de `cryptography` no requirements.txt existe para isto: sem
        um provider AES utilizável o pypdf cai no `_fallback` e todo PDF AES
        vira DependencyError (issue #280)."""
        self.assertEqual(
            crypt_provider[0],
            'cryptography',
            'provider AES do pypdf indisponível: confira o piso de '
            'cryptography no requirements.txt',
        )

    def test_pdf_aes_sem_senha_de_usuario_e_aceito_e_conta_as_paginas(self):
        for algoritmo in ALGORITMOS_AES:
            with self.subTest(algoritmo=algoritmo):
                caminho = self._gravar(
                    gerar_pdf_aes(algoritmo=algoritmo, paginas=3),
                    nome=f'{algoritmo}.pdf',
                )

                resultado = self._inspecionar(caminho)

                self.assertEqual(resultado.page_count, 3)
                self.assertEqual(
                    resultado.tamanho_bytes, caminho.stat().st_size
                )
                self.assertTrue(resultado.criptografado)
                self.assertIsNone(resultado.texto_por_pagina)

    def test_pdf_aes_com_senha_de_usuario_retorna_encrypted_pdf(self):
        for algoritmo in ALGORITMOS_AES:
            with self.subTest(algoritmo=algoritmo):
                caminho = self._gravar(
                    gerar_pdf_aes(
                        algoritmo=algoritmo, senha_usuario='segredo-do-teste'
                    ),
                    nome=f'{algoritmo}.pdf',
                )

                with self.assertRaises(OcrBackendError) as contexto:
                    self._inspecionar(caminho)

                self.assertEqual(contexto.exception.codigo, 'ENCRYPTED_PDF')
                self.assertEqual(
                    contexto.exception.mensagem,
                    'O PDF exige senha de usuário para ser aberto.',
                )

    def test_aes_256_sem_provider_local_falha_ao_abrir_e_e_inconclusivo(self):
        """Sem `cryptography` o pypdf levanta DependencyError no próprio
        construtor (ele já tenta a senha vazia ao abrir). Não é PDF inválido
        nem dá para afirmar que exige senha: o serviço decide."""
        for senha_usuario in ('', 'segredo-do-teste'):
            with self.subTest(com_senha_de_usuario=bool(senha_usuario)):
                caminho = self._gravar(
                    gerar_pdf_aes(
                        algoritmo='AES-256', senha_usuario=senha_usuario
                    )
                )

                with sem_provider_aes():
                    resultado = self._inspecionar(caminho)

                self.assertEqual(
                    resultado,
                    InspecaoPdf(
                        page_count=None,
                        tamanho_bytes=caminho.stat().st_size,
                        criptografado=True,
                        texto_por_pagina=None,
                    ),
                )

    def test_aes_128_sem_provider_local_falha_ao_ler_paginas_e_e_inconclusivo(
        self,
    ):
        """No AES-128 o construtor passa (a verificação usa RC4/MD5); o
        DependencyError só aparece ao decifrar o dicionário das páginas, bem
        depois da abertura."""
        caminho = self._gravar(
            gerar_pdf_aes(
                algoritmo='AES-128', paginas=2, string_na_pagina=True
            )
        )

        with sem_provider_aes():
            resultado = self._inspecionar(caminho, ler_texto=True)

        self.assertEqual(
            resultado,
            InspecaoPdf(
                page_count=None,
                tamanho_bytes=caminho.stat().st_size,
                criptografado=True,
                texto_por_pagina=None,
            ),
        )

    def test_pdf_invalido_continua_invalid_pdf_sem_provider_local(self):
        """O atalho do DependencyError não pode engolir PDF realmente
        inválido: lixo e PDF truncado seguem como INVALID_PDF."""
        conteudos = {
            'bytes arbitrários': b'nao e um pdf',
            'pdf truncado': b'%PDF-1.4\nconteudo truncado e sensivel',
        }
        for descricao, conteudo in conteudos.items():
            with self.subTest(descricao):
                caminho = self._gravar(conteudo)

                with sem_provider_aes():
                    self._assert_codigo('INVALID_PDF', caminho)

    def test_pdf_corrompido_com_jbig2_sem_jbig2dec_continua_invalid_pdf(self):
        """O atalho do DependencyError é só do provider AES. O pypdf também o
        levanta fora de criptografia: PDF corrompido, SEM /Encrypt, com
        /ObjStm em /JBIG2Decode e sem `jbig2dec`. Isso é PDF inválido, não um
        "cifrado que o serviço decide"."""
        caminho = self._gravar(self._pdf_objstm_jbig2_corrompido())

        # Fixa o `jbig2dec` como ausente, haja ou não o binário na máquina.
        with patch('pypdf.filters.JBIG2DEC_BINARY', None):
            # A fixture tem de cair mesmo no DependencyError do pypdf; sem
            # isto o INVALID_PDF abaixo passaria por outro motivo.
            reader = PdfReader(str(caminho), strict=False)
            self.assertFalse(reader.is_encrypted)
            with self.assertRaises(DependencyError):
                len(reader.pages)

            self._assert_codigo('INVALID_PDF', caminho)

    def test_pdf_corrompido_truncado_retorna_invalid_pdf(self):
        caminho = self._gravar(b'%PDF-1.4\nconteudo truncado e sensivel')
        self._assert_codigo('INVALID_PDF', caminho)

    def test_mediabox_com_dimensao_invalida_retorna_invalid_pdf(self):
        caminho = self._gravar(self._pdf(width=0, height=792))
        self._assert_codigo('INVALID_PDF', caminho)

    def test_mediabox_invertido_e_aceito_usando_valor_absoluto(self):
        def inverter(pagina, _indice):
            pagina.mediabox.lower_left = (612, 0)
            pagina.mediabox.upper_right = (0, 792)

        caminho = self._gravar(self._pdf(configurar=inverter))

        resultado = self._inspecionar(caminho)

        self.assertEqual(resultado.page_count, 1)

    def test_borda_maior_que_3600_retorna_pdf_page_too_large(self):
        caminho = self._gravar(self._pdf(width=3601, height=100))
        self._assert_codigo('PDF_PAGE_TOO_LARGE', caminho)

    def test_area_maior_que_10_milhoes_retorna_pdf_page_too_large(self):
        caminho = self._gravar(self._pdf(width=3200, height=3200))
        self._assert_codigo('PDF_PAGE_TOO_LARGE', caminho)

    def test_paginas_acima_do_limite_retorna_too_many_pages(self):
        caminho = self._gravar(self._pdf(paginas=3))
        self._assert_codigo('TOO_MANY_PAGES', caminho, max_paginas=2)

    def test_texto_embutido_em_todas_as_paginas_retorna_paginas(self):
        textos = ['a' * 200, 'b' * 230]
        resultado = self._inspecionar(
            self._gravar(self._pdf(paginas=2, textos=textos)),
            ler_texto=True,
        )

        paginas = paginas_texto_embutido(resultado.texto_por_pagina)

        self.assertEqual(
            paginas,
            [
                {
                    'numero_pagina': 1,
                    'texto': textos[0],
                    'blocos': {
                        'dpi': None,
                        'width_px': None,
                        'height_px': None,
                        'blocos': [],
                    },
                },
                {
                    'numero_pagina': 2,
                    'texto': textos[1],
                    'blocos': {
                        'dpi': None,
                        'width_px': None,
                        'height_px': None,
                        'blocos': [],
                    },
                },
            ],
        )

    def test_limiar_configurado_abaixo_de_200_le_todas_as_paginas(self):
        """A saída antecipada da extração usa o limiar CONFIGURADO: com
        limiar 150, uma página de 160 chars no MEIO não pode truncar a
        tupla (o default 200 da constante faria o resultado virar
        INVALID_OCR_RESULT na finalização)."""
        textos = ['a' * 220, 'b' * 160, 'c' * 220]
        resultado = self._inspecionar(
            self._gravar(self._pdf(paginas=3, textos=textos)),
            ler_texto=True,
            min_chars_pagina=150,
        )

        self.assertEqual(len(resultado.texto_por_pagina), 3)
        paginas = paginas_texto_embutido(
            resultado.texto_por_pagina, min_chars_pagina=150
        )
        self.assertEqual(
            paginas,
            [
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
                for numero, texto in enumerate(textos, start=1)
            ],
        )

    def test_pdf_misto_retorna_none_e_para_na_primeira_pagina_curta(self):
        resultado = self._inspecionar(
            self._gravar(
                self._pdf(
                    paginas=3,
                    textos=['a' * 220, 'curto', 'nao deve ser lido' * 30],
                )
            ),
            ler_texto=True,
        )

        self.assertIsInstance(resultado.texto_por_pagina, tuple)
        self.assertEqual(len(resultado.texto_por_pagina), 2)
        self.assertIsNone(paginas_texto_embutido(resultado.texto_por_pagina))

    def test_excecao_em_extract_text_retorna_none_sem_invalid_pdf(self):
        caminho = self._gravar(self._pdf(textos=['a' * 220]))

        with patch(
            'pypdf._page.PageObject.extract_text',
            side_effect=RuntimeError('falha de extracao'),
        ):
            resultado = self._inspecionar(caminho, ler_texto=True)

        self.assertIsInstance(resultado.texto_por_pagina, tuple)
        self.assertIsNone(paginas_texto_embutido(resultado.texto_por_pagina))

    def test_prazo_curto_com_muitas_paginas_esgota_orcamento(self):
        caminho = self._gravar(
            self._pdf(paginas=8, textos=['x' * 220 for _ in range(8)])
        )

        with self.assertRaises(OrcamentoEsgotado):
            self._inspecionar(
                caminho,
                prazo=time.monotonic(),
                ler_texto=True,
            )

    def test_logger_pypdf_nao_propaga_warning_de_pdf_corrompido(self):
        caminho = self._gravar(b'%PDF-1.4\nconteudo-sensivel-sem-eof')
        capturados = []

        class Capturar(logging.Handler):
            def emit(self, record):
                capturados.append(record)

        raiz = logging.getLogger()
        handler = Capturar(level=logging.WARNING)
        raiz.addHandler(handler)
        self.addCleanup(raiz.removeHandler, handler)

        self._assert_codigo('INVALID_PDF', caminho)

        self.assertEqual(capturados, [])
