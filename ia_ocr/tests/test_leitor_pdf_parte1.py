"""Primeira parte dos testes de leitor de PDF, migrada verbatim."""

from unittest.mock import patch

from pypdf._crypt_providers import crypt_provider

from ia_ocr.backends import OcrBackendError
from ia_ocr.leitor_pdf import InspecaoPdf
from ia_ocr.tests.pdf_cifrado import (
    erro_dependencia_aes,
    gerar_pdf_aes,
    sem_provider_aes,
)

ALGORITMOS_AES = ('AES-128', 'AES-256-R5', 'AES-256')


class LeitorPdfTestsParte1:
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
