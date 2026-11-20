"""``PrazoAbsolutoTests`` e seus servidores gotejantes — migração VERBATIM de
``ia_ocr/tests/test_ocr_client.py`` (Etapa 13 do plano de 400 linhas).

``_TransporteSemShutdown``, ``_gzip_com_nome``, ``_ServidorBase``,
``_ServidorBrutoGotejante`` e ``_ServidorFluxoGotejante`` só são usados aqui
(os gotejantes TLS de ``test_ocr_client_tls.py`` herdam de
``_ServidorFluxoGotejante``).
"""

import json
import socket
import struct
import threading
import time
import zlib
from pathlib import Path

from ia_ocr.ocr_client import (
    OcrServiceClient,
    OrcamentoEsgotado,
    _PrazoAbsoluto,
)
from ia_ocr.tests.stub_servico import StubServicoOcr


class _TransporteSemShutdown:
    """Imita o SSLTransport do urllib3: embrulha o socket real em ``.socket``, sem ``shutdown``."""

    def __init__(self, socket_real):
        self.socket = socket_real


def _gzip_com_nome(dados, nome):
    compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    deflate = compressor.compress(dados) + compressor.flush()
    cabecalho = b'\x1f\x8b\x08\x08\x00\x00\x00\x00\x00\xff' + nome + b'\x00'
    rodape = struct.pack('<II', zlib.crc32(dados), len(dados) & 0xFFFFFFFF)
    return cabecalho + deflate + rodape


class _ServidorBase:
    def __init__(self, pausa_s):
        self._pausa_s = pausa_s
        self._encerrado = False
        self._escuta = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._escuta.bind(('127.0.0.1', 0))
        self._escuta.listen()
        self._escuta.settimeout(0.1)
        host, porta = self._escuta.getsockname()
        self.base_url = f'http://{host}:{porta}'
        self._thread = threading.Thread(target=self._aceitar, daemon=True)

    def iniciar(self):
        self._thread.start()
        return self

    def encerrar(self):
        self._encerrado = True
        self._thread.join()
        self._escuta.close()

    def _aceitar(self):
        while not self._encerrado:
            try:
                conexao, _ = self._escuta.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(
                target=self._atender, args=(conexao,), daemon=True
            ).start()

    def _atender(self, conexao):
        with conexao:
            try:
                recebido = b''
                while b'\r\n\r\n' not in recebido:
                    dados = conexao.recv(4096)
                    if not dados:
                        return
                    recebido += dados
                self._responder(conexao)
            except OSError:
                return


class _ServidorBrutoGotejante(_ServidorBase):
    """Envia a resposta crua: cabeçalhos de uma vez, corpo um byte por vez."""

    def __init__(self, resposta, pausa_s):
        super().__init__(pausa_s)
        self._resposta = resposta
        self._fim_cabecalhos = resposta.index(b'\r\n\r\n') + 4

    def _responder(self, conexao):
        conexao.sendall(self._resposta[: self._fim_cabecalhos])
        for indice in range(self._fim_cabecalhos, len(self._resposta)):
            conexao.sendall(self._resposta[indice : indice + 1])
            time.sleep(self._pausa_s)


class _ServidorFluxoGotejante(_ServidorBase):
    """Envia pedaços da lista um a um e depois segura a conexão aberta."""

    def __init__(self, pedacos, pausa_s):
        super().__init__(pausa_s)
        self._pedacos = pedacos

    def _responder(self, conexao):
        for pedaco in self._pedacos:
            conexao.sendall(pedaco)
            time.sleep(self._pausa_s)
        while not self._encerrado:
            time.sleep(0.01)


