"""``PrazoAbsolutoTlsTests`` e os servidores TLS gotejantes — migração VERBATIM
de ``ia_ocr/tests/test_ocr_client.py`` (Etapa 13 do plano de 400 linhas).

``_ServidorHandshakeGotejante`` e ``_ServidorTlsFluxoGotejante`` só são usados
aqui e ficam no mesmo arquivo da classe (herdam de ``_ServidorFluxoGotejante``
de ``test_ocr_client_prazo.py``).
"""

import json
import shutil
import ssl
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from ia_ocr.ocr_client import OcrServiceClient, OrcamentoEsgotado

from .test_ocr_client_prazo import _ServidorFluxoGotejante


class _ServidorHandshakeGotejante(_ServidorFluxoGotejante):
    """Responde sem esperar requisição HTTP, como um servidor TLS que goteja o ServerHello."""

    def _atender(self, conexao):
        with conexao:
            try:
                self._responder(conexao)
            except OSError:
                return


class _ServidorTlsFluxoGotejante(_ServidorFluxoGotejante):
    def __init__(self, pedacos, pausa_s, contexto):
        super().__init__(pedacos, pausa_s)
        self._contexto = contexto

    def _atender(self, conexao):
        try:
            conexao = self._contexto.wrap_socket(conexao, server_side=True)
        except OSError:
            conexao.close()
            return
        super()._atender(conexao)


@unittest.skipUnless(
    shutil.which('openssl'), 'openssl indisponível para gerar o certificado de teste'
)
class PrazoAbsolutoTlsTestsParte:
    PAUSA_BYTE_S = 0.02
    PRAZO_S = 0.1
    MARGEM_S = 0.5

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        diretorio = tempfile.TemporaryDirectory()
        cls.addClassCleanup(diretorio.cleanup)
        caminho = Path(diretorio.name)
        cls.certificado = caminho / 'cert.pem'
        chave = caminho / 'chave.pem'
        subprocess.run(
            [
                'openssl', 'req', '-x509', '-newkey', 'ec',
                '-pkeyopt', 'ec_paramgen_curve:prime256v1', '-nodes',
                '-keyout', str(chave), '-out', str(cls.certificado),
                '-days', '1', '-subj', '/CN=localhost',
                '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
            ],
            check=True,
            capture_output=True,
        )
        cls.contexto_servidor = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.contexto_servidor.load_cert_chain(cls.certificado, chave)

    def _assert_aborta_no_prazo_tls(self, pedacos):
        servidor = _ServidorTlsFluxoGotejante(
            pedacos, self.PAUSA_BYTE_S, self.contexto_servidor,
        )
        servidor.iniciar()
        self.addCleanup(servidor.encerrar)
        cliente = OcrServiceClient(
            servidor.base_url.replace('http://', 'https://'),
            'token', 'access-id', 'access-secret',
            timeout_s=1, backoff_base_s=0,
        )
        cliente.sessao.verify = str(self.certificado)

        inicio = time.monotonic()
        with self.assertRaises(OrcamentoEsgotado):
            cliente.consultar_job('job-tls', inicio + self.PRAZO_S)

        self.assertLess(time.monotonic() - inicio, self.PRAZO_S + self.MARGEM_S)

    def test_https_cabecalhos_gotejantes_estouram_no_prazo_real(self):
        resposta = (
            b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
            b'X-Lenta: ' + b'a' * 60 + b'\r\nContent-Length: 100\r\n\r\n'
            + b'x' * 100
        )
        self._assert_aborta_no_prazo_tls([bytes([byte]) for byte in resposta])

    def test_handshake_tls_gotejante_estoura_no_prazo_real(self):
        registro = b'\x16\x03\x03\x3f\xff' + b'\x00' * 150
        servidor = _ServidorHandshakeGotejante(
            [bytes([byte]) for byte in registro], self.PAUSA_BYTE_S
        )
        servidor.iniciar()
        self.addCleanup(servidor.encerrar)
        cliente = OcrServiceClient(
            servidor.base_url.replace('http://', 'https://'),
            'token', 'access-id', 'access-secret',
            timeout_s=1, backoff_base_s=0,
        )
        cliente.sessao.verify = str(self.certificado)

        inicio = time.monotonic()
        with self.assertRaises(OrcamentoEsgotado):
            cliente.consultar_job('job-handshake', inicio + self.PRAZO_S)

        self.assertLess(time.monotonic() - inicio, self.PRAZO_S + self.MARGEM_S)

    def test_https_corpo_gotejante_estoura_no_prazo_real(self):
        corpo = json.dumps({'job_id': 'job-tls', 'status': 'processing'}).encode()
        cabecalhos = (
            b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
            b'Content-Length: ' + str(len(corpo) + 100).encode() + b'\r\n'
            b'Connection: close\r\n\r\n'
        )
        self._assert_aborta_no_prazo_tls(
            [cabecalhos] + [bytes([byte]) for byte in corpo + b'x' * 100]
        )

    def test_connect_do_proxy_https_gotejante_estoura_no_prazo_real(self):
        resposta = (
            b'HTTP/1.1 200 Connection established\r\n'
            b'X-Lenta: ' + b'a' * 60 + b'\r\n\r\n'
        )
        proxy = _ServidorTlsFluxoGotejante(
            [bytes([byte]) for byte in resposta],
            self.PAUSA_BYTE_S,
            self.contexto_servidor,
        )
        proxy.iniciar()
        self.addCleanup(proxy.encerrar)
        cliente = OcrServiceClient(
            'https://servico.invalido', 'token', 'access-id', 'access-secret',
            timeout_s=1, backoff_base_s=0,
        )
        cliente.sessao.trust_env = False
        cliente.sessao.verify = str(self.certificado)
        cliente.sessao.proxies = {
            'https': proxy.base_url.replace('http://', 'https://')
        }

        inicio = time.monotonic()
        with self.assertRaises(OrcamentoEsgotado):
            cliente.consultar_job('job-connect-tls', inicio + self.PRAZO_S)

        self.assertLess(time.monotonic() - inicio, self.PRAZO_S + self.MARGEM_S)
