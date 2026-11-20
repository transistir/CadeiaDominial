"""Sessão HTTP com prazo absoluto e leitura de resposta limitada.

``time`` NÃO é importado aqui: ``_ClienteHttpComPrazo._restante`` lê
``ocr_client.time`` via pacote a cada chamada — o teste do 429 no fim do
orçamento faz ``patch('ia_ocr.ocr_client.time', relogio)`` e injeta o
relógio falso por esse namespace (o mesmo padrão de
``services/paginas.py``). Os demais usos de ``time`` do pacote ficam nos
módulos que não são alvo desse patch.
"""

from __future__ import annotations

import json
import logging

import requests
import urllib3

from .. import ocr_client  # alvo de patch: ia_ocr.ocr_client.time
from ..backends import OrcamentoEsgotado
from .prazo import _PrazoAbsoluto, _contexto_prazo, _sessao_com_prazo

logger = logging.getLogger(__name__)


class _ClienteHttpComPrazo:
    """Sessão HTTP com prazo absoluto e leitura de resposta limitada.

    O limite de resposta é obrigatório por instância (__init__) — a base
    NÃO define MAX_BYTES_RESPOSTA como atributo de classe, para que o
    limite de um cliente não vaze para outro por acidente (achado N8).
    """

    TAMANHO_CHUNK_RESPOSTA = 4 * 1024
    _MENSAGEM_CABECALHOS = ''
    timeout_s: float
    _MENSAGEM_PRAZO_RESPOSTA = 'Prazo esgotado durante a resposta.'

    def __init__(
        self,
        base_url,
        token,
        access_client_id,
        access_client_secret,
        *,
        max_bytes_resposta,
        sessao=None,
    ):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.access_client_id = access_client_id
        self.access_client_secret = access_client_secret
        self.max_bytes_resposta = max_bytes_resposta
        self.sessao = sessao or _sessao_com_prazo()
        self._primeira_requisicao = True

    def _executar_tentativa(self, metodo, url, prazo, **kw):
        """Uma tentativa HTTP completa: envia, lê e fecha. Devolve
        (status, corpo_bruto). Converte só o estouro do prazo absoluto em
        OrcamentoEsgotado; todo o resto (TransportException inclusive)
        sobe para a política de retry da subclasse."""
        restante = self._restante(prazo)
        dados = kw.get('data')
        if hasattr(dados, 'reset'):
            dados.reset()

        cabecalhos = {'Accept-Encoding': 'identity', **kw.get('headers', {})}
        cabecalhos.update(
            {
                'CF-Access-Client-Id': self.access_client_id,
                'CF-Access-Client-Secret': self.access_client_secret,
                'X-Internal-Token': self.token,
            }
        )
        self._log_cabecalhos_aplicados()

        argumentos = dict(kw)
        argumentos['headers'] = cabecalhos
        argumentos['allow_redirects'] = False
        argumentos['stream'] = True
        argumentos['timeout'] = min(self.timeout_s, restante)

        guarda = _PrazoAbsoluto(prazo)
        try:
            try:
                _contexto_prazo.guarda = guarda
                try:
                    resposta = self.sessao.request(metodo, url, **argumentos)
                finally:
                    _contexto_prazo.guarda = None
                try:
                    corpo_bruto = self._ler_resposta(resposta, prazo)
                finally:
                    guarda.encerrar()
                    resposta.close()
            except OrcamentoEsgotado:
                raise
            except Exception as excecao:
                if guarda.estourou:
                    raise OrcamentoEsgotado(
                        self._MENSAGEM_PRAZO_RESPOSTA
                    ) from excecao
                raise
        finally:
            guarda.encerrar()

        return resposta.status_code, corpo_bruto

    def _log_cabecalhos_aplicados(self):
        """Uma linha por requisição com os nomes dos cabeçalhos de
        autenticação. A primeira requisição de cada instância sai em
        INFO; as seguintes em DEBUG. Valores e corpo nunca aparecem —
        a mensagem é uma constante fixa.
        """
        if self._primeira_requisicao:
            self._primeira_requisicao = False
            logger.info('%s', self._MENSAGEM_CABECALHOS)
        else:
            logger.debug('%s', self._MENSAGEM_CABECALHOS)

    def _ler_resposta(self, resposta, prazo):
        partes = []
        total = 0
        while True:
            self._restante(prazo)
            chunk = self._ler_bloco(resposta, self.TAMANHO_CHUNK_RESPOSTA)
            if not chunk:
                break
            total += len(chunk)
            if total > self.max_bytes_resposta:
                raise self._erro_resposta_grande()
            partes.append(chunk)
        self._restante(prazo)
        return b''.join(partes)

    def _erro_resposta_grande(self):
        """Erro do contrato da subclasse para resposta acima do limite."""
        raise NotImplementedError

    @staticmethod
    def _ler_bloco(resposta, tamanho):
        # read1 volta a cada recv: iter_content esperaria o bloco inteiro e ignoraria o prazo.
        try:
            return resposta.raw.read1(tamanho, decode_content=True)
        except urllib3.exceptions.HTTPError as exc:
            raise requests.exceptions.ConnectionError(exc) from None

    @staticmethod
    def _json(corpo):
        try:
            return json.loads(corpo.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _restante(prazo):
        restante = prazo - ocr_client.time.monotonic()
        if restante <= 0:
            raise OrcamentoEsgotado('Prazo do job esgotado.')
        return restante
