"""Cliente HTTP de baixo nível para o serviço OCR v1.0.1."""

from __future__ import annotations

import json
import os
import time
import uuid
from urllib.parse import quote

import requests

from ia_ocr.backends import OcrBackendError


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


class OrcamentoEsgotado(Exception):
    """O prazo monotônico compartilhado da operação foi consumido."""


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

    TAMANHO_CHUNK_RESPOSTA = 64 * 1024
    MAX_BYTES_RESPOSTA = 52_428_800

    def __init__(
        self,
        base_url,
        token,
        access_client_id,
        access_client_secret,
        timeout_s=30,
        max_tentativas=3,
        backoff_base_s=0.5,
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
        self.poll_interval_s = poll_interval_s
        self.sessao = sessao or requests.Session()

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
        ultimo_codigo = 'SERVICE_UNAVAILABLE'
        ultima_mensagem = 'Serviço OCR indisponível.'

        for tentativa in range(1, self.max_tentativas + 1):
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
                if tentativa == self.max_tentativas:
                    raise OcrBackendError(ultimo_codigo, ultima_mensagem) from None
                self._aguardar_retry(tentativa, prazo)
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

            if status == 503:
                codigo, mensagem = self._erro_do_corpo(
                    corpo, 'SERVICE_UNAVAILABLE'
                )
                if codigo == 'UNAUTHORIZED':
                    raise OcrBackendError(codigo, mensagem)
                if codigo == 'QUEUE_FULL':
                    ultimo_codigo = codigo
                    ultima_mensagem = mensagem
                else:
                    ultimo_codigo = 'SERVICE_UNAVAILABLE'
                    ultima_mensagem = 'Serviço OCR indisponível.'
            elif status == 429 or 500 <= status < 600:
                ultimo_codigo = 'SERVICE_UNAVAILABLE'
                ultima_mensagem = 'Serviço OCR indisponível.'
            else:
                raise OcrBackendError(
                    'SERVICE_UNAVAILABLE',
                    f'Resposta HTTP inesperada do serviço OCR: {status}.',
                )

            if tentativa == self.max_tentativas:
                raise OcrBackendError(ultimo_codigo, ultima_mensagem)
            self._aguardar_retry(tentativa, prazo)

        raise OcrBackendError(ultimo_codigo, ultima_mensagem)

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

    def _aguardar_retry(self, tentativa, prazo):
        atraso = self.backoff_base_s * (2 ** (tentativa - 1))
        restante = self._restante(prazo)
        if atraso >= restante:
            raise OrcamentoEsgotado('Prazo do job esgotado antes do retry.')
        if atraso > 0:
            time.sleep(atraso)
        self._restante(prazo)

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