class PrazoAbsolutoTestsParte:
    """O prazo do job vale para cada leitura, inclusive dentro do decoder e do framing."""

    PAUSA_BYTE_S = 0.02
    PRAZO_S = 0.1
    MARGEM_S = 0.5

    JSON_PROCESSANDO = json.dumps({'job_id': 'job-drip', 'status': 'processing'})

    def _resposta_bruta(self, cabecalhos, corpo, fechar_conexao):
        fechamento = ['Connection: close'] if fechar_conexao else []
        linhas = ['HTTP/1.1 200 OK', *cabecalhos, *fechamento, '', '']
        return '\r\n'.join(linhas).encode('ascii') + corpo

    def _assert_aborta_no_prazo(self, servidor):
        servidor.iniciar()
        self.addCleanup(servidor.encerrar)
        cliente = OcrServiceClient(
            servidor.base_url, 'token', 'access-id', 'access-secret',
            timeout_s=1, backoff_base_s=0,
        )

        inicio = time.monotonic()
        with self.assertRaises(OrcamentoEsgotado):
            cliente.consultar_job('job-drip', inicio + self.PRAZO_S)

        self.assertLess(time.monotonic() - inicio, self.PRAZO_S + self.MARGEM_S)

    def _assert_estoura_no_prazo(self, cabecalhos, corpo, fechar_conexao=True):
        self._assert_aborta_no_prazo(
            _ServidorBrutoGotejante(
                self._resposta_bruta(cabecalhos, corpo, fechar_conexao),
                self.PAUSA_BYTE_S,
            )
        )

    @staticmethod
    def _um_byte_por_vez(dados):
        return [dados[indice : indice + 1] for indice in range(len(dados))]

    def test_cabecalhos_gotejantes_desde_o_status_line_estouram_no_prazo_real(self):
        cabecalhos = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: application/json\r\n'
            b'X-Lenta: ' + b'a' * 60 + b'\r\n\r\n'
        )
        self._assert_aborta_no_prazo(
            _ServidorFluxoGotejante(
                self._um_byte_por_vez(cabecalhos + self.JSON_PROCESSANDO.encode()),
                self.PAUSA_BYTE_S,
            )
        )

    def test_cabecalhos_gotejantes_depois_do_status_line_estouram_no_prazo_real(self):
        cabecalhos = (
            b'Content-Type: application/json\r\n'
            b'X-Lenta: ' + b'a' * 60 + b'\r\n\r\n'
        )
        self._assert_aborta_no_prazo(
            _ServidorFluxoGotejante(
                [b'HTTP/1.1 200 OK\r\n']
                + self._um_byte_por_vez(cabecalhos + self.JSON_PROCESSANDO.encode()),
                self.PAUSA_BYTE_S,
            )
        )

    def test_cabecalhos_completos_e_parte_do_corpo_estouram_no_prazo_real(self):
        cabecalhos = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: 100\r\n\r\n'
        )
        self._assert_aborta_no_prazo(
            _ServidorFluxoGotejante(
                self._um_byte_por_vez(cabecalhos) + [b'x' * 10],
                self.PAUSA_BYTE_S,
            )
        )

    def test_gzip_com_nome_gotejante_estoura_no_prazo_real(self):
        corpo = _gzip_com_nome(self.JSON_PROCESSANDO.encode(), b'n' * 100)

        self._assert_estoura_no_prazo(
            [
                'Content-Type: application/json',
                'Content-Encoding: gzip',
                f'Content-Length: {len(corpo)}',
            ],
            corpo,
        )

    def test_gzip_gotejante_com_keep_alive_estoura_no_prazo_real(self):
        corpo = _gzip_com_nome(self.JSON_PROCESSANDO.encode(), b'n' * 100)

        self._assert_estoura_no_prazo(
            [
                'Content-Type: application/json',
                'Content-Encoding: gzip',
                f'Content-Length: {len(corpo)}',
            ],
            corpo,
            fechar_conexao=False,
        )

    def test_chunked_com_extensao_gotejante_estoura_no_prazo_real(self):
        dados = self.JSON_PROCESSANDO.encode()
        corpo = (
            b'%x;ext=' % len(dados)
            + b'a' * 100
            + b'\r\n'
            + dados
            + b'\r\n0\r\n\r\n'
        )

        self._assert_estoura_no_prazo(
            ['Content-Type: application/json', 'Transfer-Encoding: chunked'],
            corpo,
        )

    def test_connect_do_proxy_gotejante_estoura_no_prazo_real(self):
        resposta = (
            b'HTTP/1.1 200 Connection established\r\n'
            b'X-Lenta: ' + b'a' * 60 + b'\r\n\r\n'
        )
        proxy = _ServidorFluxoGotejante(
            self._um_byte_por_vez(resposta), self.PAUSA_BYTE_S
        )
        proxy.iniciar()
        self.addCleanup(proxy.encerrar)
        cliente = OcrServiceClient(
            'https://servico.invalido', 'token', 'access-id', 'access-secret',
            timeout_s=1, backoff_base_s=0,
        )
        cliente.sessao.trust_env = False
        cliente.sessao.proxies = {'https': proxy.base_url}

        inicio = time.monotonic()
        with self.assertRaises(OrcamentoEsgotado):
            cliente.consultar_job('job-connect', inicio + self.PRAZO_S)

        self.assertLess(time.monotonic() - inicio, self.PRAZO_S + 0.25)

    def test_transporte_sem_shutdown_e_interrompido_pelo_socket_de_baixo(self):
        real, outro = socket.socketpair()
        self.addCleanup(real.close)
        self.addCleanup(outro.close)
        real.settimeout(2)
        guarda = _PrazoAbsoluto(time.monotonic() + 0.05)
        self.addCleanup(guarda.encerrar)
        guarda.registrar(_TransporteSemShutdown(real))

        inicio = time.monotonic()
        dados = real.recv(1)

        self.assertEqual(dados, b'')
        self.assertTrue(guarda.estourou)
        self.assertLess(time.monotonic() - inicio, 1)

    def test_cliente_pede_corpo_sem_compressao(self):
        stub = StubServicoOcr([(200, {'job_id': 'job-id', 'status': 'processing'}, {})]).iniciar()
        self.addCleanup(stub.encerrar)

        OcrServiceClient(
            stub.base_url, 'token', 'access-id', 'access-secret', backoff_base_s=0
        ).consultar_job('job-id', time.monotonic() + 5)

        cabecalhos = {k.lower(): v for k, v in stub.recebidas[0]['cabecalhos'].items()}
        self.assertEqual(cabecalhos['accept-encoding'], 'identity')

    def test_sucesso_nao_deixa_timer_de_prazo_vivo(self):
        stub = StubServicoOcr([(200, {'job_id': 'job-id', 'status': 'processing'}, {})]).iniciar()
        self.addCleanup(stub.encerrar)
        timers_antes = [t for t in threading.enumerate() if isinstance(t, threading.Timer)]

        OcrServiceClient(
            stub.base_url, 'token', 'access-id', 'access-secret', backoff_base_s=0
        ).consultar_job('job-id', time.monotonic() + 5)

        timers_depois = [t for t in threading.enumerate() if isinstance(t, threading.Timer)]
        self.assertEqual(timers_depois, timers_antes)

    def test_conexao_devolvida_ao_pool_sai_sem_guarda_de_prazo(self):
        stub = StubServicoOcr([(200, {'job_id': 'job-id', 'status': 'processing'}, {})]).iniciar()
        self.addCleanup(stub.encerrar)
        cliente = OcrServiceClient(
            stub.base_url, 'token', 'access-id', 'access-secret', backoff_base_s=0
        )

        cliente.consultar_job('job-id', time.monotonic() + 5)

        adaptador = cliente.sessao.get_adapter(stub.base_url)
        pool = adaptador.poolmanager.connection_from_url(stub.base_url)
        conexoes = [c for c in pool.pool.queue if c is not None]
        self.assertTrue(conexoes)
        for conexao in conexoes:
            self.assertIsNone(conexao._guarda)

    def test_requirements_declara_urllib3_com_read1(self):
        requisitos = (Path(__file__).resolve().parents[2] / 'requirements.txt').read_text()

        self.assertRegex(requisitos, r'(?m)^urllib3>=2\.6\b')
