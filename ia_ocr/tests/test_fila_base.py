"""Infraestrutura dos testes de fila — migração VERBATIM de
``ia_ocr/tests/test_fila.py`` (Etapa 13 do plano de 400 linhas).

Nenhum teste aqui: constantes de PII, ``_resultado``, os 11 backends
``Backend*`` e a sentinela ``_Pare``. Os backends são nomeados por caminho
pontuado (``ia_ocr.tests.test_fila.<Backend>``) nas ``override_settings`` —
a fachada ``test_fila.py`` os reexporta.
"""

from django.db.utils import DatabaseError

from ia_ocr.backends import OcrBackend, OcrBackendError, ResultadoOcr


MARCADOR_PII = 'CPF-SINTETICO-999.888.777-66'
MARCADOR_PII_NOME = 'PROPRIETARIO-SINTETICO-XYZ'


def _resultado():
    return ResultadoOcr(
        paginas=[
            {
                'numero_pagina': 1,
                'texto': 'texto sintético da página 1',
                'blocos': [{'bbox': [0, 0, 100, 200]}],
            },
            {'numero_pagina': 2, 'texto': 'texto sintético da página 2', 'blocos': None},
        ],
        sha256_pdf='a' * 64,
        page_count=2,
        timings_ms={'total': 1234},
        origem='ocr',
    )


class BackendSucesso(OcrBackend):
    def processar(self, job):
        return _resultado()


class BackendFalhaContratual(OcrBackend):
    def processar(self, job):
        raise OcrBackendError('SERVICE_UNAVAILABLE', 'gateway respondeu 503')


class BackendErroGenerico(OcrBackend):
    def processar(self, job):
        raise RuntimeError('explode de propósito')


class BackendDatabaseError(OcrBackend):
    def processar(self, job):
        raise DatabaseError('boom sintético')


class BackendVazaPii(OcrBackend):
    def processar(self, job):
        raise RuntimeError(
            f'falha lendo página do documento {MARCADOR_PII} de {MARCADOR_PII_NOME}'
        )


class BackendSemOrigem(OcrBackend):
    """Resultado sem `origem` explícita: a origem definida no criar_job prevalece."""

    def processar(self, job):
        return ResultadoOcr(
            paginas=[{'numero_pagina': 1, 'texto': 'texto sintético', 'blocos': None}],
            sha256_pdf='e' * 64,
            page_count=1,
            timings_ms={'total': 10},
        )


class BackendOrigemTextoEmbutido(OcrBackend):
    def processar(self, job):
        resultado = _resultado()
        resultado.origem = 'texto_embutido'
        return resultado


class BackendOrigemInvalida(OcrBackend):
    def processar(self, job):
        resultado = _resultado()
        resultado.origem = 'origem_invalida'
        return resultado


ARQUIVO_ALVO_FALHA_PERSISTENCIA = 'alvo-pagina-duplicada.pdf'


class BackendTimingsSuspeitos(OcrBackend):
    """timings_ms com texto/bool/lista: só escalares numéricos podem persistir."""

    def processar(self, job):
        return ResultadoOcr(
            paginas=[{'numero_pagina': 1, 'texto': 'texto sintético', 'blocos': None}],
            sha256_pdf='g' * 64,
            page_count=1,
            timings_ms={
                'total': 4321,
                'arquivo': f'{MARCADOR_PII_NOME}.pdf',
                'aceito': True,
                'lista': [1, 2],
            },
        )


class BackendErroForaDoContrato(OcrBackend):
    """Código fora de [A-Z0-9_] e mensagem longa com quebra de linha."""

    def processar(self, job):
        raise OcrBackendError(
            'serviço fora do ar!', 'x' * 600 + '\nquebra de linha sintética'
        )


class _Pare(Exception):
    """Sentinela para encerrar o modo contínuo no teste."""
