"""Servidor HTTP local e determinístico para os testes do cliente de extração."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


CAMINHO_ISCA = '/isca-login'


class StubServicoExtracao:
    """Stub do serviço de extração, restrito à interface loopback.

    Um modo fixo por instância: ``ok``, ``500``, ``429``, ``302``,
    ``gotejante`` (1 byte/s), ``grande``, ``nao_json``, ``reset`` (fecha o
    socket sem responder) e ``bloqueante`` (aguarda um ``Event``).
    """

    def __init__(self, modo='ok', *, payload=None, bytes_corpo=None):
        self.modo = modo
        self.payload = payload
        self.bytes_corpo = bytes_corpo
        self.recebidas = []
        self.acessos_isca = 0
        self.evento_liberar = threading.Event()
        self.evento_pausado = threading.Event()
        self._lock = threading.Lock()
        self._servidor = None
        self._thread = None

    @property
    def base_url(self):
        if self._servidor is None:
            raise RuntimeError('StubServicoExtracao ainda não foi iniciado.')
        host, porta = self._servidor.server_address
        return f'http://{host}:{porta}'

    def iniciar(self):
        if self._servidor is not None:
            raise RuntimeError('StubServicoExtracao já foi iniciado.')

        stub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.0'

            def do_POST(self):
                self._atender()

            def do_GET(self):
                self._atender()

            def _atender(self):
                if self.path == CAMINHO_ISCA:
                    with stub._lock:
                        stub.acessos_isca += 1
                    self.send_response(200)
                    self.send_header('Content-Length', '2')
                    self.end_headers()
                    self.wfile.write(b'oi')
                    return

                tamanho = int(self.headers.get('Content-Length', '0'))
                corpo = bytearray()
                while len(corpo) < tamanho:
                    dados = self.rfile.read(min(64 * 1024, tamanho - len(corpo)))
                    if not dados:
                        break
                    corpo.extend(dados)
                with stub._lock:
                    stub.recebidas.append(
                        {
                            'metodo': self.command,
                            'caminho': self.path,
                            'cabecalhos': dict(self.headers.items()),
                            'corpo': bytes(corpo),
                        }
                    )

                if stub.modo == 'reset':
                    # Fecha o socket sem responder: transporte falho de verdade.
                    self.close_connection = True
                    return
                if stub.modo == 'bloqueante':
                    stub.evento_pausado.set()
                    stub.evento_liberar.wait()
                getattr(self, '_modo_' + stub.modo)()

            def _modo_bloqueante(self):
                self._modo_ok()

            def _modo_ok(self):
                corpo = json.dumps(stub.payload or {'meta': {}, 'acts': []})
                self._responder(200, corpo, 'application/json')

            def _modo_500(self):
                corpo = json.dumps(
                    {'error': {'code': 'INFERENCE_FAILED', 'message': 'x'}}
                )
                self._responder(500, corpo, 'application/json')

            def _modo_429(self):
                corpo = json.dumps({'error': {'code': 'QUEUE_FULL'}})
                self._responder(429, corpo, 'application/json')

            def _modo_302(self):
                self.send_response(302)
                self.send_header('Location', f'{stub.base_url}{CAMINHO_ISCA}')
                self.send_header('Content-Length', '0')
                self.end_headers()

            def _modo_gotejante(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', '200')
                self.end_headers()
                # 1 byte/s: o prazo absoluto manda, não o timeout TCP.
                self.wfile.flush()
                try:
                    for _ in range(200):
                        self.wfile.write(b'x')
                        self.wfile.flush()
                        time.sleep(1)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def _modo_grande(self):
                corpo = '{"padding": "%s"}' % ('x' * (stub.bytes_corpo or 6 * 1024 * 1024))
                self._responder(200, corpo, 'application/json')

            def _modo_nao_json(self):
                self._responder(200, '<html>login</html>', 'text/html')

            def _responder(self, status, corpo, content_type):
                dados = corpo.encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(dados)))
                self.end_headers()
                try:
                    self.wfile.write(dados)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, format, *args):
                pass

        self._servidor = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self._servidor.daemon_threads = True
        self._thread = threading.Thread(
            target=self._servidor.serve_forever,
            name='stub-servico-extracao',
            daemon=True,
        )
        self._thread.start()
        return self

    def encerrar(self):
        if self._servidor is None:
            return
        self.evento_liberar.set()
        self._servidor.shutdown()
        self._servidor.server_close()
        self._thread.join()
        self._servidor = None
        self._thread = None
