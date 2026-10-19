"""Cliente HTTP do serviço de extração estruturada (I-5).

Espelha ``ia_ocr.ocr_client`` (mesma sessão de prazo absoluto) mas com a
política dogmática da extração: UMA tentativa, sem retry — nem 429, nem
503. Quem orquestra a janela é o worker da I-6.
"""

from __future__ import annotations

import json
import time

from django.conf import settings
import requests

from ia_ocr.ocr_client import _ClienteHttpComPrazo, OrcamentoEsgotado

from .extracao_backends import ExtracaoBackendError

# Extrai a partir de matrícula: um POST por matrícula — e ponto.
CAMINHO_EXTRACAO = '/v1/extracao/matricula'


class ExtracaoServiceClient(_ClienteHttpComPrazo):
    """Cliente sem estado de negócio para o endpoint de extração."""

    _MENSAGEM_CABECALHOS = (
        'servico de extracao: cabecalhos de autenticacao aplicados: '
        'cf-access-client-id, cf-access-client-secret, x-internal-token'
    )
    _MENSAGEM_PRAZO_RESPOSTA = 'Prazo da extração esgotado durante a resposta.'

    def __init__(self, base_url, token, access_client_id, access_client_secret, sessao=None):
        super().__init__(
            base_url,
            token,
            access_client_id,
            access_client_secret,
            max_bytes_resposta=settings.EXTRACAO_MAX_BYTES_RESPOSTA,
            sessao=sessao,
        )
        self.timeout_s = settings.EXTRACAO_HTTP_TIMEOUT_SECONDS

    def extrair(self, requisicao):
        """Uma tentativa: POST único do requisito já montado."""
        corpo = json.dumps(requisicao).encode('utf-8')
        if len(corpo) > settings.EXTRACAO_MAX_BYTES_REQUISICAO:
            raise ExtracaoBackendError(
                'ENTRADA_GRANDE_DEMAIS',
                'Requisição de extração excede o limite.',
            )

        prazo = time.monotonic() + settings.EXTRACAO_HTTP_TIMEOUT_SECONDS
        url = f'{self.base_url}{CAMINHO_EXTRACAO}'
        try:
            status, corpo_bruto = self._executar_tentativa(
                'POST',
                url,
                prazo,
                data=corpo,
                headers={'Content-Type': 'application/json'},
            )
        except OrcamentoEsgotado:
            raise ExtracaoBackendError(
                'PRAZO_ESGOTADO', 'Prazo do worker de extração esgotado.'
            ) from None
        except requests.RequestException:
            raise ExtracaoBackendError(
                'EXTRACAO_INDISPONIVEL',
                'Falha de transporte ao acessar o serviço de extração.',
            ) from None

        corpo_resposta = self._json(corpo_bruto)
        if status == 200:
            if isinstance(corpo_resposta, dict):
                return corpo_resposta
            raise ExtracaoBackendError(
                'RESPOSTA_INVALIDA', 'Resposta JSON inválida do serviço de extração.'
            )
        if 300 <= status < 400 or status in (401, 403):
            raise ExtracaoBackendError(
                'NAO_AUTORIZADO', 'Acesso ao serviço de extração negado.'
            )
        if status == 413:
            raise ExtracaoBackendError(
                'ENTRADA_GRANDE_DEMAIS',
                'O serviço de extração recusou a requisição (413).',
            )
        if status == 429 or 500 <= status < 600:
            raise ExtracaoBackendError(
                'EXTRACAO_INDISPONIVEL', 'Serviço de extração indisponível.'
            )
        raise ExtracaoBackendError(
            'RESPOSTA_INVALIDA',
            f'Resposta HTTP inesperada do serviço de extração: {status}.',
        )

    def _erro_resposta_grande(self):
        return ExtracaoBackendError(
            'RESPOSTA_GRANDE_DEMAIS',
            'Resposta do serviço de extração excede o limite.',
        )
