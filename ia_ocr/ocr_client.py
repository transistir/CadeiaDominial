"""Cliente HTTP de baixo nível para o serviço OCR v1.0.1."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from urllib.parse import quote

import requests

from ia_ocr.backends import OcrBackendError, OrcamentoEsgotado

logger = logging.getLogger(__name__)


CODIGOS_CONTRATO = frozenset(
    {
        'INVALID_INPUT',
        'UNSUPPORTED_MEDIA_TYPE',
        'FILE_TOO_LARGE',
        'EMPTY_FILE',
        'INVALID_PDF',
        'ENCRYPTED_PDF',
        'TOO_MANY_PAGES',
        'PDF_PAGE_TOO_LARGE',
        'INVALID_OCR_RESULT',
        'EMPTY_OCR_RESULT',
        'OUTPUT_TOO_LARGE',
        'JOB_NOT_FOUND',
        'JOB_TIMEOUT',
        'JOB_ID_CONFLICT',
        'QUEUE_FULL',
        'UNAUTHORIZED',
        'INFERENCE_FAILED',
    }
)


class _MultipartEncoder:
    """Corpo multipart reabrível, lido em blocos sob o mesmo prazo."""

    TAMANHO_CHUNK = 64 * 1024

    def __init__(self, caminho_pdf, campos, boundary, prazo):
        self.caminho_pdf = os.fspath(caminho_pdf)
        self.prazo = prazo
        self.boundary = boundary
        self._preambulo = self._montar_preambulo(campos)
        self._epilogo = f'\r\n--{boundary}--\r\n'.encode('ascii')
        self._tamanho_arquivo = os.path.getsize(self.caminho_pdf)
        self._arquivo = None
        self._pos_preambulo = 0
        self._pos_epilogo = 0
        self._arquivo_concluido = False

    def __len__(self):
        return len(self._preambulo) + self._tamanho_arquivo + len(self._epilogo)

    def reset(self):
        self.close()
        self._pos_preambulo = 0
        self._pos_epilogo = 0
        self._arquivo_concluido = False

    def close(self):
        if self._arquivo is not None:
            self._arquivo.close()
            self._arquivo = None

    def read(self, amt=None):
        self._conferir_prazo()
        limite = amt if amt is not None and amt >= 0 else self.TAMANHO_CHUNK
        if limite == 0:
            return b''

        saida = bytearray()
        while len(saida) < limite:
            restante = limite - len(saida)
            if self._pos_preambulo < len(self._preambulo):
                fim = min(len(self._preambulo), self._pos_preambulo + restante)
                saida.extend(self._preambulo[self._pos_preambulo : fim])
                self._pos_preambulo = fim
                continue

            if not self._arquivo_concluido:
                self._conferir_prazo()
                if self._arquivo is None:
                    self._arquivo = open(self.caminho_pdf, 'rb')
                dados = self._arquivo.read(min(restante, self.TAMANHO_CHUNK))
                self._conferir_prazo()
                if dados:
                    saida.extend(dados)
                    continue
                self.close()
                self._arquivo_concluido = True
                continue

            if self._pos_epilogo < len(self._epilogo):
                fim = min(len(self._epilogo), self._pos_epilogo + restante)
                saida.extend(self._epilogo[self._pos_epilogo : fim])
                self._pos_epilogo = fim
                continue
            break
        return bytes(saida)

    def _montar_preambulo(self, campos):
        partes = []
        for nome, valor in campos:
            partes.extend(
                [
                    f'--{self.boundary}\r\n',
                    f'Content-Disposition: form-data; name="{nome}"\r\n\r\n',
                    f'{valor}\r\n',
                ]
            )
        partes.extend(
            [
                f'--{self.boundary}\r\n',
                'Content-Disposition: form-data; name="file"; '
                'filename="documento.pdf"\r\n',
                'Content-Type: application/pdf\r\n\r\n',
            ]
        )
        return ''.join(partes).encode('utf-8')

    def _conferir_prazo(self):
        if time.monotonic() >= self.prazo:
            raise OrcamentoEsgotado('Prazo do job esgotado durante o upload.')


class OcrServiceClient:
    """Cliente sem estado de negócio para os três endpoints OCR."""

    TAMANHO_CHUNK_RESPOSTA = 4 * 1024
    MAX_BYTES_RESPOSTA = 52_428_800
    # Evidência de aceite (2) do #259: os NOMES dos três cabeçalhos por
    # requisição — valores (token/credenciais) nunca entram no log.
    _MENSAGEM_CABECALHOS = (
        'servico OCR: cabecalhos de autenticacao aplicados: '
        'cf-access-client-id, cf-access-client-secret, x-internal-token'
    )

    def __init__(
        self,
        base_url,
        token,
        access_client_id,
        access_client_secret,
        timeout_s=30,
        max_tentativas=3,
        backoff_base_s=0.5,
        backoff_max_s=30,
        reserva_retry_s=0,
        poll_interval_s=5,
        sessao=None,
    ):
        if max_tentativas < 1:
            raise ValueError('max_tentativas deve ser pelo menos 1.')
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.access_client_id = access_client_id
        self.access_client_secret = access_client_secret
        self.timeout_s = timeout_s
        self.max_tentativas = max_tentativas
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s
        self.reserva_retry_s = reserva_retry_s
        self.poll_interval_s = poll_interval_s
        self.sessao = sessao or requests.Session()
        self._primeira_requisicao = True

    def enviar_job(self, caminho_pdf, job_id, prazo, **params):
        timeout_informado = params.pop('timeout_seconds', None)
        restante = self._restante(prazo)
        timeout_seconds = int(
            restante if timeout_informado is None else timeout_informado
        )
        timeout_seconds = max(1, min(86_400, timeout_seconds))

        campos = [
            ('job_id', job_id),
            ('dpi', params.pop('dpi', 200)),
            ('timeout_seconds', timeout_seconds),
            ('max_pages', params.pop('max_pages', 25)),
        ]
        lang = params.pop('lang', None)
        layout_detection = params.pop('layout_detection', None)
        if params:
            desconhecidos = ', '.join(sorted(params))
            raise TypeError(f'Parâmetros OCR desconhecidos: {desconhecidos}.')
        if lang is not None:
            campos.append(('lang', lang))
        if layout_detection is not None:
            campos.append(
                (
                    'layout_detection',
                    'true' if layout_detection else 'false',
                )
            )

        boundary = f'ocr-{uuid.uuid4().hex}'
        encoder = _MultipartEncoder(caminho_pdf, campos, boundary, prazo)
        try:
            return self._requisicao(
                'POST',
                '/v1/ocr/jobs',
                prazo,
                data=encoder,
                headers={
                    'Content-Type': f'multipart/form-data; boundary={boundary}'
                },
            )
        finally:
            encoder.close()

    def consultar_job(self, job_id, prazo):
        job_id_url = quote(str(job_id), safe='')
        return self._requisicao('GET', f'/v1/ocr/jobs/{job_id_url}', prazo)

    def obter_resultado(self, job_id, prazo, formato='full'):
        job_id_url = quote(str(job_id), safe='')
        return self._requisicao(
            'GET',
            f'/v1/ocr/jobs/{job_id_url}/result',
            prazo,
            params={'format': formato},
        )

    def _requisicao(self, metodo, caminho, prazo, **kw):
        """Executa, lê e classifica toda chamada HTTP feita pelo cliente."""
        url = f'{self.base_url}/{caminho.lstrip("/")}'
        dados = kw.get('data')
        # A reserva protege o reenvio do job (POST); um GET barato usa o prazo inteiro.
        reserva_s = self.reserva_retry_s if metodo.upper() == 'POST' else 0
        ultimo_codigo = 'SERVICE_UNAVAILABLE'
        ultima_mensagem = 'Serviço OCR indisponível.'
        tentativas_limitadas = 0
        numero_retry = 0

        while True:
            restante = self._restante(prazo)
            if hasattr(dados, 'reset'):
                dados.reset()

            cabecalhos = dict(kw.get('headers', {}))
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

            try:
                resposta = self.sessao.request(metodo, url, **argumentos)
                try:
                    corpo_bruto = self._ler_resposta(resposta, prazo)
                finally:
                    resposta.close()
            except OrcamentoEsgotado:
                raise
            except requests.RequestException:
                ultimo_codigo = 'SERVICE_UNAVAILABLE'
                ultima_mensagem = 'Falha de transporte ao acessar o serviço OCR.'
                tentativas_limitadas += 1
                if tentativas_limitadas >= self.max_tentativas:
                    raise OcrBackendError(ultimo_codigo, ultima_mensagem) from None
                numero_retry += 1
                self._aguardar_retry(
                    numero_retry, prazo, reserva_s, ultimo_codigo, ultima_mensagem
                )
                continue

            corpo = self._json(corpo_bruto)
            status = resposta.status_code
            if status in (200, 202):
                if isinstance(corpo, dict):
                    return corpo
                raise OcrBackendError(
                    'INVALID_OCR_RESULT', 'Resposta JSON inválida do serviço OCR.'
                )
            if status in (401, 403) or 300 <= status < 400:
                raise OcrBackendError('UNAUTHORIZED', 'Acesso ao serviço OCR negado.')
            if status == 404:
                raise OcrBackendError('JOB_NOT_FOUND', 'Job OCR não encontrado.')
            if status == 409:
                if metodo.upper() == 'POST' and caminho.rstrip('/') == '/v1/ocr/jobs':
                    raise OcrBackendError(
                        'JOB_ID_CONFLICT', 'O job_id já identifica outro arquivo.'
                    )
                if isinstance(corpo, dict):
                    return corpo
                raise OcrBackendError(
                    'INVALID_OCR_RESULT', 'Estado de job inválido na resposta 409.'
                )
            if status in (400, 413, 415):
                padrao = {
                    400: 'INVALID_INPUT',
                    413: 'FILE_TOO_LARGE',
                    415: 'UNSUPPORTED_MEDIA_TYPE',
                }[status]
                codigo, mensagem = self._erro_do_corpo(corpo, padrao)
                raise OcrBackendError(codigo, mensagem)

            retry_ate_prazo = False
            if status == 503:
                codigo, mensagem = self._erro_do_corpo(
                    corpo, 'SERVICE_UNAVAILABLE'
                )
                if codigo == 'UNAUTHORIZED':
                    raise OcrBackendError(codigo, mensagem)
                if codigo == 'QUEUE_FULL':
                    ultimo_codigo = codigo
                    ultima_mensagem = mensagem
                    retry_ate_prazo = True
                else:
                    ultimo_codigo = 'SERVICE_UNAVAILABLE'
                    ultima_mensagem = 'Serviço OCR indisponível.'
            elif status == 429:
                ultimo_codigo = 'QUEUE_FULL'
                ultima_mensagem = 'Serviço OCR com fila cheia (429).'
                retry_ate_prazo = True
            elif 500 <= status < 600:
                ultimo_codigo = 'SERVICE_UNAVAILABLE'
                ultima_mensagem = 'Serviço OCR indisponível.'
            else:
                raise OcrBackendError(
                    'SERVICE_UNAVAILABLE',
                    f'Resposta HTTP inesperada do serviço OCR: {status}.',
                )

            if not retry_ate_prazo:
                tentativas_limitadas += 1
                if tentativas_limitadas >= self.max_tentativas:
                    raise OcrBackendError(ultimo_codigo, ultima_mensagem)
            numero_retry += 1
            self._aguardar_retry(
                numero_retry, prazo, reserva_s, ultimo_codigo, ultima_mensagem
            )

    def _log_cabecalhos_aplicados(self):
        """Uma linha por requisição com os nomes dos três cabeçalhos
        (evidência de aceite 2 do #259). A primeira requisição de cada
        instância sai em INFO; as seguintes (polls, retries) em DEBUG,
        para não poluir. Valores, nome de arquivo e texto do documento
        nunca aparecem — a mensagem é uma constante fixa.
        """
        if self._primeira_requisicao:
            self._primeira_requisicao = False
            logger.info('%s', self._MENSAGEM_CABECALHOS)
        else:
            logger.debug('%s', self._MENSAGEM_CABECALHOS)

    def _ler_resposta(self, resposta, prazo):
        partes = []
        total = 0
        for chunk in resposta.iter_content(chunk_size=self.TAMANHO_CHUNK_RESPOSTA):
            self._restante(prazo)
            if not chunk:
                continue
            total += len(chunk)
            if total > self.MAX_BYTES_RESPOSTA:
                raise OcrBackendError(
                    'OUTPUT_TOO_LARGE', 'Resposta do serviço OCR excede o limite.'
                )
            partes.append(chunk)
        self._restante(prazo)
        return b''.join(partes)

    def _aguardar_retry(self, tentativa, prazo, reserva_s, codigo, mensagem):
        try:
            self._aguardar_backoff(tentativa, prazo, reserva_s)
        except OrcamentoEsgotado:
            if codigo == 'QUEUE_FULL':
                raise OcrBackendError(codigo, mensagem) from None
            raise

    def _aguardar_backoff(self, tentativa, prazo, reserva_s):
        atraso = min(
            self.backoff_base_s * (2 ** (tentativa - 1)),
            self.backoff_max_s,
        )
        restante = self._restante(prazo)
        if restante <= reserva_s:
            raise OrcamentoEsgotado('Prazo do job esgotado antes do retry.')
        if atraso >= restante - reserva_s:
            raise OrcamentoEsgotado('Prazo do job esgotado antes do retry.')
        if atraso > 0:
            time.sleep(atraso)
        restante = self._restante(prazo)
        if restante <= reserva_s:
            raise OrcamentoEsgotado('Prazo do job esgotado antes do retry.')

    @staticmethod
    def _json(corpo):
        try:
            return json.loads(corpo.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _erro_do_corpo(corpo, padrao):
        erro = corpo.get('error', {}) if isinstance(corpo, dict) else {}
        codigo = erro.get('code')
        if codigo not in CODIGOS_CONTRATO and codigo != 'SERVICE_UNAVAILABLE':
            codigo = padrao
        mensagem = erro.get('message')
        if not isinstance(mensagem, str) or not mensagem:
            mensagem = f'Erro do serviço OCR: {codigo}.'
        return codigo, mensagem

    @staticmethod
    def _restante(prazo):
        restante = prazo - time.monotonic()
        if restante <= 0:
            raise OrcamentoEsgotado('Prazo do job OCR esgotado.')
        return restante
