"""Prazo absoluto: interrupção de socket, guarda por thread e pools.

O prazo do job é um ``time.monotonic()`` absoluto; estas classes registram
o socket corrente numa guarda por requisição e o interrompem por
``shutdown`` quando o prazo estoura, acordando um ``recv`` bloqueado em
outra thread.

``_PrazoAbsoluto`` lê ``ocr_client.time`` via pacote na montagem do timer —
o mesmo namespace alvo de ``patch('ia_ocr.ocr_client.time', relogio)``
(que no monólito alcançava este módulo e segue alcançando; ver
``cliente.py``/``http.py``).
"""

from __future__ import annotations

import socket
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

from .. import ocr_client  # alvo de patch: ia_ocr.ocr_client.time


_contexto_prazo = threading.local()


def _interromper_socket(sock):
    # SSLTransport (TLS sobre túnel de proxy) não tem shutdown: o socket real fica em .socket.
    shutdown = getattr(sock, 'shutdown', None)
    if shutdown is None:
        socket_de_baixo = getattr(sock, 'socket', None)
        if socket_de_baixo is not None:
            _interromper_socket(socket_de_baixo)
        return
    try:
        shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


class _PrazoAbsoluto:
    # shutdown (e não close) é o que acorda um recv bloqueado em outra thread.

    def __init__(self, prazo):
        self._lock = threading.Lock()
        self._sock = None
        self._ativo = True
        self.estourou = False
        self._timer = threading.Timer(
            max(0.0, prazo - ocr_client.time.monotonic()), self._estourar
        )
        self._timer.daemon = True
        self._timer.start()

    def registrar(self, sock):
        with self._lock:
            if not self._ativo:
                return
            self._sock = sock
            if self.estourou:
                _interromper_socket(sock)

    def soltar(self):
        with self._lock:
            self._sock = None

    def encerrar(self):
        with self._lock:
            self._ativo = False
            self._sock = None
        self._timer.cancel()
        self._timer.join()

    def _estourar(self):
        with self._lock:
            if not self._ativo:
                return
            self.estourou = True
            if self._sock is not None:
                _interromper_socket(self._sock)


class _ConexaoComPrazo:
    # Conexão do pool só fica registrada na guarda da requisição que a pegou;
    # ao voltar ao pool o socket é solto para não derrubar a próxima requisição.
    _guarda = None

    def acompanhar(self, guarda):
        self._guarda = guarda
        if guarda is not None and self.sock is not None:
            guarda.registrar(self.sock)

    def _new_conn(self):
        # Registra antes do túnel de CONNECT, cujas respostas são lidas dentro de connect().
        sock = super()._new_conn()
        if self._guarda is not None:
            self._guarda.registrar(sock)
        return sock

    def connect(self):
        super().connect()
        if self._guarda is not None:
            self._guarda.registrar(self.sock)

    def soltar_prazo(self):
        if self._guarda is not None:
            self._guarda.soltar()
            self._guarda = None


class _ConexaoHttpComPrazo(_ConexaoComPrazo, HTTPConnection):
    pass


class _ConexaoHttpsComPrazo(_ConexaoComPrazo, HTTPSConnection):
    # urllib3 troca o socket TCP por um SSLSocket aqui; o TCP registrado em _new_conn fica com fd=-1.
    def _connect_tls_proxy(self, hostname, sock):
        ssl_sock = super()._connect_tls_proxy(hostname, sock)
        if self._guarda is not None:
            self._guarda.registrar(ssl_sock)
        return ssl_sock


class _PoolComPrazo:
    def _get_conn(self, *args, **kwargs):
        conexao = super()._get_conn(*args, **kwargs)
        conexao.acompanhar(getattr(_contexto_prazo, 'guarda', None))
        return conexao

    def _put_conn(self, conexao):
        if isinstance(conexao, _ConexaoComPrazo):
            conexao.soltar_prazo()
        super()._put_conn(conexao)


class _PoolHttpComPrazo(_PoolComPrazo, HTTPConnectionPool):
    ConnectionCls = _ConexaoHttpComPrazo


class _PoolHttpsComPrazo(_PoolComPrazo, HTTPSConnectionPool):
    ConnectionCls = _ConexaoHttpsComPrazo


_POOLS_COM_PRAZO = {'http': _PoolHttpComPrazo, 'https': _PoolHttpsComPrazo}


class _AdaptadorComPrazo(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = _POOLS_COM_PRAZO

    def proxy_manager_for(self, *args, **kwargs):
        gerenciador = super().proxy_manager_for(*args, **kwargs)
        classes = dict(gerenciador.pool_classes_by_scheme)
        for esquema, padrao in (
            ('http', HTTPConnectionPool),
            ('https', HTTPSConnectionPool),
        ):
            if classes.get(esquema) is padrao:
                classes[esquema] = _POOLS_COM_PRAZO[esquema]
        gerenciador.pool_classes_by_scheme = classes
        return gerenciador


def _sessao_com_prazo():
    sessao = requests.Session()
    adaptador = _AdaptadorComPrazo()
    sessao.mount('http://', adaptador)
    sessao.mount('https://', adaptador)
    return sessao
