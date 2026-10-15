"""Servidor HTTP local e determinístico para os testes do cliente OCR."""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class StubServicoOcr:
    """Stub roteirizado do serviço OCR, restrito à interface loopback."""

    def __init__(
        self,
        respostas,
        *,
        tamanho_chunk_resposta=None,
        pausa_s=0,
        token_esperado=None,
    ):
        self._respostas = deque(respostas)
        self._lock = threading.Lock()
        self.tamanho_chunk_resposta = tamanho_chunk_resposta
        self.pausa_s = pausa_s
        # None mantém a checagem de presença (comportamento da I-1); um valor
        # concreto exige OUTRO token — o caminho do 401/UNAUTHORIZED do #259.
        self.token_esperado = token_esperado
        self.recebidas = []
        self.jobs_aceitos = set()
        self._servidor = None
        self._thread = None

    @property
    def base_url(self):
        if self._servidor is None:
            raise RuntimeError('StubServicoOcr ainda não foi iniciado.')
        host, porta = self._servidor.server_address
        return f'http://{host}:{porta}'

    def iniciar(self):
        if self._servidor is not None:
            raise RuntimeError('StubServicoOcr já foi iniciado.')

        stub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.0'

            def do_GET(self):
                self._atender()

            def do_POST(self):
                self._atender()

            def _atender(self):
                tamanho = int(self.headers.get('Content-Length', '0'))
                partes = urlsplit(self.path)
                corpo_em_progresso = bytearray()
                recebida = {
                    'metodo': self.command,
                    'caminho': partes.path,
                    'query': parse_qs(partes.query, keep_blank_values=True),
                    'query_bruta': partes.query,
                    'cabecalhos': dict(self.headers.items()),
                    'content_length': tamanho,
                    'corpo_bruto': corpo_em_progresso,
                    'upload_completo': tamanho == 0,
                    'campos': {},
                    'arquivo_bytes': None,
                }
                with stub._lock:
                    stub.recebidas.append(recebida)

                restante = tamanho
                tamanho_chunk_upload = getattr(
                    stub, 'tamanho_chunk_upload', 64 * 1024
                )
                while restante > 0:
                    dados = self.rfile.read(min(restante, tamanho_chunk_upload))
                    if not dados:
                        break
                    with stub._lock:
                        corpo_em_progresso.extend(dados)
                    restante -= len(dados)
                    pausa_upload_s = getattr(stub, 'pausa_upload_s', 0)
                    if pausa_upload_s:
                        time.sleep(pausa_upload_s)

                corpo = bytes(corpo_em_progresso)
                upload_completo = len(corpo) == tamanho
                if upload_completo:
                    campos, arquivo = stub._decodificar_multipart(
                        self.headers.get('Content-Type'), corpo
                    )
                else:
                    campos, arquivo = {}, None
                with stub._lock:
                    recebida.update(
                        {
                            'corpo_bruto': corpo,
                            'upload_completo': upload_completo,
                            'campos': campos,
                            'arquivo_bytes': arquivo,
                        }
                    )
                    if self.command == 'POST' and campos.get('job_id'):
                        stub.jobs_aceitos.add(campos['job_id'])

                if not upload_completo:
                    self.close_connection = True
                    return

                if not self.headers.get('CF-Access-Client-Id') or not self.headers.get(
                    'CF-Access-Client-Secret'
                ):
                    self._responder(
                        403,
                        {
                            'ok': False,
                            'error': {
                                'code': 'UNAUTHORIZED',
                                'message': 'Cloudflare Access ausente.',
                            },
                        },
                        {},
                    )
                    return
                token_recebido = self.headers.get('X-Internal-Token')
                token_invalido = not token_recebido or (
                    stub.token_esperado is not None
                    and token_recebido != stub.token_esperado
                )
                if token_invalido:
                    self._responder(
                        401,
                        {
                            'ok': False,
                            'error': {
                                'code': 'UNAUTHORIZED',
                                'message': 'Token interno ausente ou divergente.',
                            },
                        },
                        {},
                    )
                    return

                with stub._lock:
                    resposta = stub._respostas.popleft() if stub._respostas else None
                if resposta is None:
                    self._responder(
                        500,
                        {
                            'ok': False,
                            'error': {
                                'code': 'INFERENCE_FAILED',
                                'message': 'Roteiro de respostas esgotado.',
                            },
                        },
                        {},
                    )
                    return

                status, corpo_resposta, cabecalhos = resposta
                if status is None:
                    # Simula o servidor aceitando todo o POST e perdendo a resposta.
                    self.close_connection = True
                    return
                self._responder(status, corpo_resposta, cabecalhos)

            def _responder(self, status, corpo, cabecalhos):
                if isinstance(corpo, (dict, list)):
                    dados = json.dumps(corpo).encode('utf-8')
                    cabecalhos = {'Content-Type': 'application/json', **cabecalhos}
                elif isinstance(corpo, str):
                    dados = corpo.encode('utf-8')
                else:
                    dados = corpo

                self.send_response(status)
                for nome, valor in cabecalhos.items():
                    self.send_header(nome, valor)
                self.send_header('Content-Length', str(len(dados)))
                self.end_headers()

                tamanho_chunk = stub.tamanho_chunk_resposta or len(dados) or 1
                try:
                    for inicio in range(0, len(dados), tamanho_chunk):
                        self.wfile.write(dados[inicio : inicio + tamanho_chunk])
                        self.wfile.flush()
                        if stub.pausa_s:
                            time.sleep(stub.pausa_s)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, format, *args):
                pass

        self._servidor = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self._servidor.daemon_threads = True
        self._thread = threading.Thread(
            target=self._servidor.serve_forever,
            name='stub-servico-ocr',
            daemon=True,
        )
        self._thread.start()
        return self

    def encerrar(self):
        if self._servidor is None:
            return
        self._servidor.shutdown()
        self._servidor.server_close()
        self._thread.join()
        self._servidor = None
        self._thread = None

    @staticmethod
    def _decodificar_multipart(content_type, corpo):
        if not content_type or 'multipart/form-data' not in content_type:
            return {}, None
        mensagem = BytesParser(policy=policy.default).parsebytes(
            b'Content-Type: '
            + content_type.encode('ascii')
            + b'\r\nMIME-Version: 1.0\r\n\r\n'
            + corpo
        )
        campos = {}
        arquivo = None
        for parte in mensagem.iter_parts():
            if parte.get_content_disposition() != 'form-data':
                continue
            nome = parte.get_param('name', header='content-disposition')
            dados = parte.get_payload(decode=True) or b''
            if parte.get_filename() is not None:
                arquivo = dados
                campos[f'{nome}_filename'] = parte.get_filename()
            elif nome:
                charset = parte.get_content_charset() or 'utf-8'
                campos[nome] = dados.decode(charset)
        return campos, arquivo
