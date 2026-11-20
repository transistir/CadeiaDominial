"""Segunda parte dos testes de leitor de PDF, migrada verbatim."""

import logging
import time
from unittest.mock import patch

from pypdf import PdfReader
from pypdf.errors import DependencyError

from ia_ocr.leitor_pdf import paginas_texto_embutido
from ia_ocr.ocr_client import OrcamentoEsgotado
from ia_ocr.tests.pdf_cifrado import sem_provider_aes


class LeitorPdfTestsParte2:
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
